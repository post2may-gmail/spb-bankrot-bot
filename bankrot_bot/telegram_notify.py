from __future__ import annotations

import logging
from typing import Any

import httpx

from bankrot_bot.models import Lot

logger = logging.getLogger(__name__)


def format_lot_message(lot: Lot) -> str:
    price = (
        f"{lot.price:,.0f} ₽".replace(",", " ")
        if lot.price is not None
        else "цена не указана"
    )
    area = f"{lot.area_sqm:g} м²" if lot.area_sqm is not None else "—"
    lines = [
        "🏘 <b>Новый лот: недвижимость, СПб, банкротство</b>",
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
    if desc:
        short = desc if len(desc) <= 400 else desc[:397] + "…"
        lines.extend(["", _esc(short)])
    lines.extend(["", f'<a href="{_esc(lot.url)}">Открыть лот</a>'])
    return "\n".join(lines)


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

    async def send_lot(self, client: httpx.AsyncClient, lot: Lot) -> str | None:
        if self.dry_run or not self.configured:
            logger.info("dry-run / no telegram: skip publish %s", lot.dedupe_key)
            return None
        payload: dict[str, Any] = {
            "chat_id": self.chat_id,
            "text": format_lot_message(lot),
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        resp = await client.post(url, json=payload, timeout=30.0)
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram API error: {data}")
        message_id = str(data.get("result", {}).get("message_id", ""))
        return message_id or None

    async def send_text(self, client: httpx.AsyncClient, text: str) -> None:
        if self.dry_run or not self.configured:
            return
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        resp = await client.post(
            url,
            json={"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"},
            timeout=30.0,
        )
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram API error: {data}")
