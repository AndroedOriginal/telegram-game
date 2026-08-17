import random

from bot.game.attacks import attacked_squares
from bot.game.board import Position, is_adjacent
from bot.game.models import PieceType, Spawn
from bot.game.spawns import (
    find_valid_spawn_position,
    generate_initial_layout,
    relocate_spawn,
)


def test_find_valid_spawn_position_avoids_players_and_spawns():
    rng = random.Random(1)
    players = {Position.from_algebraic("A1")}
    spawns = {Position.from_algebraic("B2")}
    for _ in range(200):
        pos = find_valid_spawn_position(players, spawns, rng)
        assert pos not in players
        assert pos not in spawns


def test_relocate_spawn_moves_to_new_valid_cell():
    rng = random.Random(2)
    spawn = Spawn(owner_user_id=1, position=Position.from_algebraic("A1"))
    other_spawn = Spawn(owner_user_id=2, position=Position.from_algebraic("H8"))
    all_spawns = [spawn, other_spawn]
    player_positions = {Position.from_algebraic("A1"), Position.from_algebraic("C3")}

    relocate_spawn(spawn, all_spawns, player_positions, rng)

    assert spawn.position != Position.from_algebraic("A1")
    assert spawn.position not in player_positions
    assert spawn.position != other_spawn.position


def test_generate_initial_layout_is_valid_for_many_players():
    rng = random.Random(42)
    user_ids = list(range(8))
    layout = generate_initial_layout(user_ids, rng)

    assert len(layout) == 8
    positions = list(layout.values())
    assert len(set(positions)) == 8  # no overlaps

    for i, pos_a in enumerate(positions):
        for pos_b in positions[i + 1 :]:
            assert not is_adjacent(pos_a, pos_b)

    occupied = set(positions)
    for pos in positions:
        others = occupied - {pos}
        for other in others:
            assert pos not in attacked_squares(PieceType.PAWN, other, occupied)


def test_generate_initial_layout_two_players():
    rng = random.Random(7)
    layout = generate_initial_layout([100, 200], rng)
    assert len(layout) == 2
    assert layout[100] != layout[200]
