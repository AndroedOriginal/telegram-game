"""Telegram handlers for Buckshot Roulette lobby and gameplay."""
from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from ..config import config
from ..handlers.lobby import display_name_for, is_allowed_chat
from ..handlers.telegram_safe import telegram_retry
from . import callbacks
from . import engine
from . import sequencer
from . import ui
from .engine import ActionResult
from .models import EventKind, GameState, GameStatus, PendingKind
from .sequencer import SLOT_ACTIONS, SLOT_COMMENTARY, SLOT_INFO, SLOT_STATUS, UiUpdate
from .texts import not_enough_players

logger = logging.getLogger(__name__)


def _manager(context):
    return context.bot_data["manager"]


def _topic_allowed(topic_id: int | None) -> bool:
    if config.buckshot_topic_id is None:
        return True
    return topic_id == config.buckshot_topic_id


async def _delete_ids(bot, state: GameState) -> None:
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
    state.temp_message_ids = []
    state.info_message_id = None
    state.commentary_message_id = None
    state.actions_message_id = None
    state.rules_message_id = None
    state.lobby_message_id = None
    state.start_message_id = None
    state.announce_message_id = None
    state.status_message_id = None
    state.magnify_message_id = None


async def _edit_or_send(bot, chat_id, message_id, topic_id, text, markup=None, parse_mode=ParseMode.HTML):
    if message_id is not None:
        try:
            await telegram_retry(
                lambda: bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=markup,
                    parse_mode=parse_mode,
                )
            )
            return message_id
        except BadRequest:
            pass
    msg = await telegram_retry(
        lambda: bot.send_message(
            chat_id=chat_id,
            message_thread_id=topic_id,
            text=text,
            reply_markup=markup,
            parse_mode=parse_mode,
        )
    )
    return None if msg is None else msg.message_id


async def _delete_temps(bot, state: GameState) -> None:
    ids = list(state.temp_message_ids)
    state.temp_message_ids = []
    for message_id in ids:
        try:
            await bot.delete_message(chat_id=state.chat_id, message_id=message_id)
        except Exception:
            pass


def _pending_markup(state: GameState):
    pending = state.pending
    if pending is None:
        return None, None
    if pending.kind == PendingKind.SHOOT_TARGET:
        return "Цель:", ui.target_keyboard(state, callbacks.TARGET, include_self=True, exclude_self=True)
    if pending.kind == PendingKind.USE_ITEM:
        current = state.current_player()
        if current is None:
            return None, None
        return "Предмет:", ui.item_keyboard(state, current.inventory, callbacks.ITEM)
    if pending.kind == PendingKind.JAMMER_TARGET:
        return "Цель:", ui.target_keyboard(state, callbacks.JAMMER, include_self=False)
    if pending.kind == PendingKind.ADRENALINE_TARGET:
        return "Цель:", _steal_target_keyboard(state)
    if pending.kind == PendingKind.ADRENALINE_ITEM:
        target = state.get_player(pending.target_user_id) if pending.target_user_id else None
        if target is None:
            return None, None
        return "Предмет:", ui.item_keyboard(state, target.inventory, callbacks.ADR_ITEM)
    if pending.kind == PendingKind.INSPECT_TARGET and pending.target_user_id:
        return "\u2190", ui.inspect_back_keyboard(state)
    if pending.kind == PendingKind.INSPECT_TARGET:
        return "Цель:", ui.target_keyboard(state, callbacks.LOOK, include_self=False)
    return None, None


def _updates_for_events(state: GameState, events) -> list[UiUpdate]:
    updates: list[UiUpdate] = []
    for event in events:
        text = ui.render_event(state, event)
        if not text:
            continue
        if event.kind == EventKind.STATUS:
            updates.append(UiUpdate(slot=SLOT_STATUS, text=text, parse_mode=None))
        else:
            updates.append(UiUpdate(slot=SLOT_COMMENTARY, text=text, parse_mode=ParseMode.HTML))
    return updates


