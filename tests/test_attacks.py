from bot.game.attacks import attacked_squares, is_square_attacked_by
from bot.game.board import Position
from bot.game.models import PieceType


def test_pawn_attacks_four_diagonals():
    pos = Position.from_algebraic("D4")
    attacked = attacked_squares(PieceType.PAWN, pos, {pos})
    expected = {
        Position.from_algebraic("C5"),
        Position.from_algebraic("E5"),
        Position.from_algebraic("C3"),
        Position.from_algebraic("E3"),
    }
    assert attacked == expected


def test_pawn_attacks_respect_board_edge():
    pos = Position.from_algebraic("A1")
    attacked = attacked_squares(PieceType.PAWN, pos, {pos})
    assert attacked == {Position.from_algebraic("B2")}


def test_bishop_attacks_stop_at_blocker_inclusive():
    pos = Position.from_algebraic("D4")
    blocker = Position.from_algebraic("F6")
    attacked = attacked_squares(PieceType.BISHOP, pos, {pos, blocker})
    assert Position.from_algebraic("E5") in attacked
    assert blocker in attacked
    assert Position.from_algebraic("G7") not in attacked


def test_rook_attacks_full_line_when_open():
    pos = Position.from_algebraic("D4")
    attacked = attacked_squares(PieceType.ROOK, pos, {pos})
    assert Position.from_algebraic("D8") in attacked
    assert Position.from_algebraic("A4") in attacked
    assert Position.from_algebraic("H4") in attacked
    assert Position.from_algebraic("D1") in attacked


def test_queen_attacks_combine_rook_and_bishop():
    pos = Position.from_algebraic("D4")
    attacked = attacked_squares(PieceType.QUEEN, pos, {pos})
    assert Position.from_algebraic("D8") in attacked  # rook-like
    assert Position.from_algebraic("A1") in attacked  # bishop-like
    assert Position.from_algebraic("B3") not in attacked  # not a queen line from D4


def test_knight_attacks_all_eight_l_shapes_regardless_of_movement_buttons():
    pos = Position.from_algebraic("D4")
    attacked = attacked_squares(PieceType.KNIGHT, pos, {pos})
    assert len(attacked) == 8
    assert Position.from_algebraic("B3") in attacked  # only reachable via full L-shape geometry
    assert Position.from_algebraic("F3") in attacked


def test_is_square_attacked_by_helper():
    pos = Position.from_algebraic("D4")
    target = Position.from_algebraic("D8")
    assert is_square_attacked_by(PieceType.ROOK, pos, target, {pos})
    assert not is_square_attacked_by(PieceType.BISHOP, pos, target, {pos})
