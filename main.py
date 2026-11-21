from __future__ import annotations

import uvicorn

from bankrot_bot.config import get_settings
from bankrot_bot.web.app import create_app

# Top-level FastAPI instance for Cursor publish hosting.
settings = get_settings()
app = create_app(settings)


def main() -> None:
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