async def _apply_ui_update(bot, state: GameState, update: UiUpdate) -> None:
    message_id = sequencer.slot_message_id(state, update.slot)
    markup = update.markup
    if update.slot == SLOT_INFO and markup is None:
        markup = ui.info_keyboard(state)
    elif update.slot == SLOT_ACTIONS and markup is None:
        markup = ui.actions_keyboard(state)
    if message_id is None:
        new_id = await _edit_or_send(
            bot,
            state.chat_id,
            None,
            state.topic_id,
            update.text,
            markup=markup,
            parse_mode=update.parse_mode,
        )
        if new_id:
            sequencer.set_slot_message_id(state, update.slot, new_id)
        return
    try:
        await telegram_retry(
            lambda: bot.edit_message_text(
                chat_id=state.chat_id,
                message_id=message_id,
                text=update.text,
                reply_markup=markup,
                parse_mode=update.parse_mode,
            )
        )
    except BadRequest:
        logger.warning("Could not edit persistent %s message %s", update.slot, message_id)


async def _publish_events(bot, state: GameState, result: ActionResult) -> None:
    async def apply(update: UiUpdate) -> None:
        await _apply_ui_update(bot, state, update)

    events = list(result.events)
    split = result.ui_sync_at
    if split is None or split < 0 or split > len(events):
        await sequencer.apply_sequence(_updates_for_events(state, events), apply=apply)
        return
    await sequencer.apply_sequence(_updates_for_events(state, events[:split]), apply=apply)
    if state.status == GameStatus.ACTIVE:
        await _apply_ui_update(
            bot,
            state,
            UiUpdate(slot=SLOT_INFO, text=ui.info_message_html(state), markup=ui.info_keyboard(state)),
        )
    await sequencer.apply_sequence(_updates_for_events(state, events[split:]), apply=apply)


async def _refresh_persistent_ui(bot, state: GameState) -> None:
    if state.status != GameStatus.ACTIVE:
        return
    await _delete_temps(bot, state)
    info_id = await _edit_or_send(
        bot,
        state.chat_id,
        state.info_message_id,
        state.topic_id,
        ui.info_message_html(state),
        markup=ui.info_keyboard(state),
    )
    if info_id:
        state.info_message_id = info_id
        state.track_message(info_id)
    act_id = await _edit_or_send(
        bot,
        state.chat_id,
        state.actions_message_id,
        state.topic_id,
        ui.actions_message_text(),
        markup=ui.actions_keyboard(state),
        parse_mode=None,
    )
    if act_id:
        state.actions_message_id = act_id
        state.track_message(act_id)

    caption, markup = _pending_markup(state)
    pending = state.pending
    if pending is not None and pending.kind == PendingKind.MAGNIFY and state.magnify_message_id is None:
        msg = await telegram_retry(
            lambda: bot.send_message(
                chat_id=state.chat_id,
                message_thread_id=state.topic_id,
                text="Узнать патрон:",
                reply_markup=ui.magnify_keyboard(state),
            )
        )
        if msg is not None:
            state.magnify_message_id = msg.message_id
            state.track_message(msg.message_id)
        return
    if markup is None:
        return
    text = caption or " "
    msg = await telegram_retry(
        lambda: bot.send_message(
            chat_id=state.chat_id,
            message_thread_id=state.topic_id,
            text=text,
            reply_markup=markup,
        )
    )
    if msg is not None:
        state.temp_message_ids.append(msg.message_id)
        state.track_message(msg.message_id)


def _steal_target_keyboard(state: GameState):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    current = state.current_player()
    current_id = current.user_id if current else None
    buttons = []
    for player in state.stealable_players(current_id or -1):
        buttons.append(
            InlineKeyboardButton(
                player.mention,
                callback_data=callbacks.encode_target(
                    callbacks.ADR_TARGET, state.game_id, state.action_seq, player.user_id
                ),
            )
        )
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)] or [[]]
    return InlineKeyboardMarkup(rows)


async def _delete_magnify(bot, state: GameState) -> None:
    if state.magnify_message_id is None:
        return
    try:
        await bot.delete_message(chat_id=state.chat_id, message_id=state.magnify_message_id)
    except Exception:
        pass
    state.magnify_message_id = None


async def send_lobby_messages(context, state: GameState) -> None:
    bot = context.bot
    rules = await bot.send_message(
        chat_id=state.chat_id,
        message_thread_id=state.topic_id,
        text=ui.rules_message_text(),
        parse_mode=ParseMode.HTML,
    )
    lobby = await bot.send_message(
        chat_id=state.chat_id,
        message_thread_id=state.topic_id,
        text=ui.lobby_message_text(len(state.players)),
        reply_markup=ui.lobby_keyboard(state.game_id),
    )
    start = await bot.send_message(
        chat_id=state.chat_id,
        message_thread_id=state.topic_id,
        text=ui.start_button_message_text(),
        reply_markup=ui.start_keyboard(state.game_id),
    )
    state.rules_message_id = rules.message_id
    state.lobby_message_id = lobby.message_id
    state.start_message_id = start.message_id
    announce = await bot.send_message(
        chat_id=state.chat_id,
        message_thread_id=state.topic_id,
        text=ui.announce_placeholder(),
    )
    state.announce_message_id = announce.message_id
    state.status_message_id = announce.message_id
    state.track_message(rules.message_id)
    state.track_message(lobby.message_id)
    state.track_message(start.message_id)
    state.track_message(announce.message_id)


