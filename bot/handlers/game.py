"""Rendering/sending of the persistent game UI and movement callbacks."""
from __future__ import annotations

import asyncio
import logging

from telegram import Bot, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from ..callback_data import DirectionCallback, DistanceCallback, GameButtonCallback
from ..game import engine
from ..game.models import GameState, GameStatus
from ..rendering.board_renderer import render_board
from ..rendering.messages import (
    RULES_ALERT,
    distance_prompt_text,
    info_message_text,
    moves_prompt_text,
)
from .keyboards import direction_keyboard, distance_keyboard, info_keyboard
from .telegram_safe import telegram_retry

logger = logging.getLogger(__name__)

INVALID_MOVE_TEXT = "ход невозможен."


def _track(state: GameState, message) -> None:
    if message is not None:
        state.track_message(message.message_id)


async def delete_game_messages(bot: Bot, state: GameState) -> None:
    ids = state.ui_message_ids()
    if not ids:
        return
    try:
        await bot.delete_messages(chat_id=state.chat_id, message_ids=ids)
    except Exception:
        for message_id in ids:
            try:
                await bot.delete_message(chat_id=state.chat_id, message_id=message_id)
            except Exception:
                pass
    state.tracked_message_ids = []
    state.info_message_id = None
    state.board_message_id = None
    state.rules_message_id = None
    state.lobby_message_id = None
    state.start_message_id = None
    state.distance_message_id = None
    state.announce_message_id = None
    state.moves_message_id = None


async def upsert_announcement(bot: Bot, state: GameState, text: str) -> None:
    """Keep a single 🔈 line by editing the existing slot."""

    engine._set_status(state, text)
    if state.status == GameStatus.ACTIVE and state.info_message_id is not None:
        await update_info_message(bot, state)
        return

    if state.announce_message_id is not None:
        try:
            await telegram_retry(
                lambda: bot.edit_message_text(
                    chat_id=state.chat_id,
                    message_id=state.announce_message_id,
                    text=text,
                )
            )
            return
        except BadRequest as exc:
            logger.warning("Could not edit announcement: %s", exc)
            state.announce_message_id = None

    msg = await bot.send_message(
        chat_id=state.chat_id,
        message_thread_id=state.topic_id,
        text=text,
    )
    state.announce_message_id = msg.message_id
    state.track_message(msg.message_id)


async def update_info_message(bot: Bot, state: GameState) -> None:
    markup = (
        info_keyboard(state.game_id, state.move_seq)
        if state.status == GameStatus.ACTIVE
        else None
    )
    html = info_message_text(state)
    if state.info_message_id is not None:
        try:
            await telegram_retry(
                lambda: bot.edit_message_text(
                    chat_id=state.chat_id,
                    message_id=state.info_message_id,
                    text=html,
                    parse_mode=ParseMode.HTML,
                    reply_markup=markup,
                )
            )
            return
        except BadRequest as exc:
            logger.warning("Could not edit info: %s", exc)
            state.info_message_id = None

    msg = await telegram_retry(
        lambda: bot.send_message(
            chat_id=state.chat_id,
            message_thread_id=state.topic_id,
            text=html,
            parse_mode=ParseMode.HTML,
            reply_markup=markup,
        )
    )
    if msg is not None:
        state.info_message_id = msg.message_id
        _track(state, msg)


async def update_board_message(bot: Bot, state: GameState) -> None:
    html = render_board(state)
    if state.board_message_id is not None:
        try:
            await telegram_retry(
                lambda: bot.edit_message_text(
                    chat_id=state.chat_id,
                    message_id=state.board_message_id,
                    text=html,
                    parse_mode=ParseMode.HTML,
                )
            )
            return
        except BadRequest as exc:
            logger.warning("Could not edit board: %s", exc)
            state.board_message_id = None

    msg = await telegram_retry(
        lambda: bot.send_message(
            chat_id=state.chat_id,
            message_thread_id=state.topic_id,
            text=html,
            parse_mode=ParseMode.HTML,
        )
    )
    if msg is not None:
        state.board_message_id = msg.message_id
        _track(state, msg)


async def update_moves_message(bot: Bot, state: GameState) -> None:
    markup = (
        direction_keyboard(state.game_id, state.move_seq)
        if state.status == GameStatus.ACTIVE
        else None
    )
    if state.moves_message_id is not None:
        try:
            await telegram_retry(
                lambda: bot.edit_message_text(
                    chat_id=state.chat_id,
                    message_id=state.moves_message_id,
                    text=moves_prompt_text(),
                    reply_markup=markup,
                )
            )
            return
        except BadRequest:
            try:
                await telegram_retry(
                    lambda: bot.edit_message_reply_markup(
                        chat_id=state.chat_id,
                        message_id=state.moves_message_id,
                        reply_markup=markup,
                    )
                )
                return
            except BadRequest:
                state.moves_message_id = None

    msg = await telegram_retry(
        lambda: bot.send_message(
            chat_id=state.chat_id,
            message_thread_id=state.topic_id,
            text=moves_prompt_text(),
            reply_markup=markup,
        )
    )
    if msg is not None:
        state.moves_message_id = msg.message_id
        _track(state, msg)


async def send_game_start_messages(bot: Bot, state: GameState) -> None:
    current = state.current_player()
    if current is None:
        raise RuntimeError("Cannot render game UI without a current player")
    if not state.status_line:
        from ..game.rules import turn_announcement

        state.status_line = turn_announcement(current)

    await update_info_message(bot, state)
    await update_board_message(bot, state)
    await update_moves_message(bot, state)


async def update_game_messages(bot: Bot, state: GameState) -> None:
    await update_info_message(bot, state)
    await update_board_message(bot, state)
    await update_moves_message(bot, state)


