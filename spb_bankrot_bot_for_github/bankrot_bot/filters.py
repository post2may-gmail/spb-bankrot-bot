from __future__ import annotations

import re

from bankrot_bot.models import Lot

# Долевая собственность: слова из ТЗ + типичные формы прилагательного.
SHARE_RE = re.compile(
    r"(?i)(?<![а-яёa-z])("
    r"доля|доли|долей|"
    r"долев(?:ой|ая|ое|ые|ого|ому|ым|ом|ую|ыми|ых)"
    r")(?![а-яёa-z])"
)

# Аренда / найм — не продажа.
RENT_RE = re.compile(
    r"(?i)(?<![а-яёa-z])("
    r"аренда|аренды|аренду|аренде|арендой|арендовать|"
    r"найм|наём|найма|сдач[аиеу]|сдан[оаы]?"
    r")(?![а-яёa-z])"
)

SPB_RE = re.compile(
    r"(?i)(санкт[-\s]?петербург|г\.?\s*спб|спб|петербург)"
)


def has_shared_ownership(text: str) -> bool:
    return bool(SHARE_RE.search(text or ""))


def is_rent(text: str) -> bool:
    return bool(RENT_RE.search(text or ""))


def looks_like_spb(text: str) -> bool:
    return bool(SPB_RE.search(text or ""))


def passes_lot_filters(lot: Lot) -> tuple[bool, str]:
    """Проверяет лот после выборки источника. Возвращает (ok, reason)."""
    blob = " ".join(
        part
        for part in (lot.title, lot.description, lot.address, lot.raw_text)
        if part
    )
    if has_shared_ownership(blob):
        return False, "share"
    if is_rent(blob):
        return False, "rent"
    if lot.region and "петербург" not in lot.region.lower() and "спб" not in lot.region.lower():
        if not looks_like_spb(blob):
            return False, "region"
    return True, "ok"
