"""Single entry point for all callback queries.

Every callback is parsed, routed to the appropriate handler, and processed
under a per-game asyncio lock so concurrent button presses for the same
game never interleave (section 31/41)."""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from ..callback_data import (
    DRAW,
    LOBBY_JOIN,
    LOBBY_LEAVE,
    LOBBY_START,
    QUIT,
    RULES,
    CallbackParseError,
    DirectionCallback,
    DistanceCallback,
    GameButtonCallback,
    LobbyCallback,
    decode,
)
from . import game as game_handlers
from . import lobby as lobby_handlers

logger = logging.getLogger(__name__)


async def on_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.data is None:
        return

    try:
        callback = decode(query.data)
    except CallbackParseError:
        await query.answer()
        return

    manager = context.bot_data["manager"]
    state = manager.get_by_id(callback.game_id)
    if state is None:
        await query.answer()
        return

    lock = manager.lock_for(state.chat_id, state.topic_id)
    async with lock:
        if isinstance(callback, LobbyCallback):
            if callback.kind == LOBBY_JOIN:
                await lobby_handlers.handle_join(update, context, callback.game_id)
            elif callback.kind == LOBBY_LEAVE:
                await lobby_handlers.handle_leave(update, context, callback.game_id)
            elif callback.kind == LOBBY_START:
                await lobby_handlers.handle_start(update, context, callback.game_id)
            else:  # pragma: no cover - defensive
                await query.answer()
        elif isinstance(callback, GameButtonCallback):
            if callback.kind == RULES:
                await game_handlers.process_rules(update, context, callback)
            elif callback.kind == QUIT:
                await game_handlers.process_quit(update, context, callback)
            elif callback.kind == DRAW:
                await game_handlers.process_draw(update, context, callback)
            else:
                await query.answer()
        elif isinstance(callback, DistanceCallback):
            await game_handlers.process_distance(update, context, callback)
        elif isinstance(callback, DirectionCallback):
            await game_handlers.process_direction(update, context, callback)
        else:  # pragma: no cover - defensive
            await query.answer()
