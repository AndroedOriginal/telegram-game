"""InlineKeyboardMarkup builders."""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from ..callback_data import (
    DRAW,
    LOBBY_JOIN,
    LOBBY_LEAVE,
    LOBBY_START,
    QUIT,
    RULES,
    encode_direction,
    encode_distance,
    encode_game_button,
    encode_lobby,
)
from ..game.models import DIRECTION_EMOJI, Direction

DIRECTION_ORDER = (
    Direction.LEFT,
    Direction.RIGHT,
    Direction.UP,
    Direction.DOWN,
    Direction.UP_LEFT,
    Direction.UP_RIGHT,
    Direction.DOWN_LEFT,
    Direction.DOWN_RIGHT,
)

DIGIT_EMOJI = ["1\ufe0f\u20e3", "2\ufe0f\u20e3", "3\ufe0f\u20e3", "4\ufe0f\u20e3",
               "5\ufe0f\u20e3", "6\ufe0f\u20e3", "7\ufe0f\u20e3"]


def lobby_keyboard(game_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Зайти", callback_data=encode_lobby(LOBBY_JOIN, game_id)),
                InlineKeyboardButton("Выйти", callback_data=encode_lobby(LOBBY_LEAVE, game_id)),
            ]
        ]
    )


def start_keyboard(game_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("тык", callback_data=encode_lobby(LOBBY_START, game_id))]]
    )


def info_keyboard(game_id: int, move_seq: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Правила", callback_data=encode_game_button(RULES, game_id, move_seq)),
                InlineKeyboardButton("Выйти", callback_data=encode_game_button(QUIT, game_id, move_seq)),
                InlineKeyboardButton("Ничья", callback_data=encode_game_button(DRAW, game_id, move_seq)),
            ]
        ]
    )


def direction_keyboard(game_id: int, move_seq: int) -> InlineKeyboardMarkup:
    row = [
        InlineKeyboardButton(
            DIRECTION_EMOJI[direction],
            callback_data=encode_direction(game_id, move_seq, direction),
        )
        for direction in DIRECTION_ORDER
    ]
    return InlineKeyboardMarkup([row])


def distance_keyboard(
    game_id: int, move_seq: int, direction: Direction, max_distance: int
) -> InlineKeyboardMarkup:
    row = [
        InlineKeyboardButton(
            DIGIT_EMOJI[n - 1],
            callback_data=encode_distance(game_id, move_seq, direction, n),
        )
        for n in range(1, max_distance + 1)
    ]
    return InlineKeyboardMarkup([row])
