"""Telegram HTML text and keyboards for Buckshot Roulette."""
from __future__ import annotations

from html import escape

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from . import callbacks
from .emoji_assets import (
    adrenaline,
    beer,
    blank_cartridge,
    cigarettes,
    energy_hp,
    expired_pills,
    handcuffs,
    inverter,
    jammer,
    knife,
    live_cartridge,
    magnifying_glass,
    remote,
    shotgun,
)
from .models import (
    ITEM_NAME_RU,
    BlockKind,
    EventKind,
    GameEvent,
    GameState,
    ItemType,
    Player,
)
from .texts import RULES_ALERT, RULES_FULL, item_name

ITEM_EMOJI = {
    ItemType.BEER: beer,
    ItemType.INVERTER: inverter,
    ItemType.MAGNIFYING_GLASS: magnifying_glass,
    ItemType.CIGARETTES: cigarettes,
    ItemType.HANDCUFFS: handcuffs,
    ItemType.KNIFE: knife,
    ItemType.EXPIRED_PILLS: expired_pills,
    ItemType.JAMMER: jammer,
    ItemType.ADRENALINE: adrenaline,
    ItemType.REMOTE: remote,
}


def item_sticker_html(item: ItemType) -> str:
    return ITEM_EMOJI[item]().to_html()


def item_label_html(item: ItemType) -> str:
    return f"{item_sticker_html(item)} {escape(item_name(item))}"


def hp_html(count: int) -> str:
    token = energy_hp().to_html()
    return "".join(token for _ in range(max(0, count)))


def html_quote(inner: str, *, expandable: bool = False) -> str:
    attr = " expandable" if expandable else ""
    return f"<blockquote{attr}>{inner}</blockquote>"


def rules_message_text() -> str:
    quoted = "Правила\n\n" + escape(RULES_FULL)
    return f"\U0001f50e Правила игры:\n\n{html_quote(quoted, expandable=True)}"


def rules_alert_text() -> str:
    return RULES_ALERT[:200]


def lobby_message_text(count: int) -> str:
    return f"\U0001f9e9 Лобби({count} игроков):"


def start_button_message_text() -> str:
    return "\u2705 Начать игру:"


def announce_placeholder() -> str:
    return "\U0001f508"


def _prefix(player: Player, current_id: int | None) -> str:
    marks = ""
    if current_id is not None and player.user_id == current_id and player.is_active:
        marks += "\U0001f52b"
    if player.block == BlockKind.HANDCUFFS:
        marks += "\U0001f517"
    if player.block == BlockKind.JAMMER:
        marks += "\U0001f6ab"
    return f"{marks} " if marks else ""


def player_line_html(player: Player, current_id: int | None) -> str:
    return (
        f"{_prefix(player, current_id)}"
        f"{escape(player.mention)}: {hp_html(player.hp)}"
    )


def info_message_html(state: GameState) -> str:
    current = state.current_player()
    current_id = current.user_id if current is not None and current.is_active else None
    lines = []
    for player in state.players_in_turn_order():
        if not player.is_active:
            continue
        lines.append(player_line_html(player, current_id))
    body = "\n".join(lines) if lines else "—"
    return f"\U0001f4ce Информация по игре:\n\n{html_quote(body)}"


def _item_lines(inventory: list[ItemType], bullet: str) -> str:
    if not inventory:
        return "пусто"
    return "\n".join(f"{bullet} {item_label_html(item)}." for item in inventory)


def items_commentary_html(player: Player, items: list[ItemType], no_space: bool) -> str:
    block = [f"{escape(player.mention)} берет предметы:"]
    if items:
        block.extend(f"+ {item_label_html(item)}." for item in items)
    if no_space:
        block.append("Нет места.")
    if not items and not no_space:
        block.append("пусто")
    return "\n".join(block)


def shotgun_commentary_html(state: GameState) -> str:
    display = "".join(
        live_cartridge().to_html() if live else blank_cartridge().to_html()
        for live in state.shotgun_display
    )
    live_count = sum(1 for live in state.shotgun_display if live)
    blank_count = len(state.shotgun_display) - live_count
    gun = shotgun().to_html()
    return (
        f"{gun} Заряжается дробовик:\n\n{display}\n\n"
        f"холостых — {blank_count}\nзаряженных — {live_count}"
    )


def inventory_commentary_html(player: Player) -> str:
    return f"Инвентарь {escape(player.mention)}:\n{_item_lines(player.inventory, '•')}"


def look_commentary_html(viewer: Player, other: Player) -> str:
    return (
        f"{escape(viewer.mention)} смотрит инвентарь {escape(other.mention)}:\n"
        f"{_item_lines(other.inventory, '•')}"
    )


