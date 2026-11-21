from __future__ import annotations

import logging
import re
from urllib.parse import unquote

import httpx

logger = logging.getLogger(__name__)

SKIP_URL_RE = re.compile(
    r"(?i)("
    r"blur|logo|favicon|icon|sprite|avatar|placeholder|"
    r"акт|akt[_-]?|приемк|приёмк|document|\.pdf($|\?)|"
    r"%d0%b0%d0%ba%d1%82"  # «акт» url-encoded
    r")"
)


def normalize_photo_urls(urls: list[str] | None, *, limit: int = 10) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in urls or []:
        if not isinstance(raw, str):
            continue
        url = raw.strip()
        if not url.startswith(("http://", "https://")):
            continue
        decoded = unquote(url)
        if SKIP_URL_RE.search(url) or SKIP_URL_RE.search(decoded):
            continue
        if url in seen:
            continue
        seen.add(url)
        out.append(url)
        if len(out) >= limit:
            break
    return out


async def enrich_photos_from_torgiopen(
    client: httpx.AsyncClient,
    *,
    query: str,
    limit: int = 10,
) -> list[str]:
    """Подтягивает фото похожего лота из открытого зеркала (если у агрегатора фото закрыты)."""
    q = (query or "").strip()
    if len(q) < 8:
        return []
    # Короткий поисковый хвост — иначе API хуже матчит.
    q = re.sub(r"\s+", " ", q)[:80]
    try:
        resp = await client.get(
            "https://torgiopen.ru/api/lots",
            params={
                "region": "78",
                "category": "real_estate",
                "channel": "bankruptcy",
                "q": q,
                "pageSize": 5,
                "page": 1,
            },
            timeout=20.0,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.debug("photo enrich failed for %r: %s", q, exc)
        return []
    for item in data.get("items") or []:
        photos = normalize_photo_urls(item.get("photos") or [], limit=limit)
        if photos:
            return photos
    return []
