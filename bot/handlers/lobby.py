"""Lobby lifecycle: opening a new game, joining/leaving, starting."""
from __future__ import annotations

import logging

from telegram import Update, User
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from ..config import config
from ..game import engine
from ..game.models import GameState, GameStatus, MIN_PLAYERS_TO_START
from ..rendering import messages
from . import game as game_handlers
from .keyboards import lobby_keyboard, start_keyboard

logger = logging.getLogger(__name__)


def _manager(context: ContextTypes.DEFAULT_TYPE):
    return context.bot_data["manager"]


def is_allowed_chat(chat_id: int) -> bool:
    if config.chat_id is None:
        return True
    return chat_id == config.chat_id


def display_name_for(user: User) -> str:
    return user.full_name or user.first_name or str(user.id)


async def cmd_new_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    message = update.effective_message
    if chat is None or message is None:
        return
    topic_id = message.message_thread_id
    if not is_allowed_chat(chat.id):
        return

    manager = _manager(context)
    state = manager.get_by_key(chat.id, topic_id)

    if state is not None and state.status == GameStatus.LOBBY:
        await message.reply_text("Лобби уже открыто.")
        return

    if state is not None and state.status == GameStatus.ACTIVE:
        if state.board_message_id is None or state.info_message_id is None:
            try:
                await game_handlers.send_game_start_messages(context.bot, state)
                manager.save(state)
                return
            except Exception:
                logger.exception("Failed to restore game UI; opening a new lobby")
        else:
            await message.reply_text("Игра уже идёт в этом топике.")
            return

    state = manager.create(chat.id, topic_id)
    await send_lobby_messages(context, state)
    manager.save(state)


async def cmd_restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    message = update.effective_message
    if chat is None or message is None:
        return
    topic_id = message.message_thread_id
    if not is_allowed_chat(chat.id):
        return

    manager = _manager(context)
    lock = manager.lock_for(chat.id, topic_id)
    async with lock:
        state = manager.get_by_key(chat.id, topic_id)
        if state is None:
            await message.reply_text("Нет активной игры.")
            return

        engine.end_game(state)
        await game_handlers.delete_game_messages(context.bot, state)
        manager.save(state)

        new_state = manager.create(chat.id, topic_id)
        await send_lobby_messages(context, new_state)
        manager.save(new_state)


async def send_lobby_messages(context: ContextTypes.DEFAULT_TYPE, state: GameState) -> None:
    bot = context.bot
    rules_msg = await bot.send_message(
        chat_id=state.chat_id,
        message_thread_id=state.topic_id,
        text=messages.rules_message_text(),
        parse_mode=ParseMode.HTML,
    )
    lobby_msg = await bot.send_message(
        chat_id=state.chat_id,
        message_thread_id=state.topic_id,
        text=messages.lobby_message_text(len(state.players)),
        reply_markup=lobby_keyboard(state.game_id),
    )
    start_msg = await bot.send_message(
        chat_id=state.chat_id,
        message_thread_id=state.topic_id,
        text=messages.start_button_message_text(),
        reply_markup=start_keyboard(state.game_id),
    )
    # Persistent 🔈 slot: every later 🔈 line EDITs this message.
    announce_msg = await bot.send_message(
        chat_id=state.chat_id,
        message_thread_id=state.topic_id,
        text=messages.announce_placeholder_text(),
    )
    state.rules_message_id = rules_msg.message_id
    state.lobby_message_id = lobby_msg.message_id
    state.start_message_id = start_msg.message_id
    state.announce_message_id = announce_msg.message_id
    state.track_message(rules_msg.message_id)
    state.track_message(lobby_msg.message_id)
    state.track_message(start_msg.message_id)
    state.track_message(announce_msg.message_id)


async def _refresh_lobby_count(context: ContextTypes.DEFAULT_TYPE, state: GameState) -> None:
    if state.lobby_message_id is None:
        return
    try:
        await context.bot.edit_message_text(
            chat_id=state.chat_id,
            message_id=state.lobby_message_id,
            text=messages.lobby_message_text(len(state.players)),
            reply_markup=lobby_keyboard(state.game_id),
        )
    except Exception:
        pass


async def handle_join(update: Update, context: ContextTypes.DEFAULT_TYPE, game_id: int) -> None:
    query = update.callback_query
    manager = _manager(context)
    state = manager.get_by_id(game_id)
    if state is None or state.status != GameStatus.LOBBY:
        await query.answer()
        return

    user = query.from_user
    result = engine.join_lobby(state, user.id, user.username, display_name_for(user))
    if not result.ok:
        feedback = {
            "already_joined": "Вы уже в лобби.",
            "lobby_full": "Лобби заполнено.",
        }.get(result.reason)
        await query.answer(text=feedback, show_alert=bool(feedback))
        return

    await query.answer()
    await game_handlers.upsert_announcement(
        context.bot,
        state,
        messages.lobby_join_progress_message(result.player, len(state.players), MIN_PLAYERS_TO_START),
    )
    await _refresh_lobby_count(context, state)
    manager.save(state)


async def handle_leave(update: Update, context: ContextTypes.DEFAULT_TYPE, game_id: int) -> None:
    query = update.callback_query
    manager = _manager(context)
    state = manager.get_by_id(game_id)
    if state is None or state.status != GameStatus.LOBBY:
        await query.answer()
        return

    user = query.from_user
    result = engine.leave_lobby(state, user.id)
    if not result.ok:
        await query.answer()
        return

    await query.answer()
    text = messages.lobby_leave_system_message(result.player)
    if len(state.players) < 2:
        text = messages.lobby_not_enough_players_message()
    await game_handlers.upsert_announcement(context.bot, state, text)
    await _refresh_lobby_count(context, state)
    manager.save(state)


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE, game_id: int) -> None:
    query = update.callback_query
    manager = _manager(context)
    state = manager.get_by_id(game_id)
    if state is None or state.status != GameStatus.LOBBY:
        await query.answer()
        return

    if len(state.players) < MIN_PLAYERS_TO_START:
        await query.answer(text=messages.lobby_not_enough_players_message(), show_alert=True)
        return

    await query.answer()

    result = engine.start_game(state)
    if not result.ok:
        manager.save(state)
        return

    try:
        await game_handlers.delete_game_messages(context.bot, state)
        await game_handlers.send_game_start_messages(context.bot, state)
    except Exception:
        logger.exception("Failed to publish game UI after start")
        manager.save(state)
        return
    manager.save(state)
