from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from bankrot_bot.config import DB_PATH, DATA_DIR
from bankrot_bot.models import Lot, utc_now_iso


SCHEMA = """
CREATE TABLE IF NOT EXISTS lots (
    dedupe_key TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL,
    price REAL,
    address TEXT NOT NULL DEFAULT '',
    area_sqm REAL,
    region TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    auction_form TEXT NOT NULL DEFAULT '',
    published_at TEXT,
    photos_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'new',
    telegram_message_id TEXT,
    first_seen_at TEXT NOT NULL,
    published_to_tg_at TEXT,
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS scan_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    stats_json TEXT NOT NULL DEFAULT '[]',
    new_count INTEGER NOT NULL DEFAULT 0,
    published_count INTEGER NOT NULL DEFAULT 0,
    error TEXT
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: Path | None = None) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.path = path or DB_PATH
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init(self) -> None:
        with self.connection() as conn:
            conn.executescript(SCHEMA)

    def get_meta(self, key: str, default: str | None = None) -> str | None:
        with self.connection() as conn:
            row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else default

    def set_meta(self, key: str, value: str) -> None:
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO meta(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def upsert_lot(self, lot: Lot) -> bool:
        """Вставляет лот, если новый. True = новый."""
        now = utc_now_iso()
        with self.connection() as conn:
            existing = conn.execute(
                "SELECT dedupe_key FROM lots WHERE dedupe_key = ?",
                (lot.dedupe_key,),
            ).fetchone()
            if existing:
                return False
            # Кросс-источниковый дубль: тот же объект с другой площадки.
            twin = conn.execute(
                """
                SELECT dedupe_key FROM lots
                WHERE lower(title) = lower(?)
                   OR (
                        address != '' AND ? != ''
                        AND lower(address) = lower(?)
                        AND ifnull(price, -1) = ifnull(?, -1)
                   )
                LIMIT 1
                """,
                (lot.title, lot.address, lot.address, lot.price),
            ).fetchone()
            if twin:
                return False
            conn.execute(
                """
                INSERT INTO lots (
                    dedupe_key, source, external_id, title, description, url,
                    price, address, area_sqm, region, category, auction_form,
                    published_at, photos_json, status, first_seen_at, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?, ?)
                """,
                (
                    lot.dedupe_key,
                    lot.source,
                    lot.external_id,
                    lot.title,
                    lot.description,
                    lot.url,
                    lot.price,
                    lot.address,
                    lot.area_sqm,
                    lot.region,
                    lot.category,
                    lot.auction_form,
                    lot.published_at,
                    json.dumps(lot.photos, ensure_ascii=False),
                    now,
                    json.dumps(lot.to_dict(), ensure_ascii=False),
                ),
            )
            return True

    def mark_published(self, dedupe_key: str, message_id: str | None = None) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                UPDATE lots
                SET status = 'published',
                    published_to_tg_at = ?,
                    telegram_message_id = COALESCE(?, telegram_message_id)
                WHERE dedupe_key = ?
                """,
                (utc_now_iso(), message_id, dedupe_key),
            )

    def mark_skipped(self, dedupe_key: str, reason: str = "skipped") -> None:
        with self.connection() as conn:
            conn.execute(
                "UPDATE lots SET status = ? WHERE dedupe_key = ?",
                (reason, dedupe_key),
            )

    def list_lots(
        self,
        *,
        limit: int = 50,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM lots"
        params: list[Any] = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY first_seen_at DESC LIMIT ?"
        params.append(limit)
        with self.connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def counts(self) -> dict[str, int]:
        with self.connection() as conn:
            total = conn.execute("SELECT COUNT(*) AS c FROM lots").fetchone()["c"]
            published = conn.execute(
                "SELECT COUNT(*) AS c FROM lots WHERE status = 'published'"
            ).fetchone()["c"]
            pending = conn.execute(
                "SELECT COUNT(*) AS c FROM lots WHERE status = 'new'"
            ).fetchone()["c"]
            return {"total": total, "published": published, "pending": pending}

    def save_scan_run(
        self,
        *,
        started_at: str,
        finished_at: str,
        stats: list[dict[str, Any]],
        new_count: int,
        published_count: int,
        error: str | None = None,
    ) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO scan_runs (
                    started_at, finished_at, stats_json, new_count, published_count, error
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    started_at,
                    finished_at,
                    json.dumps(stats, ensure_ascii=False),
                    new_count,
                    published_count,
                    error,
                ),
            )

    def latest_scan(self) -> dict[str, Any] | None:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM scan_runs ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if not row:
                return None
            data = dict(row)
            data["stats"] = json.loads(data.pop("stats_json") or "[]")
            return data

    def pending_for_publish(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM lots
                WHERE status = 'new'
                ORDER BY first_seen_at ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]