async def send_distance_prompt(bot: Bot, state: GameState, callback: DirectionCallback, max_distance: int) -> None:
    msg = await bot.send_message(
        chat_id=state.chat_id,
        message_thread_id=state.topic_id,
        text=distance_prompt_text(),
        reply_markup=distance_keyboard(state.game_id, state.move_seq, callback.direction, max_distance),
    )
    state.distance_message_id = msg.message_id
    _track(state, msg)


async def delete_distance_prompt(bot: Bot, state: GameState) -> None:
    if state.distance_message_id is not None:
        try:
            await bot.delete_message(chat_id=state.chat_id, message_id=state.distance_message_id)
        except Exception:
            pass
        if state.distance_message_id in state.tracked_message_ids:
            state.tracked_message_ids.remove(state.distance_message_id)
        state.distance_message_id = None


async def send_invalid_move(bot: Bot, state: GameState) -> None:
    engine._set_status(state, INVALID_MOVE_TEXT)
    await update_info_message(bot, state)


async def restart_to_lobby(context: ContextTypes.DEFAULT_TYPE, state: GameState) -> None:
    from . import lobby as lobby_handlers

    await delete_game_messages(context.bot, state)
    manager = context.bot_data["manager"]
    new_state = manager.create(state.chat_id, state.topic_id)
    await lobby_handlers.send_lobby_messages(context, new_state)
    manager.save(new_state)


async def _finalize(context: ContextTypes.DEFAULT_TYPE, state: GameState, result) -> None:
    await delete_distance_prompt(context.bot, state)
    await update_game_messages(context.bot, state)
    context.bot_data["manager"].save(state)
    if result.draw or result.victory:
        await asyncio.sleep(2)
        await restart_to_lobby(context, state)


async def process_direction(update: Update, context: ContextTypes.DEFAULT_TYPE, callback: DirectionCallback) -> None:
    query = update.callback_query
    manager = context.bot_data["manager"]
    state = manager.get_by_id(callback.game_id)
    if state is None:
        await query.answer()
        return

    user_id = query.from_user.id
    result = engine.select_direction(state, user_id, callback.direction, callback.move_seq)

    if not result.ok:
        await query.answer()
        if result.invalid:
            await send_invalid_move(context.bot, state)
            manager.save(state)
        return

    await query.answer()

    if result.pending_distances is not None:
        await send_distance_prompt(context.bot, state, callback, len(result.pending_distances))
        manager.save(state)
        return

    await _finalize(context, state, result)


async def disable_board_buttons(bot: Bot, state: GameState) -> None:
    await update_moves_message(bot, state)


async def process_rules(update: Update, context: ContextTypes.DEFAULT_TYPE, callback: GameButtonCallback) -> None:
    query = update.callback_query
    manager = context.bot_data["manager"]
    state = manager.get_by_id(callback.game_id)
    if state is None:
        await query.answer()
        return
    result = engine.view_rules(state, query.from_user.id)
    if not result.ok:
        await query.answer()
        return
    await query.answer(text=RULES_ALERT[:200], show_alert=True)
    await update_info_message(context.bot, state)
    manager.save(state)


async def process_quit(update: Update, context: ContextTypes.DEFAULT_TYPE, callback: GameButtonCallback) -> None:
    query = update.callback_query
    manager = context.bot_data["manager"]
    state = manager.get_by_id(callback.game_id)
    if state is None:
        await query.answer()
        return
    result = engine.leave_game(state, query.from_user.id)
    await query.answer()
    if not result.ok:
        return
    await _finalize(context, state, result)


async def process_draw(update: Update, context: ContextTypes.DEFAULT_TYPE, callback: GameButtonCallback) -> None:
    query = update.callback_query
    manager = context.bot_data["manager"]
    state = manager.get_by_id(callback.game_id)
    if state is None:
        await query.answer()
        return
    result = engine.vote_draw(state, query.from_user.id)
    await query.answer()
    if not result.ok:
        return
    await _finalize(context, state, result)


async def cmd_leave_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    message = update.effective_message
    if chat is None or message is None or update.effective_user is None:
        return

    manager = context.bot_data["manager"]
    topic_id = message.message_thread_id
    state = manager.get_by_key(chat.id, topic_id)
    if state is None or state.status != GameStatus.ACTIVE:
        return

    lock = manager.lock_for(state.chat_id, state.topic_id)
    async with lock:
        result = engine.leave_game(state, update.effective_user.id)
        if not result.ok:
            return
        await _finalize(context, state, result)


async def on_player_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    message = update.effective_message
    user = update.effective_user
    if chat is None or message is None or user is None or not message.text:
        return
    if message.text.startswith("/"):
        return

    manager = context.bot_data["manager"]
    state = manager.get_by_key(chat.id, message.message_thread_id)
    if state is None or state.status != GameStatus.ACTIVE:
        return

    lock = manager.lock_for(state.chat_id, state.topic_id)
    async with lock:
        result = engine.apply_chat_message(state, user.id, message.text)
        if not result.ok:
            return
        try:
            await message.delete()
        except Exception:
            logger.warning("Could not delete player chat message")
        await update_info_message(context.bot, state)
        manager.save(state)


async def process_distance(update: Update, context: ContextTypes.DEFAULT_TYPE, callback: DistanceCallback) -> None:
    query = update.callback_query
    manager = context.bot_data["manager"]
    state = manager.get_by_id(callback.game_id)
    if state is None:
        await query.answer()
        return

    user_id = query.from_user.id
    result = engine.select_distance(
        state, user_id, callback.direction, callback.distance, callback.move_seq
    )

    if not result.ok:
        await query.answer()
        if result.invalid:
            await send_invalid_move(context.bot, state)
            manager.save(state)
        return

    await query.answer()
    await _finalize(context, state, result)
