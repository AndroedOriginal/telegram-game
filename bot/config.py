"""Runtime configuration loaded from environment variables.

No secrets are hardcoded here. Values are read from the process environment,
optionally populated from a local ``.env`` file (see ``.env.example``).
"""
from __future__ import annotations

import os
from dataclasses import dataclass

try:  # pragma: no cover - convenience only, not required for tests.
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass


def _get_int_or_none(name: str) -> int | None:
    value = os.getenv(name)
    if value is None or value == "":
        return None
    return int(value)


@dataclass(frozen=True)
class Config:
    bot_token: str
    chat_id: int | None
    topic_id: int | None
    database_path: str

    @classmethod
    def from_env(cls) -> "Config":
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        return cls(
            bot_token=token,
            chat_id=_get_int_or_none("TELEGRAM_CHAT_ID"),
            topic_id=_get_int_or_none("TELEGRAM_TOPIC_ID"),
            database_path=os.getenv("DATABASE_PATH", "chess_royale.sqlite3"),
        )


config = Config.from_env()
