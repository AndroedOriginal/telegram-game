from bot.emoji_assets import (
    LABEL_PLACEHOLDER,
    all_custom_emoji_ids,
    at_symbol,
    column_label,
    empty_cell,
    evolution_point,
    piece,
    row_label,
)
from bot.game.board import Position
from bot.game.models import GameState, GameStatus, Player, PieceColor, PieceType, Spawn
from bot.rendering.board_renderer import (
    board_rich_message_payload,
    render_board,
    render_board_heading6_html,
    render_square,
)


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
    assert column_label("A").placeholder == LABEL_PLACEHOLDER


def test_render_board_uses_tg_emoji_tags_not_raw_letters_as_entities():
    html = render_board(_sample_state())
    assert html.count("<tg-emoji") == 9 * 9
    assert 'emoji-id="' in html
    square = render_square(Position.from_algebraic("A8"), _sample_state())
    assert square.startswith("<tg-emoji")
    assert "A" not in square


def test_board_layout_is_header_plus_eight_rows_without_divider_or_quote():
    html = render_board(_sample_state())
    lines = html.split("\n")

    assert len(lines) == 9
    assert "<blockquote" not in html
    assert "expandable" not in html
    assert "######" not in html
    assert "<hr" not in html
    assert all("<tg-emoji" in line for line in lines)
    assert html.count("<tg-emoji") == 9 * 9


def test_board_heading6_html_wraps_the_entire_board_in_one_h6():
    body = render_board(_sample_state())
    html = render_board_heading6_html(_sample_state())

    assert html.startswith("<h6>")
    assert html.endswith("</h6>")
    assert html.count("<h6>") == 1
    assert html.count("</h6>") == 1
    assert "######" not in html
    assert "<blockquote" not in html
    assert html.count("<tg-emoji") == 9 * 9
    for line in body.split("\n"):
        assert line in html
    assert "<br/>".join(body.split("\n")) in html


def test_rich_message_payload_uses_heading6_html_not_literal_hashes():
    payload = board_rich_message_payload(_sample_state())
    assert set(payload) == {"html", "skip_entity_detection"}
    assert payload["skip_entity_detection"] is True
    assert payload["html"].startswith("<h6>")
    assert payload["html"].endswith("</h6>")
    assert "######" not in payload["html"]
    assert "markdown" not in payload
    assert "blocks" not in payload


def test_all_rendered_emoji_ids_are_configured():
    html = render_board(_sample_state())
    ids = set()
    needle = 'emoji-id="'
    start = 0
    while True:
        index = html.find(needle, start)
        if index < 0:
            break
        end = html.find('"', index + len(needle))
        ids.add(html[index + len(needle) : end])
        start = end + 1
    assert ids <= all_custom_emoji_ids()
    assert ids
