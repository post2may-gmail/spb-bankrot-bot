from __future__ import annotations

import logging
from typing import Any

import httpx

from bankrot_bot.models import Lot
from bankrot_bot.photos import normalize_photo_urls

logger = logging.getLogger(__name__)

# У Telegram caption у media group — до 1024 символов.
CAPTION_LIMIT = 1000


def format_lot_message(lot: Lot, *, short: bool = False) -> str:
    price = (
        f"{lot.price:,.0f} ₽".replace(",", " ")
        if lot.price is not None
        else "цена не указана"
    )
    area = f"{lot.area_sqm:g} м²" if lot.area_sqm is not None else "—"
    lines = [
        "🏘 <b>Квартира / жилое помещение — СПб, банкротство</b>",
        "",
        f"<b>{_esc(lot.title)}</b>",
        f"💰 {price}",
        f"📐 Площадь: {area}",
    ]
    if lot.address:
        lines.append(f"📍 {_esc(lot.address)}")
    if lot.auction_form:
        lines.append(f"🏛 Форма: {_esc(lot.auction_form)}")
    lines.append(f"Источник: {_esc(lot.source)}")
    desc = (lot.description or "").strip()
    max_desc = 180 if short else 400
    if desc:
        short_desc = desc if len(desc) <= max_desc else desc[: max_desc - 1] + "…"
        lines.extend(["", _esc(short_desc)])
    lines.extend(["", f'<a href="{_esc(lot.url)}">Открыть лот</a>'])
    text = "\n".join(lines)
    if short and len(text) > CAPTION_LIMIT:
        text = text[: CAPTION_LIMIT - 1] + "…"
    return text


def _esc(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str, *, dry_run: bool = False) -> None:
        self.token = token.strip()
        self.chat_id = chat_id.strip()
        self.dry_run = dry_run

    @property
    def configured(self) -> bool:
        return bool(self.token and self.chat_id)

    def _api(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self.token}/{method}"

    async def send_lot(self, client: httpx.AsyncClient, lot: Lot) -> str | None:
        if self.dry_run or not self.configured:
            logger.info("dry-run / no telegram: skip publish %s", lot.dedupe_key)
            return None

        photos = normalize_photo_urls(lot.photos, limit=10)
        if photos:
            try:
                return await self._send_media_group(client, lot, photos)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "media group failed for %s (%s), fallback to text: %s",
                    lot.dedupe_key,
                    len(photos),
                    exc,
                )

        return await self._send_text(client, format_lot_message(lot))

    async def _send_text(self, client: httpx.AsyncClient, text: str) -> str | None:
        resp = await client.post(
            self._api("sendMessage"),
            json={
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
            timeout=30.0,
        )
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram API error: {data}")
        return str(data.get("result", {}).get("message_id", "") or "") or None

    async def _send_media_group(
        self,
        client: httpx.AsyncClient,
        lot: Lot,
        photos: list[str],
    ) -> str | None:
        caption = format_lot_message(lot, short=True)
        media: list[dict[str, Any]] = []
        for i, photo_url in enumerate(photos):
            item: dict[str, Any] = {"type": "photo", "media": photo_url}
            if i == 0:
                item["caption"] = caption
                item["parse_mode"] = "HTML"
            media.append(item)

        resp = await client.post(
            self._api("sendMediaGroup"),
            json={"chat_id": self.chat_id, "media": media},
            timeout=60.0,
        )
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram sendMediaGroup error: {data}")
        results = data.get("result") or []
        if not results:
            return None
        # media group returns a list of messages
        first = results[0] if isinstance(results, list) else results
        return str(first.get("message_id", "") or "") or None

    async def send_text(self, client: httpx.AsyncClient, text: str) -> None:
        if self.dry_run or not self.configured:
            return
        await self._send_text(client, text)
