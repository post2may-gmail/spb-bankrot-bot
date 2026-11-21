from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from bankrot_bot.models import Lot
from bankrot_bot.photos import normalize_photo_urls

logger = logging.getLogger(__name__)

# Официальный API ГИС «Торги» (Торги России).
TORGI_API = "https://torgi.gov.ru/new/api/public/lotcards/search"
# Публичное зеркало открытых данных (fallback, если ГИС недоступна с хоста).
TORGIOPEN_API = "https://torgiopen.ru/api/lots"

# dynSubjRF для СПб в ГИС часто совпадает с кодом 78; при 0 результатов пробуем соседние.
SPB_DYN_CODES = ("78", "40")
# catCode=7 — недвижимость (родительский узел).
REAL_ESTATE_CAT = "7"

BANKRUPTCY_HINT = re.compile(
    r"(?i)(банкрот|конкурсн\w*\s+управляющ|реализаци\w*\s+имуществ|должник|ефрсб|fedresurs)"
)


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _from_torgi_gov_item(item: dict[str, Any]) -> Lot | None:
    lot_name = (item.get("lotName") or "").strip()
    lot_desc = (item.get("lotDescription") or "").strip()
    bidd_type = item.get("biddType") or {}
    bidd_form = item.get("biddForm") or {}
    type_name = ""
    if isinstance(bidd_type, dict):
        type_name = str(bidd_type.get("name") or bidd_type.get("code") or "")
    form_name = ""
    if isinstance(bidd_form, dict):
        form_name = str(bidd_form.get("name") or bidd_form.get("code") or "")

    blob = " ".join([lot_name, lot_desc, type_name, form_name])
    # Только банкротство: по типу торгов или явным маркерам в тексте.
    type_l = f"{type_name} {form_name}".lower()
    if "банкрот" not in type_l and not BANKRUPTCY_HINT.search(blob):
        return None

    notice = str(item.get("noticeNumber") or "")
    lot_number = str(item.get("lotNumber") or "1")
    external_id = str(item.get("id") or f"{notice}_{lot_number}")
    url = f"https://torgi.gov.ru/new/public/lots/lot/{notice}_{lot_number}"
    if notice and lot_number:
        url = f"https://torgi.gov.ru/new/public/lots/lot/{notice}_{lot_number}"

    address = ""
    area = None
    for ch in item.get("characteristics") or []:
        name = str(ch.get("name") or ch.get("code") or "")
        val = ch.get("characteristicValue")
        if val is None:
            val = ch.get("value")
        if "адрес" in name.lower() and val:
            address = str(val)
        if "площад" in name.lower() and area is None:
            area = _num(val)

    photos: list[str] = []
    for img in item.get("lotImages") or []:
        if isinstance(img, str) and img:
            photos.append(f"https://torgi.gov.ru/new/file-store/v1/{img}")

    category = item.get("category") or {}
    cat_name = category.get("name") if isinstance(category, dict) else "Недвижимость"

    return Lot(
        source="torgi.gov.ru",
        external_id=external_id,
        title=lot_name or f"Лот {external_id}",
        description=lot_desc[:1500],
        url=url,
        price=_num(item.get("priceMin")),
        address=address,
        area_sqm=area,
        region="Санкт-Петербург",
        category=str(cat_name or "Недвижимость"),
        auction_form=form_name or type_name,
        published_at=str(item.get("createDate") or item.get("firstVersionPublicationDate") or "")
        or None,
        photos=photos,
        raw_text=blob,
    )


async def _fetch_official(
    client: httpx.AsyncClient,
    *,
    max_pages: int,
) -> list[Lot]:
    lots: list[Lot] = []
    for dyn in SPB_DYN_CODES:
        page_lots: list[Lot] = []
        for page in range(max_pages):
            params = {
                "lotStatus": "PUBLISHED",
                "catCode": REAL_ESTATE_CAT,
                "dynSubjRF": dyn,
                "sort": "firstVersionPublicationDate,desc",
                "size": 20,
                "page": page,
            }
            try:
                resp = await client.get(TORGI_API, params=params, timeout=12.0)
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "torgi.gov.ru unavailable (dyn=%s page=%s): %s",
                    dyn,
                    page,
                    exc or type(exc).__name__,
                )
                return lots
            content = data.get("content") or []
            if not content:
                break
            for item in content:
                lot = _from_torgi_gov_item(item)
                if lot:
                    page_lots.append(lot)
            total_pages = int(data.get("totalPages") or 1)
            if page + 1 >= total_pages:
                break
        lots.extend(page_lots)
        if page_lots or lots:
            break
    return lots


