from __future__ import annotations

import logging
import re
from html import unescape
from typing import Any
from urllib.parse import urlencode, urljoin

import httpx

from bankrot_bot.models import Lot

logger = logging.getLogger(__name__)

BASE = "https://tbankrot.ru"

# Санкт-Петербург + недвижимость (жилая/нежилая/земля) + секция банкротство.
# stop — стоп-слова долевой собственности на стороне агрегатора.
SEARCH_PARAMS: list[tuple[str, str]] = [
    ("region[]", "58"),
    ("parent_cat[]", "2"),
    ("sub_cat[]", "3"),
    ("sub_cat[]", "4"),
    ("sub_cat[]", "5"),
    ("etp[]", "bankrupt"),
    ("type_1", "on"),  # публичное предложение
    ("type_2", "on"),  # аукцион
    ("stop", "доля, долевой, долей, аренда, аренды, найм"),
    ("sort", "created"),
    ("sort_order", "desc"),
]

LOT_SPLIT = re.compile(r'<div class="lot_title">', re.I)
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")
PRICE_RE = re.compile(
    r"(\d[\d\s]{2,}(?:[.,]\d{1,2})?)\s*₽",
)
AREA_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*м\s*[²2]", re.I)
ADDR_RE = re.compile(r"Адрес:\s*([^<]{5,180})", re.I)


def _clean(text: str) -> str:
    text = TAG_RE.sub(" ", text)
    text = unescape(text)
    return WS_RE.sub(" ", text).strip()


def _parse_price(text: str) -> float | None:
    m = PRICE_RE.search(text)
    if not m:
        return None
    raw = m.group(1).replace(" ", "").replace("\xa0", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_area(text: str) -> float | None:
    m = AREA_RE.search(text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


def _parse_address(html_chunk: str, plain: str) -> str:
    m = ADDR_RE.search(html_chunk)
    if m:
        return _clean(m.group(1))
    # fallback: строка с Санкт-Петербург
    for part in re.split(r"[.|;]", plain):
        if "петербург" in part.lower() or "спб" in part.lower():
            return part.strip()[:180]
    return ""


def _guess_title(plain: str, lot_id: str) -> str:
    # Часто формат: "<id> Лот N <blur> <Title>, Санкт-Петербург ..."
    m = re.search(
        rf"{lot_id}\s+Лот\s+\d+\s+(?:▒+\s+)?(.+?)(?:\s+Адрес:|\s+Cведения|\s+Сведения|$)",
        plain,
        re.I,
    )
    if m:
        title = m.group(1).strip()
        # обрежем слишком длинное описание
        if len(title) > 160:
            title = title[:157] + "…"
        return title
    return f"Лот {lot_id}"


def parse_listing_html(html: str) -> list[Lot]:
    lots: list[Lot] = []
    parts = LOT_SPLIT.split(html)[1:]
    seen: set[str] = set()
    for part in parts:
        id_m = re.search(r'class="lot_num[^"]*"[^>]*>(\d+)', part)
        if not id_m:
            continue
        lot_id = id_m.group(1)
        if lot_id in seen:
            continue
        seen.add(lot_id)
        chunk = part[:6000]
        plain = _clean(chunk)
        title = _guess_title(plain, lot_id)
        address = _parse_address(chunk, plain)
        price = _parse_price(plain)
        area = _parse_area(plain)
        url = urljoin(BASE, f"/item?id={lot_id}")
        # описание — кусок текста после заголовка
        description = plain
        if title and title in description:
            description = description.split(title, 1)[-1].strip()
        description = description[:1200]
        lots.append(
            Lot(
                source="tbankrot",
                external_id=lot_id,
                title=title,
                description=description,
                url=url,
                price=price,
                address=address,
                area_sqm=area,
                region="Санкт-Петербург",
                category="Недвижимость",
                auction_form="банкротство",
                raw_text=plain,
            )
        )
    return lots


async def fetch_tbankrot_lots(
    client: httpx.AsyncClient,
    *,
    max_pages: int = 3,
) -> list[Lot]:
    results: list[Lot] = []
    seen: set[str] = set()
    for page in range(1, max_pages + 1):
        params = list(SEARCH_PARAMS)
        if page > 1:
            params.append(("page", str(page)))
        url = f"{BASE}/?{urlencode(params)}"
        logger.info("tbankrot fetch page=%s", page)
        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("tbankrot page %s failed: %s", page, exc)
            break
        page_lots = parse_listing_html(resp.text)
        if not page_lots:
            break
        for lot in page_lots:
            if lot.external_id in seen:
                continue
            seen.add(lot.external_id)
            results.append(lot)
        # пагинация на первой странице после фильтра stop может быть пустой
        if page == 1 and "page=" not in resp.text:
            # всё равно пробуем page=2 если набрали мало
            if len(page_lots) < 4:
                break
    return results
