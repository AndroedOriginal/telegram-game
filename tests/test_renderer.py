from bot.emoji_assets import (
    EmojiRef,
    LABEL_PLACEHOLDER,
    all_custom_emoji_ids,
    at_symbol,
    column_label,
    divider,
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


def _sample_state() -> GameState:
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
    return state


def test_custom_emoji_placeholders_are_not_plain_text():
    assert _is_emoji_placeholder(empty_cell("white").placeholder)
    assert _is_emoji_placeholder(empty_cell("black").placeholder)
    assert _is_emoji_placeholder(piece("pawn", "white", "black").placeholder)
    assert _is_emoji_placeholder(evolution_point().placeholder)
    assert _is_emoji_placeholder(column_label("A").placeholder)
    assert _is_emoji_placeholder(row_label("8").placeholder)
    assert _is_emoji_placeholder(at_symbol().placeholder)
    assert _is_emoji_placeholder(divider().placeholder)
    assert column_label("A").placeholder == LABEL_PLACEHOLDER


def test_render_board_uses_tg_emoji_tags_not_raw_letters_as_entities():
    html = render_board(_sample_state())
    assert html.count("<tg-emoji") == 9 * 9 + 1  # divider + header + 8 rows
    assert 'emoji-id="' in html
    square = render_square(Position.from_algebraic("A8"), _sample_state())
    assert square.startswith("<tg-emoji")
    assert "A" not in square


def test_board_message_ends_with_exactly_one_divider_and_is_not_quoted():
    html = render_board(_sample_state())
    lines = html.split("\n")
    divider_html = divider().to_html()

    assert lines[0] != divider_html
    assert lines[-1] == divider_html
    assert html.count(divider_html) == 1
    assert html.endswith(divider_html)
    assert "<blockquote" not in html
    assert "expandable" not in html
    assert len(lines) == 10  # A–H header, 8 board rows, trailing divider
    assert divider_html not in "\n".join(lines[:-1])
    assert all("<tg-emoji" in line for line in lines[:-1])


def test_render_board_accepts_an_injected_divider_without_changing_cells():
    injected = EmojiRef(LABEL_PLACEHOLDER, "1111111111111111111")
    html = render_board(_sample_state(), divider=injected)
    assert html.endswith("\n" + injected.to_html())
    assert html.count(injected.to_html()) == 1
    assert not html.startswith(injected.to_html())
    assert "<blockquote" not in html
    square = render_square(Position.from_algebraic("A8"), _sample_state())
    assert injected.to_html() not in square
    assert divider().to_html() not in square


def test_divider_uses_a_real_configured_custom_emoji_id():
    """A made-up id is rejected by Telegram as Document_invalid."""

    assert divider().custom_emoji_id in all_custom_emoji_ids()