def commentary_html(state: GameState) -> str:
    """Render the current-player inventory commentary (state 4)."""
    current = state.current_player()
    if current is None:
        return "\U0001f508"
    look_id = state.looking_at_user_id
    if look_id is not None and look_id != current.user_id:
        other = state.get_player(look_id)
        if other is not None:
            return look_commentary_html(current, other)
    return inventory_commentary_html(current)


def render_event(state: GameState, event: GameEvent) -> str | None:
    if event.kind == EventKind.STATUS:
        return event.text
    if event.kind == EventKind.ITEMS:
        player = state.get_player(event.player_id or -1)
        if player is None:
            return None
        return items_commentary_html(player, event.items, event.no_space)
    if event.kind == EventKind.SHOTGUN:
        return shotgun_commentary_html(state)
    if event.kind == EventKind.INVENTORY:
        player = state.get_player(event.player_id or -1)
        if player is None:
            return None
        return inventory_commentary_html(player)
    if event.kind == EventKind.LOOK:
        viewer = state.get_player(event.player_id or -1)
        other = state.get_player(event.other_id or -1)
        if viewer is None or other is None:
            return None
        return look_commentary_html(viewer, other)
    if event.kind == EventKind.STEAL:
        thief = state.get_player(event.player_id or -1)
        victim = state.get_player(event.other_id or -1)
        if thief is None or victim is None or event.item is None:
            return None
        return steal_commentary_html(thief, victim, event.item)
    return None


def steal_commentary_html(thief: Player, victim: Player, item: ItemType) -> str:
    sticker = item_label_html(item)
    return (
        f"{escape(thief.mention)} получает предмет.\n\n"
        f"+ {sticker}.\n\n"
        f"{escape(victim.mention)} теряет предмет.\n\n"
        f"- {sticker}."
    )


def actions_message_text() -> str:
    return "Действия:"


def lobby_keyboard(game_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Зайти", callback_data=callbacks.encode_lobby(callbacks.JOIN, game_id)),
                InlineKeyboardButton("Выйти", callback_data=callbacks.encode_lobby(callbacks.LEAVE, game_id)),
            ]
        ]
    )


def start_keyboard(game_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("тык", callback_data=callbacks.encode_lobby(callbacks.START, game_id))]]
    )


def info_keyboard(state: GameState) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Правила",
                    callback_data=callbacks.encode_lobby(callbacks.RULES, state.game_id),
                ),
                InlineKeyboardButton(
                    "Выйти",
                    callback_data=callbacks.encode_lobby(callbacks.QUIT, state.game_id),
                ),
            ]
        ]
    )


def actions_keyboard(state: GameState) -> InlineKeyboardMarkup:
    seq = state.action_seq
    gid = state.game_id
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Выстрелить", callback_data=callbacks.encode_seq(callbacks.SHOOT, gid, seq)),
                InlineKeyboardButton("Использовать предмет", callback_data=callbacks.encode_seq(callbacks.USE, gid, seq)),
                InlineKeyboardButton("Посмотреть инвентарь", callback_data=callbacks.encode_seq(callbacks.INSPECT, gid, seq)),
            ]
        ]
    )


def target_keyboard(
    state: GameState, kind: str, include_self: bool, *, exclude_self: bool = True
) -> InlineKeyboardMarkup:
    current = state.current_player()
    current_id = current.user_id if current else None
    buttons = []
    if include_self and current is not None:
        buttons.append(
            InlineKeyboardButton(
                "Я",
                callback_data=callbacks.encode_target(kind, state.game_id, state.action_seq, current.user_id),
            )
        )
    for player in state.players_in_turn_order():
        if not player.is_active:
            continue
        if exclude_self and player.user_id == current_id:
            continue
        buttons.append(
            InlineKeyboardButton(
                player.mention,
                callback_data=callbacks.encode_target(kind, state.game_id, state.action_seq, player.user_id),
            )
        )
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(rows)


def item_keyboard(state: GameState, items: list[ItemType], kind: str) -> InlineKeyboardMarkup:
    from .engine import unique_item_types

    unique = unique_item_types(items)
    buttons = [
        InlineKeyboardButton(
            f"{ITEM_EMOJI[item]().placeholder} {ITEM_NAME_RU[item]}",
            callback_data=callbacks.encode_item(kind, state.game_id, state.action_seq, item),
        )
        for item in unique
    ]
    rows = [[button] for button in buttons]
    return InlineKeyboardMarkup(rows)


def inspect_back_keyboard(state: GameState) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Назад",
                    callback_data=callbacks.encode_seq(callbacks.BACK, state.game_id, state.action_seq),
                )
            ]
        ]
    )


def magnify_keyboard(state: GameState) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "тык",
                    callback_data=callbacks.encode_seq(callbacks.MAGNIFY, state.game_id, state.action_seq),
                )
            ]
        ]
    )