async def send_game_messages(bot, state: GameState) -> None:
    info = await bot.send_message(
        chat_id=state.chat_id,
        message_thread_id=state.topic_id,
        text=ui.info_message_html(state),
        reply_markup=ui.info_keyboard(state),
        parse_mode=ParseMode.HTML,
    )
    commentary = await bot.send_message(
        chat_id=state.chat_id,
        message_thread_id=state.topic_id,
        text="\u200b",
        parse_mode=ParseMode.HTML,
    )
    actions = await bot.send_message(
        chat_id=state.chat_id,
        message_thread_id=state.topic_id,
        text=ui.actions_message_text(),
        reply_markup=ui.actions_keyboard(state),
    )
    status = await bot.send_message(
        chat_id=state.chat_id,
        message_thread_id=state.topic_id,
        text=ui.announce_placeholder(),
    )
    state.info_message_id = info.message_id
    state.commentary_message_id = commentary.message_id
    state.actions_message_id = actions.message_id
    state.status_message_id = status.message_id
    state.announce_message_id = status.message_id
    state.track_message(info.message_id)
    state.track_message(commentary.message_id)
    state.track_message(actions.message_id)
    state.track_message(status.message_id)


async def cmd_new_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    message = update.effective_message
    if chat is None or message is None:
        return
    topic_id = message.message_thread_id
    if not is_allowed_chat(chat.id) or not _topic_allowed(topic_id):
        return
    manager = _manager(context)
    if manager.get_by_key(chat.id, topic_id) is not None:
        await message.reply_text("В этом топике уже идёт другая игра.")
        return
    state = manager.get_buckshot_by_key(chat.id, topic_id)
    if state is not None and state.status == GameStatus.LOBBY:
        await message.reply_text("Лобби уже открыто.")
        return
    if state is not None and state.status == GameStatus.ACTIVE:
        await message.reply_text("Игра уже идёт в этом топике.")
        return
    try:
        state = manager.create_buckshot(chat.id, topic_id)
        await send_lobby_messages(context, state)
        manager.save_buckshot(state)
    except Exception:
        logger.exception("Failed to open Buckshot Roulette lobby")
        await message.reply_text("Не удалось открыть лобби Buckshot Roulette.")


async def restart_in_topic(context, chat_id: int, topic_id: int | None) -> GameState:
    manager = _manager(context)
    state = manager.get_buckshot_by_key(chat_id, topic_id)
    if state is not None:
        engine.end_game(state)
        await _delete_ids(context.bot, state)
        manager.save_buckshot(state)
    new_state = manager.create_buckshot(chat_id, topic_id)
    await send_lobby_messages(context, new_state)
    manager.save_buckshot(new_state)
    return new_state


async def _after_action(context, state: GameState, result: ActionResult) -> None:
    manager = _manager(context)
    if result.delete_magnify:
        await _delete_magnify(context.bot, state)
    await _publish_events(context.bot, state, result)
    if result.victory or result.open_lobby:
        await _delete_ids(context.bot, state)
        manager.save_buckshot(state)
        new_state = manager.create_buckshot(state.chat_id, state.topic_id)
        await send_lobby_messages(context, new_state)
        manager.save_buckshot(new_state)
        return
    await _refresh_persistent_ui(context.bot, state)
    manager.save_buckshot(state)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str) -> None:
    query = update.callback_query
    try:
        callback = callbacks.decode(data)
    except callbacks.CallbackParseError:
        await query.answer()
        return
    manager = _manager(context)
    state = manager.get_buckshot_by_id(callback.game_id)
    if state is None:
        await query.answer()
        return
    lock = manager.lock_for(state.chat_id, state.topic_id)
    async with lock:
        await _dispatch(update, context, state, callback)


