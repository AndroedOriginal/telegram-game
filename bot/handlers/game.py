"""Rendering/sending of the persistent game UI (info + board messages) and
processing of movement callbacks."""
from __future__ import annotations

from telegram import Bot, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from ..callback_data import DirectionCallback, DistanceCallback
from ..game import engine
from ..game.models import GameState, GameStatus
from ..rendering.board_renderer import render_board
from ..rendering.messages import distance_prompt_text, info_message_text
from .keyboards import direction_keyboard, distance_keyboard

INVALID_MOVE_TEXT = "ход невозможен."


async def send_game_start_messages(bot: Bot, state: GameState) -> None:
    current = state.current_player()
    board_msg = await bot.send_message(
        chat_id=state.chat_id,
        message_thread_id=state.topic_id,
        text=render_board(state),
        parse_mode=ParseMode.HTML,
        reply_markup=direction_keyboard(state.game_id, state.move_seq),
    )
    state.board_message_id = board_msg.message_id

    info_msg = await bot.send_message(
        chat_id=state.chat_id,
        message_thread_id=state.topic_id,
        text=info_message_text(state, current),
        parse_mode=ParseMode.HTML,
    )
    state.info_message_id = info_msg.message_id


async def update_game_messages(bot: Bot, state: GameState) -> None:
    reply_markup = direction_keyboard(state.game_id, state.move_seq) if state.status == GameStatus.ACTIVE else None
    if state.board_message_id is not None:
        try:
            await bot.edit_message_text(
                chat_id=state.chat_id,
                message_id=state.board_message_id,
                text=render_board(state),
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
            )
        except Exception:
            pass

    if state.status == GameStatus.ACTIVE and state.info_message_id is not None:
        current = state.current_player()
        if current is not None:
            try:
                await bot.edit_message_text(
                    chat_id=state.chat_id,
                    message_id=state.info_message_id,
                    text=info_message_text(state, current),
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass


async def send_announcements(bot: Bot, state: GameState, announcements: list[str]) -> None:
    for text in announcements:
        await bot.send_message(chat_id=state.chat_id, message_thread_id=state.topic_id, text=text)


async def send_distance_prompt(bot: Bot, state: GameState, callback: DirectionCallback, max_distance: int) -> None:
    msg = await bot.send_message(
        chat_id=state.chat_id,
        message_thread_id=state.topic_id,
        text=distance_prompt_text(),
        reply_markup=distance_keyboard(state.game_id, state.move_seq, callback.direction, max_distance),
    )
    state.distance_message_id = msg.message_id


async def delete_distance_prompt(bot: Bot, state: GameState) -> None:
    if state.distance_message_id is not None:
        try:
            await bot.delete_message(chat_id=state.chat_id, message_id=state.distance_message_id)
        except Exception:
            pass
        state.distance_message_id = None


async def send_invalid_move(bot: Bot, state: GameState) -> None:
    await bot.send_message(chat_id=state.chat_id, message_thread_id=state.topic_id, text=INVALID_MOVE_TEXT)


async def _finalize(context: ContextTypes.DEFAULT_TYPE, state: GameState, result) -> None:
    await delete_distance_prompt(context.bot, state)
    await update_game_messages(context.bot, state)
    await send_announcements(context.bot, state, result.announcements)
    context.bot_data["manager"].save(state)


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
        return

    await query.answer()

    if result.pending_distances is not None:
        await send_distance_prompt(context.bot, state, callback, len(result.pending_distances))
        manager.save(state)
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
        return

    await query.answer()
    await _finalize(context, state, result)
