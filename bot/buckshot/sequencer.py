"""Async sequential message sender for Buckshot Roulette.

Dealer commentary and 🔈 status events are each their own Telegram message.
Delays use ``asyncio.sleep`` so other chats/topics keep running.

Callers must hold the per-topic game lock so sequences cannot interleave.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from telegram.constants import ParseMode

from .models import GameState

# One place to tune pacing between sequential event messages.
EVENT_DELAY_SECONDS = 0.8


@dataclass(frozen=True)
class OutgoingMessage:
    text: str
    parse_mode: str | None = ParseMode.HTML


async def send_sequence(
    bot,
    state: GameState,
    messages: list[OutgoingMessage],
    *,
    delay: float | None = None,
    sleep=asyncio.sleep,
) -> list[int]:
    """Send ``messages`` in order with ``delay`` seconds between them.

    Each sent message is tracked on ``state`` for later cleanup.
    """
    if not messages:
        return []
    gap = EVENT_DELAY_SECONDS if delay is None else delay
    ids: list[int] = []
    for index, message in enumerate(messages):
        if index:
            await sleep(gap)
        sent = await bot.send_message(
            chat_id=state.chat_id,
            message_thread_id=state.topic_id,
            text=message.text,
            parse_mode=message.parse_mode,
        )
        if sent is None:
            continue
        ids.append(sent.message_id)
        state.track_message(sent.message_id)
    return ids
