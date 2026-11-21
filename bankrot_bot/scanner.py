from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

import httpx

from bankrot_bot.db import Database
from bankrot_bot.filters import passes_lot_filters
from bankrot_bot.http_client import make_client
from bankrot_bot.models import Lot, ScanStats, utc_now_iso
from bankrot_bot.photos import enrich_photos_from_torgiopen, normalize_photo_urls
from bankrot_bot.sources.tbankrot import fetch_tbankrot_lots
from bankrot_bot.sources.torgi import fetch_torgi_lots
from bankrot_bot.telegram_notify import TelegramNotifier

logger = logging.getLogger(__name__)


SAMPLE_LOTS: list[Lot] = [
    Lot(
        source="sample",
        external_id="demo-1",
        title="Квартира 45.4 м², Санкт-Петербург, Красное Село",
        description=(
            "Квартира площадью 45,4 кв.м., кадастровый № 78:40:0901301:1277. "
            "Адрес: Санкт-Петербург, г. Красное Село, ул. Спирина, д.14. "
            "Торги по банкротству, продажа целиком."
        ),
        url="https://tbankrot.ru/item?id=8232068",
        price=3_250_000,
        address="Санкт-Петербург, г. Красное Село, ул. Спирина, д.14",
        area_sqm=45.4,
        auction_form="публичное предложение",
    ),
    Lot(
        source="sample",
        external_id="demo-2",
        title="Парковочное место 13.78 м², Санкт-Петербург",
        description=(
            "Парковочное место на -1 этаже паркинга, площадь 13.78 кв.м. "
            "Адрес: г. Санкт-Петербург, Кондратьевский проспект."
        ),
        url="https://tbankrot.ru/item?id=8232071",
        price=1_700_000,
        address="г. Санкт-Петербург, Кондратьевский проспект",
        area_sqm=13.78,
        auction_form="открытый аукцион",
    ),
]


