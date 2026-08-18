from bot.emoji_assets import (
    LABEL_PLACEHOLDER,
    at_symbol,
    column_label,
    empty_cell,
    evolution_point,
    piece,
    row_label,
)
from bot.game.board import Position
from bot.game.models import GameState, GameStatus, Player, PieceColor, PieceType, Spawn
from bot.rendering.board_renderer import render_board, render_square


def _is_emoji_placeholder(text: str) -> bool:
    return not text.isalnum() and text not in {"@", "#"}


def test_custom_emoji_placeholders_are_not_plain_text():
    assert _is_emoji_placeholder(empty_cell("white").placeholder)
    assert _is_emoji_placeholder(empty_cell("black").placeholder)
    assert _is_emoji_placeholder(piece("pawn", "white", "black").placeholder)
    assert _is_emoji_placeholder(evolution_point().placeholder)
    assert _is_emoji_placeholder(column_label("A").placeholder)
    assert _is_emoji_placeholder(row_label("8").placeholder)
    assert _is_emoji_placeholder(at_symbol().placeholder)
    assert column_label("A").placeholder == LABEL_PLACEHOLDER


def test_render_board_uses_tg_emoji_tags_not_raw_letters_as_entities():
    state = GameState(game_id=1, chat_id=-1, topic_id=1, status=GameStatus.ACTIVE)
    player = Player(
        user_id=1,
        username="alice",
        display_name="Alice",
        color=PieceColor.WHITE,
        piece_type=PieceType.PAWN,
        position=Position.from_algebraic("D4"),
    )
    state.players = [player]
    state.spawns = [Spawn(owner_user_id=1, position=Position.from_algebraic("D4"))]
    html = render_board(state)
    assert html.count("<tg-emoji") == 9 * 9  # header + 8 rows, 9 cells each
    assert 'emoji-id="' in html
    square = render_square(Position.from_algebraic("A8"), state)
    assert square.startswith("<tg-emoji")
    assert "A" not in square
