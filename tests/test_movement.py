from bot.game.board import Position
from bot.game.models import Direction
from bot.game.movement import (
    knight_jump_destination,
    pawn_attack_target,
    pawn_step_destination,
    sliding_destinations,
)


def test_pawn_step_cardinal_moves_one_square():
    pos = Position.from_algebraic("D4")
    dest = pawn_step_destination(pos, Direction.UP, set())
    assert dest == Position.from_algebraic("D5")


def test_pawn_step_blocked_by_occupied_cell():
    pos = Position.from_algebraic("D4")
    occupied = {Position.from_algebraic("D5")}
    assert pawn_step_destination(pos, Direction.UP, occupied) is None


def test_pawn_step_out_of_bounds():
    pos = Position.from_algebraic("D8")
    assert pawn_step_destination(pos, Direction.UP, set()) is None


def test_pawn_diagonal_is_not_a_step_direction():
    pos = Position.from_algebraic("D4")
    assert pawn_step_destination(pos, Direction.UP_LEFT, set()) is None


def test_pawn_attack_target_diagonal():
    pos = Position.from_algebraic("D4")
    assert pawn_attack_target(pos, Direction.UP_LEFT) == Position.from_algebraic("C5")
    assert pawn_attack_target(pos, Direction.UP_RIGHT) == Position.from_algebraic("E5")
    assert pawn_attack_target(pos, Direction.DOWN_LEFT) == Position.from_algebraic("C3")
    assert pawn_attack_target(pos, Direction.DOWN_RIGHT) == Position.from_algebraic("E3")


def test_sliding_destinations_open_board():
    pos = Position.from_algebraic("D4")
    dests = sliding_destinations(pos, Direction.UP, set())
    assert [p.to_algebraic() for p in dests] == ["D5", "D6", "D7", "D8"]


def test_sliding_destinations_stops_before_blocker():
    pos = Position.from_algebraic("D4")
    occupied = {Position.from_algebraic("D7")}
    dests = sliding_destinations(pos, Direction.UP, occupied)
    assert [p.to_algebraic() for p in dests] == ["D5", "D6"]


def test_sliding_destinations_diagonal():
    pos = Position.from_algebraic("D4")
    dests = sliding_destinations(pos, Direction.UP_RIGHT, set())
    assert [p.to_algebraic() for p in dests] == ["E5", "F6", "G7", "H8"]


def test_sliding_destinations_immediately_blocked_is_empty():
    pos = Position.from_algebraic("D4")
    occupied = {Position.from_algebraic("D5")}
    assert sliding_destinations(pos, Direction.UP, occupied) == []


def test_knight_jump_destination():
    pos = Position.from_algebraic("D4")
    assert knight_jump_destination(pos, Direction.UP_LEFT, set()) == Position.from_algebraic("C6")
    assert knight_jump_destination(pos, Direction.UP_RIGHT, set()) == Position.from_algebraic("E6")
    assert knight_jump_destination(pos, Direction.DOWN_LEFT, set()) == Position.from_algebraic("C2")
    assert knight_jump_destination(pos, Direction.DOWN_RIGHT, set()) == Position.from_algebraic("E2")


def test_knight_jump_blocked_by_occupied_destination():
    pos = Position.from_algebraic("D4")
    occupied = {Position.from_algebraic("C6")}
    assert knight_jump_destination(pos, Direction.UP_LEFT, occupied) is None


def test_knight_jump_out_of_bounds():
    pos = Position.from_algebraic("A1")
    assert knight_jump_destination(pos, Direction.DOWN_LEFT, set()) is None