class Scanner:
    def __init__(
        self,
        db: Database,
        notifier: TelegramNotifier,
        *,
        max_pages: int = 3,
        use_sample_fallback: bool = True,
    ) -> None:
        self.db = db
        self.notifier = notifier
        self.max_pages = max_pages
        self.use_sample_fallback = use_sample_fallback
        self.last_stats: list[dict[str, Any]] = []
        self.running = False

    async def run_once(self) -> dict[str, Any]:
        if self.running:
            return {"ok": False, "error": "scan already running"}
        self.running = True
        started = utc_now_iso()
        stats: list[ScanStats] = []
        new_count = 0
        published_count = 0
        error: str | None = None
        try:
            purged = self._purge_non_matching()
            if purged:
                logger.info("purged %s lots that are not realty / fail filters", purged)
            async with make_client() as client:
                for name, fetcher in (
                    ("tbankrot", fetch_tbankrot_lots),
                    ("torgi", fetch_torgi_lots),
                ):
                    st = ScanStats(source=name)
                    try:
                        lots = await fetcher(client, max_pages=self.max_pages)
                        st.fetched = len(lots)
                        st.matched = sum(1 for lot in lots if passes_lot_filters(lot)[0])
                        n_new, n_pub, skipped = await self._ingest(client, lots)
                        st.new = n_new
                        st.published = n_pub
                        st.skipped_share = skipped["share"]
                        st.skipped_rent = skipped["rent"]
                        st.skipped_other = (
                            skipped["other"]
                            + skipped.get("not_realty", 0)
                            + skipped.get("not_apartment", 0)
                        )
                        new_count += n_new
                        published_count += n_pub
                    except Exception as exc:  # noqa: BLE001
                        logger.exception("source %s failed", name)
                        st.error = str(exc)
                    stats.append(st)

                if new_count == 0 and self.use_sample_fallback:
                    existing = self.db.counts()["total"]
                    if existing == 0:
                        logger.info("seeding sample lots for empty database")
                        n_new, n_pub, _ = await self._ingest(client, SAMPLE_LOTS)
                        new_count += n_new
                        published_count += n_pub
                        stats.append(
                            ScanStats(
                                source="sample",
                                fetched=len(SAMPLE_LOTS),
                                matched=len(SAMPLE_LOTS),
                                new=n_new,
                                published=n_pub,
                            )
                        )
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
            logger.exception("scan failed")
        finally:
            self.running = False

        finished = utc_now_iso()
        payload = [asdict(s) for s in stats]
        self.last_stats = payload
        self.db.save_scan_run(
            started_at=started,
            finished_at=finished,
            stats=payload,
            new_count=new_count,
            published_count=published_count,
            error=error,
        )
        self.db.set_meta("last_scan_at", finished)
        return {
            "ok": error is None,
            "started_at": started,
            "finished_at": finished,
            "new_count": new_count,
            "published_count": published_count,
            "stats": payload,
            "error": error,
        }

    def _purge_non_matching(self) -> int:
        """Убирает из выдачи старые лоты, которые больше не проходят фильтр."""
        removed = 0
        # Без include_hidden — совместимо со старым db.py на хостинге.
        for row in self.db.list_lots(limit=5000):
            lot = Lot(
                source=row.get("source") or "",
                external_id=row.get("external_id") or "",
                title=row.get("title") or "",
                description=row.get("description") or "",
                url=row.get("url") or "",
                price=row.get("price"),
                address=row.get("address") or "",
                area_sqm=row.get("area_sqm"),
                region=row.get("region") or "",
                category=row.get("category") or "",
                auction_form=row.get("auction_form") or "",
                published_at=row.get("published_at"),
                dedupe_key=row.get("dedupe_key") or "",
            )
            ok, reason = passes_lot_filters(lot)
            if ok:
                continue
            key = lot.dedupe_key
            if hasattr(self.db, "delete_lot"):
                self.db.delete_lot(key)
            else:
                with self.db.connection() as conn:
                    conn.execute("DELETE FROM lots WHERE dedupe_key = ?", (key,))
            removed += 1
            logger.info("removed lot %s (%s)", key, reason)
        return removed

    async def _ensure_photos(self, client: httpx.AsyncClient, lot: Lot) -> Lot:
        photos = normalize_photo_urls(lot.photos, limit=10)
        if photos:
            lot.photos = photos
            return lot
        query = " ".join(
            part for part in (lot.title, lot.address) if part
        ).strip()
        enriched = await enrich_photos_from_torgiopen(client, query=query, limit=10)
        if enriched:
            lot.photos = enriched
            logger.info("enriched %s photos for %s", len(enriched), lot.dedupe_key)
        return lot

    async def _ingest(
        self,
        client: httpx.AsyncClient,
        lots: list[Lot],
    ) -> tuple[int, int, dict[str, int]]:
        skipped = {
            "share": 0,
            "rent": 0,
            "not_realty": 0,
            "not_apartment": 0,
            "other": 0,
        }
        new_count = 0
        published_count = 0
        for lot in lots:
            ok, reason = passes_lot_filters(lot)
            if not ok:
                skipped[reason if reason in skipped else "other"] += 1
                continue
            lot = await self._ensure_photos(client, lot)
            is_new = self.db.upsert_lot(lot)
            if not is_new:
                continue
            new_count += 1
            try:
                msg_id = await self.notifier.send_lot(client, lot)
                if self.notifier.configured and not self.notifier.dry_run:
                    self.db.mark_published(lot.dedupe_key, msg_id)
                    published_count += 1
                elif self.notifier.dry_run:
                    self.db.mark_published(lot.dedupe_key, "dry-run")
                    published_count += 1
                else:
                    # без токена оставляем в pending — панель покажет
                    pass
            except Exception as exc:  # noqa: BLE001
                logger.warning("publish failed for %s: %s", lot.dedupe_key, exc)
        return new_count, published_count, skipped
