"""Renders the 8x8 board as Telegram HTML using custom emoji.

Uses ``<tg-emoji emoji-id="...">placeholder</tg-emoji>`` tags. The board
message is sent as a rich message whose entire body is a Heading 6 block
(``<h6>``), not classic ``parse_mode=HTML``.
"""
from __future__ import annotations

from ..emoji_assets import at_symbol, column_label, empty_cell, evolution_point, piece, row_label
from ..game.board import ROWS, Position, cell_color
from ..game.models import GameState


def render_square(position: Position, state: GameState) -> str:
    """Return the HTML for a single square, chosen based on:
    1. square color; 2. whether it is empty; 3. piece type; 4. piece visual
    color; 5. whether it holds an evolution point (section 45)."""

    color = cell_color(position)

    for player in state.active_players():
        if player.position == position:
            return piece(player.piece_type.value, player.color.value, color).to_html()

    if state.get_spawn_at(position) is not None:
        return evolution_point().to_html()

    return empty_cell(color).to_html()


def render_board(state: GameState) -> str:
    """Render the 8×8 board (header + 8 rows) as custom-emoji HTML.

    No divider, quote, or heading wrapper — that belongs to
    :func:`render_board_heading6_html`.
    """

    lines: list[str] = []

    header = "".join(column_label(letter).to_html() for letter in "ABCDEFGH")
    header += at_symbol().to_html()
    lines.append(header)

    for row in ROWS:
        cells = "".join(render_square(Position(col, row), state) for col in range(8))
        cells += row_label(str(row)).to_html()
        lines.append(cells)

    return "\n".join(lines)


def render_board_heading6_html(state: GameState) -> str:
    """Wrap the board in Telegram rich-message Heading 6 (``<h6>``).

    This is the Bot API heading entity (size 6), not literal ``######`` text.
    """

    body = "<br/>".join(render_board(state).split("\n"))
    return f"<h6>{body}</h6>"


def board_rich_message_payload(state: GameState) -> dict:
    """``InputRichMessage`` dict for sendRichMessage / editMessageText."""

    return {
        "html": render_board_heading6_html(state),
        "skip_entity_detection": True,
    }
