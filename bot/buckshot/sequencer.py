"""Async sequential UI updates for Buckshot Roulette.

Persistent slots (info / commentary / status / actions) are EDITED in
order. Delays use ``asyncio.sleep`` so other chats keep running.

Callers must hold the per-topic game lock so sequences cannot interleave.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from telegram.constants import ParseMode

from .models import GameState

# One place to tune pacing between sequential slot edits.
EVENT_DELAY_SECONDS = 0.8

SLOT_INFO = "info"
SLOT_COMMENTARY = "commentary"
SLOT_ACTIONS = "actions"
SLOT_STATUS = "status"


@dataclass(frozen=True)
class UiUpdate:
    slot: str
    text: str
    parse_mode: str | None = ParseMode.HTML
    markup: object | None = None


def slot_message_id(state: GameState, slot: str) -> int | None:
    """Return this game's message id for ``slot``. Never reads another game."""

    if slot == SLOT_INFO:
        return state.info_message_id
    if slot == SLOT_COMMENTARY:
        return state.commentary_message_id
    if slot == SLOT_ACTIONS:
        return state.actions_message_id
    if slot == SLOT_STATUS:
        return state.status_message_id or state.announce_message_id
    raise ValueError(f"unknown slot {slot}")


def set_slot_message_id(state: GameState, slot: str, message_id: int | None) -> None:
    if slot == SLOT_INFO:
        state.info_message_id = message_id
    elif slot == SLOT_COMMENTARY:
        state.commentary_message_id = message_id
    elif slot == SLOT_ACTIONS:
        state.actions_message_id = message_id
    elif slot == SLOT_STATUS:
        state.status_message_id = message_id
        state.announce_message_id = message_id
    else:
        raise ValueError(f"unknown slot {slot}")
    state.track_message(message_id)


async def apply_sequence(
    updates: list[UiUpdate],
    *,
    delay: float | None = None,
    sleep=asyncio.sleep,
    apply,
) -> None:
    """Apply ``updates`` in order with ``delay`` seconds between them.

    ``apply`` is an async callback ``apply(update: UiUpdate) -> None``.
    It must edit the caller's own game-state message ids.
    """
    if not updates:
        return
    gap = EVENT_DELAY_SECONDS if delay is None else delay
    for index, update in enumerate(updates):
        if index:
            await sleep(gap)
        await apply(update)