async def _dispatch(update, context, state: GameState, callback) -> None:
    query = update.callback_query
    user = query.from_user
    manager = _manager(context)

    if isinstance(callback, callbacks.LobbyCallback):
        if callback.kind == callbacks.RULES:
            await query.answer(text=ui.rules_alert_text(), show_alert=True)
            return
        if callback.kind == callbacks.QUIT:
            if state.status != GameStatus.ACTIVE:
                await query.answer()
                return
            result = engine.leave_game(state, user.id)
            if not result.ok:
                await query.answer()
                return
            await query.answer()
            await _after_action(context, state, result)
            return
        if state.status != GameStatus.LOBBY:
            await query.answer()
            return
        if callback.kind == callbacks.JOIN:
            result = engine.join_lobby(state, user.id, user.username, display_name_for(user))
            if not result.ok:
                feedback = {"already_joined": "Вы уже в лобби.", "lobby_full": "Лобби заполнено."}.get(result.reason)
                await query.answer(text=feedback, show_alert=bool(feedback))
                return
            await query.answer()
            await _lobby_announce(context, state, result)
            manager.save_buckshot(state)
            return
        if callback.kind == callbacks.LEAVE:
            result = engine.leave_lobby(state, user.id)
            if not result.ok:
                await query.answer()
                return
            await query.answer()
            await _lobby_announce(context, state, result)
            manager.save_buckshot(state)
            return
        if callback.kind == callbacks.START:
            if len(state.players) < 2:
                await query.answer(text=not_enough_players(), show_alert=True)
                return
            await query.answer()
            result = engine.start_game(state)
            if not result.ok:
                manager.save_buckshot(state)
                return
            await _delete_ids(context.bot, state)
            await send_game_messages(context.bot, state)
            await _publish_events(context.bot, state, result)
            await _refresh_persistent_ui(context.bot, state)
            manager.save_buckshot(state)
            return
        await query.answer()
        return

    if state.status != GameStatus.ACTIVE:
        await query.answer()
        return

    seq = callback.action_seq
    kind = callback.kind
    result: ActionResult | None = None

    if kind == callbacks.MAGNIFY:
        if user.id != (state.current_player().user_id if state.current_player() else None):
            denied = engine.peek_denied()
            await query.answer(text=denied.private_alert, show_alert=True)
            return
        result = engine.peek_cartridge(state, user.id, seq)
        await query.answer(text=result.private_alert, show_alert=True)
        if result.ok:
            await _delete_magnify(context.bot, state)
            manager.save_buckshot(state)
        return

    if kind == callbacks.SHOOT:
        result = engine.open_shoot(state, user.id, seq)
    elif kind == callbacks.TARGET:
        result = engine.shoot(state, user.id, callback.target_id, seq)
    elif kind == callbacks.USE:
        result = engine.open_use_item(state, user.id, seq)
    elif kind == callbacks.ITEM:
        result = engine.use_item(state, user.id, callback.item, seq)
    elif kind == callbacks.JAMMER:
        result = engine.choose_jammer_target(state, user.id, callback.target_id, seq)
    elif kind == callbacks.ADR_TARGET:
        result = engine.choose_adrenaline_target(state, user.id, callback.target_id, seq)
    elif kind == callbacks.ADR_ITEM:
        result = engine.steal_and_use(state, user.id, callback.item, seq)
    elif kind == callbacks.INSPECT:
        result = engine.open_inspect(state, user.id, seq)
    elif kind == callbacks.LOOK:
        result = engine.inspect_player(state, user.id, callback.target_id, seq)
    elif kind == callbacks.BACK:
        result = engine.inspect_back(state, user.id, seq)
    else:
        await query.answer()
        return

    if not result.ok:
        await query.answer()
        return
    await query.answer()
    await _after_action(context, state, result)


async def _lobby_announce(context, state: GameState, result: ActionResult) -> None:
    async def apply(update: UiUpdate) -> None:
        await _apply_ui_update(context.bot, state, update)

    await sequencer.apply_sequence(_updates_for_events(state, result.events), apply=apply)
    if state.lobby_message_id is not None:
        try:
            await context.bot.edit_message_text(
                chat_id=state.chat_id,
                message_id=state.lobby_message_id,
                text=ui.lobby_message_text(len(state.players)),
                reply_markup=ui.lobby_keyboard(state.game_id),
            )
        except Exception:
            pass


async def cmd_leave(update: Update, context: ContextTypes.DEFAULT_TYPE, state: GameState) -> None:
    user = update.effective_user
    if user is None:
        return
    result = engine.leave_game(state, user.id)
    if not result.ok:
        return
    await _after_action(context, state, result)
