from bot.game.models import PieceType, Player
from bot.game.rules import check_draw, check_victory, draw_announcement, victory_announcement


def make_player(user_id, piece_type, username=None):
    return Player(
        user_id=user_id,
        username=username or f"user{user_id}",
        display_name=f"User {user_id}",
        piece_type=piece_type,
    )


def test_draw_when_all_same_piece_type_is_not_automatic():
    players = [make_player(1, PieceType.BISHOP), make_player(2, PieceType.BISHOP)]
    assert check_draw(players) is False


def test_draw_with_three_knights_is_not_automatic():
    players = [make_player(i, PieceType.KNIGHT) for i in range(3)]
    assert check_draw(players) is False


def test_queen_queen_is_automatic_draw():
    players = [make_player(1, PieceType.QUEEN), make_player(2, PieceType.QUEEN)]
    assert check_draw(players) is True


def test_three_queens_is_automatic_draw():
    players = [make_player(i, PieceType.QUEEN) for i in range(3)]
    assert check_draw(players) is True


def test_queen_plus_rook_is_not_draw():
    players = [make_player(1, PieceType.QUEEN), make_player(2, PieceType.ROOK)]
    assert check_draw(players) is False


def test_no_draw_when_piece_types_differ():
    players = [make_player(1, PieceType.KNIGHT), make_player(2, PieceType.ROOK), make_player(3, PieceType.KNIGHT)]
    assert check_draw(players) is False


def test_no_draw_with_single_player():
    assert check_draw([make_player(1, PieceType.QUEEN)]) is False


def test_victory_with_single_remaining_player():
    winner = make_player(1, PieceType.QUEEN)
    assert check_victory([winner]) is winner


def test_no_victory_with_multiple_players():
    players = [make_player(1, PieceType.QUEEN), make_player(2, PieceType.ROOK)]
    assert check_victory(players) is None


def test_draw_announcement_two_players():
    players = [make_player(1, PieceType.BISHOP, "a"), make_player(2, PieceType.BISHOP, "b")]
    assert draw_announcement(players) == "Ничья между @a и @b."


def test_draw_announcement_three_players():
    players = [
        make_player(1, PieceType.KNIGHT, "a"),
        make_player(2, PieceType.KNIGHT, "b"),
        make_player(3, PieceType.KNIGHT, "c"),
    ]
    assert draw_announcement(players) == "Ничья между @a, @b... и @c."


def test_victory_announcement_text():
    winner = make_player(1, PieceType.QUEEN, "winner")
    assert victory_announcement(winner) == "\U0001f508 @winner побеждает."
