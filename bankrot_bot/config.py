from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "lots.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(default="", alias="TELEGRAM_CHAT_ID")
    port: int = Field(default=8765, alias="PORT")
    scan_interval_sec: int = Field(default=300, alias="SCAN_INTERVAL_SEC")
    max_pages_per_source: int = Field(default=3, alias="MAX_PAGES_PER_SOURCE")
    dry_run: bool = Field(default=False, alias="DRY_RUN")
    host: str = Field(default="0.0.0.0", alias="HOST")

    @property
    def telegram_configured(self) -> bool:
        return bool(self.telegram_bot_token.strip() and self.telegram_chat_id.strip())


def get_settings() -> Settings:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return Settings()
