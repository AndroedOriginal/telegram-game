"""Renders the 8x8 board as Telegram HTML using custom emoji.

Uses ``<tg-emoji emoji-id="...">placeholder</tg-emoji>`` tags, which requires
sending/editing the message with ``parse_mode=ParseMode.HTML``. This avoids
manual UTF-16 offset bookkeeping that raw ``MessageEntity`` lists would
require.
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
    """Render the full board message text (HTML, custom emoji)."""

    lines: list[str] = []

    header = "".join(column_label(letter).to_html() for letter in "ABCDEFGH")
    header += at_symbol().to_html()
    lines.append(header)

    for row in ROWS:
        cells = "".join(render_square(Position(col, row), state) for col in range(8))
        cells += row_label(str(row)).to_html()
        lines.append(cells)

    # Normal (non-collapsible) Telegram quote so the full board stays visible.
    body = "\n".join(lines)
    return f"<blockquote>{body}</blockquote>"
