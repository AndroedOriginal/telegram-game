from bot.game.attacks import attacked_squares, alive_attackers_of, is_square_attacked_by
from bot.game.board import Position
from bot.game.models import PieceColor, PieceType, Player


def _pos(text: str) -> Position:
    return Position.from_algebraic(text)


def test_pawn_attacks_exactly_four_adjacent_diagonals():
    pos = _pos("D4")
    attacked = attacked_squares(PieceType.PAWN, pos, {pos})
    expected = {_pos("C5"), _pos("E5"), _pos("C3"), _pos("E3")}
    assert attacked == expected
    assert len(attacked) == 4


def test_pawn_does_not_attack_beyond_those_four_cells():
    pos = _pos("D4")
    attacked = attacked_squares(PieceType.PAWN, pos, {pos})
    beyond = {
        _pos("B6"),
        _pos("A7"),
        _pos("F6"),
        _pos("G7"),
        _pos("B2"),
        _pos("A1"),
        _pos("F2"),
        _pos("G1"),
        _pos("C4"),
        _pos("E4"),
        _pos("D5"),
        _pos("D3"),
        _pos("C6"),
        _pos("E6"),
    }
    assert attacked.isdisjoint(beyond)


def test_pawn_does_not_attack_an_entire_diagonal():
    pos = _pos("D4")
    attacked = attacked_squares(PieceType.PAWN, pos, {pos})
    assert _pos("C5") in attacked
    assert _pos("B6") not in attacked
    assert _pos("A7") not in attacked
    assert _pos("E5") in attacked
    assert _pos("F6") not in attacked
    assert _pos("G7") not in attacked


def test_pawn_attacks_respect_board_edge():
    pos = _pos("A1")
    attacked = attacked_squares(PieceType.PAWN, pos, {pos})
    assert attacked == {_pos("B2")}


def test_bishop_line_attacks_continue_until_blocked():
    pos = _pos("D4")
    attacked = attacked_squares(PieceType.BISHOP, pos, {pos})
    assert _pos("E5") in attacked
    assert _pos("F6") in attacked
    assert _pos("G7") in attacked
    assert _pos("H8") in attacked
    assert _pos("C3") in attacked
    assert _pos("A1") in attacked
    assert _pos("D5") not in attacked


def test_rook_line_attacks_continue_until_blocked():
    pos = _pos("D4")
    attacked = attacked_squares(PieceType.ROOK, pos, {pos})
    assert _pos("D8") in attacked
    assert _pos("A4") in attacked
    assert _pos("H4") in attacked
    assert _pos("D1") in attacked
    assert _pos("E5") not in attacked


def test_queen_line_attacks_combine_rook_and_bishop():
    pos = _pos("D4")
    attacked = attacked_squares(PieceType.QUEEN, pos, {pos})
    assert _pos("D8") in attacked
    assert _pos("A1") in attacked
    assert _pos("H8") in attacked
    assert _pos("A4") in attacked
    assert _pos("B3") not in attacked


def test_knight_attacks_all_eight_normal_destinations():
    pos = _pos("D4")
    attacked = attacked_squares(PieceType.KNIGHT, pos, {pos, _pos("C6")})
    expected = {
        _pos("C6"),
        _pos("E6"),
        _pos("B5"),
        _pos("F5"),
        _pos("B3"),
        _pos("F3"),
        _pos("C2"),
        _pos("E2"),
    }
    assert attacked == expected
    assert len(attacked) == 8


def test_blocking_prevents_bishop_rook_queen_attacks_past_a_piece():
    pos = _pos("D4")
    blocker = _pos("F6")
    occupied = {pos, blocker}

    bishop = attacked_squares(PieceType.BISHOP, pos, occupied)
    assert _pos("E5") in bishop
    assert blocker in bishop
    assert _pos("G7") not in bishop
    assert _pos("H8") not in bishop

    rook_blocker = _pos("D6")
    rook = attacked_squares(PieceType.ROOK, pos, {pos, rook_blocker})
    assert _pos("D5") in rook
    assert rook_blocker in rook
    assert _pos("D7") not in rook
    assert _pos("D8") not in rook

    queen = attacked_squares(PieceType.QUEEN, pos, occupied)
    assert blocker in queen
    assert _pos("G7") not in queen
    assert _pos("D8") in queen


def test_knight_attacks_ignore_blocking():
    pos = _pos("D4")
    occupied = {pos, _pos("D5"), _pos("C5"), _pos("C4")}
    attacked = attacked_squares(PieceType.KNIGHT, pos, occupied)
    assert _pos("C6") in attacked
    assert _pos("B5") in attacked


def test_is_square_attacked_by_helper():
    pos = _pos("D4")
    target = _pos("D8")
    assert is_square_attacked_by(PieceType.ROOK, pos, target, {pos})
    assert not is_square_attacked_by(PieceType.BISHOP, pos, target, {pos})
    assert not is_square_attacked_by(PieceType.PAWN, pos, _pos("B6"), {pos})


def test_alive_attackers_of_skips_dead_players_and_the_occupant():
    target = _pos("E5")
    pawn = Player(
        user_id=1,
        username="pawn",
        display_name="Pawn",
        color=PieceColor.WHITE,
        piece_type=PieceType.PAWN,
        position=_pos("D4"),
        alive=True,
    )
    dead_rook = Player(
        user_id=2,
        username="dead",
        display_name="Dead",
        color=PieceColor.BLACK,
        piece_type=PieceType.ROOK,
        position=_pos("E8"),
        alive=False,
    )
    mover = Player(
        user_id=3,
        username="mover",
        display_name="Mover",
        color=PieceColor.WHITE,
        piece_type=PieceType.BISHOP,
        position=target,
        alive=True,
    )
    occupied = {pawn.position, mover.position}
    attackers = alive_attackers_of(
        target,
        [pawn, dead_rook, mover],
        occupied,
        exclude_user_id=mover.user_id,
    )
    assert attackers == [pawn]
