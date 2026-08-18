"""Small helpers around Telegram API calls that hit flood limits."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from telegram.error import BadRequest, RetryAfter, TimedOut

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def telegram_retry(action: Callable[[], Awaitable[T]], attempts: int = 4) -> T | None:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return await action()
        except RetryAfter as exc:
            wait = int(getattr(exc, "retry_after", 1)) + 1
            logger.warning("Flood control: sleeping %ss (attempt %s)", wait, attempt + 1)
            await asyncio.sleep(wait)
            last_error = exc
        except TimedOut as exc:
            await asyncio.sleep(1)
            last_error = exc
        except BadRequest as exc:
            if "message is not modified" in str(exc).lower():
                return None
            raise
    if last_error is not None:
        logger.warning("Telegram call failed after retries: %s", last_error)
    return None
