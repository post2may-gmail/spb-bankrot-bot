from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(slots=True)
class Lot:
    source: str
    external_id: str
    title: str
    description: str
    url: str
    price: float | None = None
    address: str = ""
    area_sqm: float | None = None
    region: str = "Санкт-Петербург"
    category: str = "Недвижимость"
    auction_form: str = ""
    published_at: str | None = None
    raw_text: str = ""
    photos: list[str] = field(default_factory=list)
    dedupe_key: str = ""

    def __post_init__(self) -> None:
        if not self.dedupe_key:
            self.dedupe_key = f"{self.source}:{self.external_id}"
        if not self.raw_text:
            self.raw_text = " ".join(
                part
                for part in (self.title, self.description, self.address)
                if part
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ScanStats:
    source: str
    fetched: int = 0
    matched: int = 0
    new: int = 0
    published: int = 0
    skipped_share: int = 0
    skipped_rent: int = 0
    skipped_other: int = 0
    error: str | None = None
    finished_at: str = field(default_factory=utc_now_iso)
