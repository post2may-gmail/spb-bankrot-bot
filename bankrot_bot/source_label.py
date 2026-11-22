from __future__ import annotations

from urllib.parse import urlparse

_FORM_LABELS = {
    "open_auction": "аукцион",
    "auction": "аукцион",
    "public_offer": "публичное предложение",
    "publicoffer": "публичное предложение",
    "public_proposal": "публичное предложение",
    "competition": "конкурс",
    "direct_sale": "прямая продажа",
    "банкротство": "банкротство",
    "открытый аукцион": "аукцион",
    "открытый_аукцион": "аукцион",
}


def auction_form_label(raw: str) -> str:
    """Человекочитаемая форма торгов вместо кодов вроде open_auction."""
    text = (raw or "").strip()
    if not text:
        return ""
    key = text.lower().replace(" ", "_").replace("-", "_")
    if key in _FORM_LABELS:
        return _FORM_LABELS[key]
    low = text.lower()
    if "auction" in key or "аукцион" in low:
        return "аукцион"
    if ("public" in key and "offer" in key) or "публичн" in low and "предложен" in low:
        return "публичное предложение"
    if "публичн" in low and "предложен" in low:
        return "публичное предложение"
    return text


def source_label_from_url(url: str, fallback: str = "") -> str:
    """Подпись источника по реальной ссылке на лот, а не по агрегатору-посреднику."""
    raw = (url or "").strip()
    if not raw:
        return fallback or "торги"

    host = (urlparse(raw).netloc or "").lower().removeprefix("www.")
    path = (urlparse(raw).path or "").lower()
    blob = f"{host}{path}"

    if "fedresurs.ru" in host:
        return "fedresurs.ru"
    if "torgi.gov.ru" in host:
        return "torgi.gov.ru"
    if "tbankrot.ru" in host:
        return "tbankrot.ru"
    if "m-ets.ru" in host or "m-ets.ru" in blob:
        return "m-ets.ru"
    if "lot-online.ru" in host or "lotonline" in host:
        return "lot-online.ru"
    if "cdtrf.ru" in host:
        return "cdtrf.ru"
    if "sberbank" in host or "portal-da.ru" in host:
        return host
    if "torgiopen.ru" in host:
        # Посредник — показываем fallback, если он уже нормальный.
        if fallback and "torgiopen" not in fallback.lower():
            return fallback
        return fallback or "торги"

    return host or fallback or "торги"
