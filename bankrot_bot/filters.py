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

# Только квартиры / жилые помещения (как на торгах).
APARTMENT_RE = re.compile(
    r"(?i)(?<![а-яёa-z])("
    r"квартир[аыуеой]|"
    r"жилое\s+помещен\w*"
    r")(?![а-яёa-z])"
)

# Явно не квартира, даже если где-то мелькнуло слово.
NOT_APARTMENT_RE = re.compile(
    r"(?i)("
    r"машино[-\s]?мест|парков\w*\s+мест|гараж|"
    r"земельн|участ\w*\s+\d|"
    r"нежил(?:ое|ого|ому)\s+помещен|"
    r"картин[аыуе]|живопис|автомобил|дебиторск|"
    r"уставн\w+\s+капитал|продажа\s+(?:ооо|ао|зао|пао)"
    r")"
)


def has_shared_ownership(text: str) -> bool:
    return bool(SHARE_RE.search(text or ""))


def is_rent(text: str) -> bool:
    return bool(RENT_RE.search(text or ""))


def looks_like_spb(text: str) -> bool:
    return bool(SPB_RE.search(text or ""))


def is_apartment(text: str) -> bool:
    t = text or ""
    if NOT_APARTMENT_RE.search(t) and not APARTMENT_RE.search(t):
        return False
    # Если есть и квартира, и «нежилое» — смотрим, что ближе к смыслу лота:
    # достаточно явного «квартира» / «жилое помещение».
    return bool(APARTMENT_RE.search(t))


def passes_lot_filters(lot: Lot) -> tuple[bool, str]:
    """Проверяет лот после выборки источника. Возвращает (ok, reason)."""
    blob = " ".join(
        part
        for part in (lot.title, lot.description, lot.address, lot.raw_text, lot.category)
        if part
    )
    if not is_apartment(blob):
        return False, "not_apartment"
    if has_shared_ownership(blob):
        return False, "share"
    if is_rent(blob):
        return False, "rent"
    if lot.region and "петербург" not in lot.region.lower() and "спб" not in lot.region.lower():
        if not looks_like_spb(blob):
            return False, "region"
    return True, "ok"