def _from_torgiopen_item(item: dict[str, Any]) -> Lot | None:
    # Только продажа (не аренда).
    tt = (item.get("transactionType") or "").lower()
    if tt == "rent":
        return None

    title = (item.get("title") or "").strip()
    description = (item.get("description") or "").strip()
    address = (item.get("address") or "").strip()
    category = item.get("category") or {}
    cat_slug = ""
    cat_name = "Недвижимость"
    if isinstance(category, dict):
        cat_slug = str(category.get("slug") or "")
        cat_name = str(category.get("name") or cat_name)
    # Жёстко только категория недвижимости у зеркала.
    if cat_slug and cat_slug != "real_estate":
        return None
    blob = " ".join([title, description, address, cat_name])

    sources = item.get("sources") or []
    source_names = " ".join(str(s.get("source") or "") for s in sources if isinstance(s, dict))
    primary = item.get("primarySourceUrl") or ""
    # Канал bankruptcy = торги по банкротству с ЭТП / ЕФРСБ.
    channel = (item.get("channel") or "").lower()
    if channel != "bankruptcy" and "bankr" not in source_names.lower():
        if "torgi.gov.ru" in primary and not BANKRUPTCY_HINT.search(blob):
            return None

    external_id = str(item.get("id") or item.get("dedupKey") or primary)
    url = primary or ""
    for s in sources:
        if isinstance(s, dict) and s.get("sourceUrl"):
            url = s["sourceUrl"]
            break
    if not url:
        url = f"https://torgiopen.ru/lots/{external_id}"

    # Предпочитаем ссылку на ГИС, если есть.
    for s in sources:
        if isinstance(s, dict) and "torgi.gov.ru" in str(s.get("sourceUrl") or ""):
            url = s["sourceUrl"]
            break

    label = "torgi.gov.ru" if "torgi.gov.ru" in url else "torgiopen"
    return Lot(
        source=label,
        external_id=external_id,
        title=title or f"Лот {external_id}",
        description=description[:1500],
        url=url,
        price=_num(item.get("currentPrice") if item.get("currentPrice") is not None else item.get("startPrice")),
        address=address,
        area_sqm=_num(item.get("areaSqm")),
        region=(item.get("region") or {}).get("name") if isinstance(item.get("region"), dict) else "Санкт-Петербург",
        category=cat_name,
        auction_form=str(item.get("auctionForm") or ""),
        published_at=str(item.get("publishedAt") or "") or None,
        photos=normalize_photo_urls(
            [p for p in (item.get("photos") or []) if isinstance(p, str)],
            limit=10,
        ),
        raw_text=blob,
        dedupe_key=f"torgiopen:{item.get('dedupKey') or external_id}",
    )


async def _fetch_torgiopen(
    client: httpx.AsyncClient,
    *,
    max_pages: int,
) -> list[Lot]:
    lots: list[Lot] = []
    seen: set[str] = set()
    queries = ("квартира", "жилое помещение", "")
    for query in queries:
        for page in range(1, max_pages + 1):
            params: dict[str, Any] = {
                "region": "78",
                "category": "real_estate",
                "channel": "bankruptcy",
                "pageSize": 50,
                "page": page,
                "sort": "fresh",
            }
            if query:
                params["q"] = query
            try:
                resp = await client.get(TORGIOPEN_API, params=params, timeout=30.0)
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:  # noqa: BLE001
                logger.warning("torgiopen q=%r page %s failed: %s", query, page, exc)
                break
            items = data.get("items") or []
            if not items:
                break
            for item in items:
                lot = _from_torgiopen_item(item)
                if not lot or lot.dedupe_key in seen:
                    continue
                seen.add(lot.dedupe_key)
                lots.append(lot)
            meta = data.get("meta") or {}
            total_pages = int(meta.get("totalPages") or 1)
            if page >= total_pages:
                break
    return lots


async def fetch_torgi_lots(
    client: httpx.AsyncClient,
    *,
    max_pages: int = 3,
) -> list[Lot]:
    """Лоты «Торгов России» / банкротных ЭТП: сначала ГИС, иначе открытое зеркало."""
    official = await _fetch_official(client, max_pages=max_pages)
    if official:
        logger.info("torgi.gov.ru returned %s bankruptcy lots", len(official))
        return official
    logger.info("falling back to torgiopen bankruptcy feed")
    return await _fetch_torgiopen(client, max_pages=max_pages)
