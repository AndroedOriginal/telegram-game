"""Centralized mapping of Telegram custom/premium emoji asset IDs.

Every custom emoji ID used anywhere in the bot must be defined here and only
here. Other modules must import from this file instead of hardcoding IDs.

Each custom emoji also has a plain-unicode *placeholder* character. Telegram
requires message text to contain some base character at the position of a
``custom_emoji`` :class:`telegram.MessageEntity`; Telegram clients that
render custom emoji will display the custom asset instead of the
placeholder, while old/unsupported clients gracefully fall back to the
placeholder glyph.
"""
from __future__ import annotations

from typing import NamedTuple

# ---------------------------------------------------------------------------
# Empty cells
# ---------------------------------------------------------------------------

EMPTY_CELL_ID = {
    "white": "5463266029067049982",
    "black": "5463141938871933969",
}

EMPTY_CELL_PLACEHOLDER = {
    "white": "\u2b1c",  # ⬜
    "black": "\u2b1b",  # ⬛
}

# ---------------------------------------------------------------------------
# Pieces: PIECE_EMOJI_ID[piece_type][piece_color][cell_color] -> emoji id
# ---------------------------------------------------------------------------

PIECE_EMOJI_ID: dict[str, dict[str, dict[str, str]]] = {
    "rook": {
        "black": {"white": "5460977219520175329", "black": "5463270470063232777"},
        "white": {"white": "5463380464175683475", "black": "5462969049258399603"},
    },
    "knight": {
        "black": {"white": "5462888625995782718", "black": "5462906570369145089"},
        "white": {"white": "5461001155372916760", "black": "5463006621632305328"},
    },
    "bishop": {
        "black": {"white": "5463343948363732784", "black": "5462909061450178538"},
        "white": {"white": "5460750320692894933", "black": "5460794004805262695"},
    },
    "queen": {
        "black": {"white": "5463343643421056510", "black": "5461058634920237556"},
        "white": {"white": "5463332764268894885", "black": "5463084394900101163"},
    },
    "pawn": {
        "black": {"white": "5463154677744933493", "black": "5462983437398841197"},
        "white": {"white": "5463254896511820044", "black": "5463011651039010794"},
    },
}

PIECE_PLACEHOLDER: dict[str, dict[str, str]] = {
    "rook": {"black": "\u265c", "white": "\u2656"},
    "knight": {"black": "\u265e", "white": "\u2658"},
    "bishop": {"black": "\u265d", "white": "\u2657"},
    "queen": {"black": "\u265b", "white": "\u2655"},
    "pawn": {"black": "\u265f", "white": "\u2659"},
}

# ---------------------------------------------------------------------------
# Evolution point
# ---------------------------------------------------------------------------

EVOLUTION_POINT_ID = "5321386637756737472"
EVOLUTION_POINT_PLACEHOLDER = "\u2728"  # ✨

# ---------------------------------------------------------------------------
# Column / row labels and the "@" symbol used in the board header
# ---------------------------------------------------------------------------

COLUMN_LABEL_ID = {
    "A": "5458387461614870880",
    "B": "5458683676919341301",
    "C": "5458693684193140825",
    "D": "5458562958273551226",
    "E": "5458589359437519868",
    "F": "5458771517590478004",
    "G": "5458919792746438216",
    "H": "5458457503941532285",
}

ROW_LABEL_ID = {
    "8": "5456378486367198336",
    "7": "5458424406923550621",
    "6": "5458527421714143938",
    "5": "5458647354380917765",
    "4": "5456543709464107434",
    "3": "5456376064005642315",
    "2": "5458730337444044152",
    "1": "5456442352530889128",
}

AT_SYMBOL_ID = "5458830526146157735"
AT_SYMBOL_PLACEHOLDER = "@"


class EmojiRef(NamedTuple):
    """A placeholder character paired with the custom emoji id it maps to."""

    placeholder: str
    custom_emoji_id: str

    def to_html(self) -> str:
        """Render as a Telegram HTML ``<tg-emoji>`` tag (requires
        ``parse_mode=HTML`` when sending/editing the message)."""

        return f'<tg-emoji emoji-id="{self.custom_emoji_id}">{self.placeholder}</tg-emoji>'


def empty_cell(cell_color: str) -> EmojiRef:
    return EmojiRef(EMPTY_CELL_PLACEHOLDER[cell_color], EMPTY_CELL_ID[cell_color])


def piece(piece_type: str, piece_color: str, cell_color: str) -> EmojiRef:
    return EmojiRef(
        PIECE_PLACEHOLDER[piece_type][piece_color],
        PIECE_EMOJI_ID[piece_type][piece_color][cell_color],
    )


def evolution_point() -> EmojiRef:
    return EmojiRef(EVOLUTION_POINT_PLACEHOLDER, EVOLUTION_POINT_ID)


def column_label(letter: str) -> EmojiRef:
    return EmojiRef(letter, COLUMN_LABEL_ID[letter])


def row_label(digit: str) -> EmojiRef:
    return EmojiRef(digit, ROW_LABEL_ID[digit])


def at_symbol() -> EmojiRef:
    return EmojiRef(AT_SYMBOL_PLACEHOLDER, AT_SYMBOL_ID)
