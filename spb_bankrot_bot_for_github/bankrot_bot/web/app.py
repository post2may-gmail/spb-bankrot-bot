from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from bankrot_bot.config import Settings, get_settings
from bankrot_bot.db import Database
from bankrot_bot.scanner import Scanner
from bankrot_bot.telegram_notify import TelegramNotifier

logger = logging.getLogger(__name__)
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
STATIC_DIR = Path(__file__).parent / "static"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    db = Database()
    notifier = TelegramNotifier(
        settings.telegram_bot_token,
        settings.telegram_chat_id,
        dry_run=settings.dry_run,
    )
    scanner = Scanner(
        db,
        notifier,
        max_pages=settings.max_pages_per_source,
        use_sample_fallback=True,
    )
    state: dict[str, Any] = {
        "settings": settings,
        "db": db,
        "scanner": scanner,
        "notifier": notifier,
        "task": None,
    }

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )

        async def loop() -> None:
            # Сразу после старта панели, не блокируя HTTP.
            try:
                await scanner.run_once()
            except Exception:  # noqa: BLE001
                logger.exception("initial scan failed")
            while True:
                await asyncio.sleep(max(60, settings.scan_interval_sec))
                try:
                    await scanner.run_once()
                except Exception:  # noqa: BLE001
                    logger.exception("background scan failed")

        state["task"] = asyncio.create_task(loop())
        yield
        task = state.get("task")
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    app = FastAPI(title="SPB Bankrot Lots Bot", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    def _dashboard_context(request: Request) -> dict[str, Any]:
        counts = db.counts()
        lots = db.list_lots(limit=40)
        latest = db.latest_scan()
        return {
            "request": request,
            "counts": counts,
            "lots": lots,
            "latest": latest,
            "telegram_ok": notifier.configured,
            "dry_run": settings.dry_run,
            "interval": settings.scan_interval_sec,
            "filters": [
                "Недвижимость",
                "Санкт-Петербург",
                "Продажа",
                "Банкротство",
                "Без долевой собственности",
            ],
            "sources": ["tbankrot.ru", "ГИС «Торги» / открытые данные"],
        }

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        ctx = _dashboard_context(request)
        return TEMPLATES.TemplateResponse(
            request=request,
            name="index.html",
            context=ctx,
        )

    @app.get("/api/status")
    async def api_status() -> JSONResponse:
        return JSONResponse(
            {
                "telegram_configured": notifier.configured,
                "dry_run": settings.dry_run,
                "counts": db.counts(),
                "last_scan": db.latest_scan(),
                "scan_interval_sec": settings.scan_interval_sec,
            }
        )

    @app.get("/api/lots")
    async def api_lots(limit: int = 50, status: str | None = None) -> JSONResponse:
        return JSONResponse({"items": db.list_lots(limit=min(limit, 200), status=status)})

    @app.post("/api/scan")
    async def api_scan() -> JSONResponse:
        result = await scanner.run_once()
        return JSONResponse(result)

    return app
