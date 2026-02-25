"""
Centralized settings loaded from environment variables.

The goal is to keep all tunables in one place so switching from
SQLite to Postgres is only a DATABASE_URL change.
"""
from __future__ import annotations

from typing import Dict, List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly typed settings with defaults and env binding."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Telegram bot token (required)
    bot_token: str = ""

    # Database URL (default to local SQLite for stage 1)
    database_url: str = "sqlite+aiosqlite:///./data.db"

    # Run mode: polling or webhook
    run_mode: str = "polling"

    # Webhook configuration
    webhook_path: str = "/webhook"
    webhook_url: str = ""

    # Admin Telegram IDs (comma-separated)
    admin_ids: str = ""

    # Group chat and per-city topic thread IDs
    group_chat_id: int = 0

    city_topic_moscow: int = 7
    city_topic_spb: int = 11
    city_topic_novosibirsk: int = 4
    city_topic_chelyabinsk: int = 21
    city_topic_ufa: int = 13
    city_topic_kazan: int = 15
    city_topic_omsk: int = 17
    city_topic_krasnoyarsk: int = 19
    city_topic_nizhny_novgorod: int = 23
    city_topic_voronezh: int = 9

    def city_topics(self) -> Dict[str, int]:
        """Return a mapping of city keys to topic thread IDs."""
        return {
            "moscow": self.city_topic_moscow,
            "spb": self.city_topic_spb,
            "novosibirsk": self.city_topic_novosibirsk,
            "chelyabinsk": self.city_topic_chelyabinsk,
            "ufa": self.city_topic_ufa,
            "kazan": self.city_topic_kazan,
            "omsk": self.city_topic_omsk,
            "krasnoyarsk": self.city_topic_krasnoyarsk,
            "nizhny_novgorod": self.city_topic_nizhny_novgorod,
            "voronezh": self.city_topic_voronezh,
        }

    def get_admin_ids(self) -> List[int]:
        """Parse admin ids from comma-separated string."""
        raw = self.admin_ids.strip()
        if not raw:
            return []
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        out: List[int] = []
        for p in parts:
            try:
                out.append(int(p))
            except ValueError:
                continue
        return out


settings = Settings()
