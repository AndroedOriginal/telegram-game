"""Owner unlock of own spawn: Case A (evolve on foreign point) and Case B
(another player evolves on your point). Permission is on spawn identity."""
from bot.game import engine
from bot.game.board import Position
from bot.game.evolution import can_use_spawn
from bot.game.models import (
    Direction,
    GameState,
    GameStatus,
    PieceColor,
    PieceType,
    Player,
    Spawn,
)
from bot.game.spawns import relocate_spawn
from bot.database.repository import _spawn_from_dict, _spawn_to_dict


def make_player(user_id, piece_type, position, username=None, color=PieceColor.WHITE):
    return Player(
        user_id=user_id,
        username=username or f"user{user_id}",
        display_name=f"User {user_id}",
        color=color,
        piece_type=piece_type,
        position=Position.from_algebraic(position) if isinstance(position, str) else position,
    )


def make_state(players, spawns=None, turn_order=None):
    return GameState(
        game_id=1,
        chat_id=-100,
        topic_id=1,
        status=GameStatus.ACTIVE,
        players=players,
        spawns=spawns or [],
        turn_order=turn_order or [p.user_id for p in players],
        turn_index=0,
        move_seq=0,
    )


def _owner_lands_on_spawn(state, owner, spawn, piece_type=PieceType.PAWN):
    """Place ``owner`` on a safe square and step onto ``spawn`` with a pawn."""

    spawn.position = Position.from_algebraic("E4")
    owner.position = Position.from_algebraic("D4")
    owner.piece_type = piece_type
    for other in state.active_players():
        if other.user_id != owner.user_id:
            other.position = Position.from_algebraic("A8")
            other.piece_type = PieceType.PAWN
    for other_spawn in state.spawns:
        if other_spawn is not spawn and other_spawn.position in {
            Position.from_algebraic("E4"),
            Position.from_algebraic("D4"),
            Position.from_algebraic("A8"),
        }:
            other_spawn.position = Position.from_algebraic("H1")
    state.turn_order = [owner.user_id] + [p.user_id for p in state.players if p.user_id != owner.user_id]
    state.turn_index = 0
    state.pending_action = None
    state.status = GameStatus.ACTIVE
    return engine.select_direction(state, owner.user_id, Direction.RIGHT, state.move_seq)


def test_1_owner_denied_on_own_spawn_at_start():
    x = make_player(1, PieceType.PAWN, "C4")
    y = make_player(2, PieceType.PAWN, "B1")
    spawn_x = Spawn(owner_user_id=1, position=Position.from_algebraic("D4"), activated_by_other=False)
    state = make_state([x, y], spawns=[spawn_x])

    result = engine.select_direction(state, 1, Direction.RIGHT, state.move_seq)

    assert result.ok
    assert result.evolved is False
    assert x.piece_type == PieceType.PAWN
    assert spawn_x.activated_by_other is False
    assert can_use_spawn(x, spawn_x) is False


def test_2_evolving_on_foreign_spawn_unlocks_own():
    x = make_player(1, PieceType.PAWN, "C4")
    y = make_player(2, PieceType.PAWN, "B1")
    spawn_x = Spawn(owner_user_id=1, position=Position.from_algebraic("H8"), activated_by_other=False)
    spawn_y = Spawn(owner_user_id=2, position=Position.from_algebraic("D4"), activated_by_other=False)
    state = make_state([x, y], spawns=[spawn_x, spawn_y])

    result = engine.select_direction(state, 1, Direction.RIGHT, state.move_seq)

    assert result.evolved is True
    assert x.piece_type == PieceType.BISHOP
    assert spawn_x.activated_by_other is True
    assert can_use_spawn(x, spawn_x) is True
    assert state.get_spawn_for_owner(1) is spawn_x


def test_3_other_player_evolving_on_x_unlocks_x():
    x = make_player(1, PieceType.PAWN, "B1")
    y = make_player(2, PieceType.PAWN, "C4")
    spawn_x = Spawn(owner_user_id=1, position=Position.from_algebraic("D4"), activated_by_other=False)
    spawn_y = Spawn(owner_user_id=2, position=Position.from_algebraic("H8"), activated_by_other=False)
    state = make_state([y, x], spawns=[spawn_x, spawn_y], turn_order=[2, 1])

    result = engine.select_direction(state, 2, Direction.RIGHT, state.move_seq)

    assert result.evolved is True
    assert spawn_x.activated_by_other is True
    assert can_use_spawn(x, spawn_x) is True
    assert spawn_y.activated_by_other is True  # Case A for Y as well


def test_4_unlock_survives_relocation_after_other_evolves_on_x():
    x = make_player(1, PieceType.PAWN, "B1")
    y = make_player(2, PieceType.PAWN, "C4")
    spawn_x = Spawn(owner_user_id=1, position=Position.from_algebraic("D4"), activated_by_other=False)
    spawn_y = Spawn(owner_user_id=2, position=Position.from_algebraic("H8"), activated_by_other=False)
    state = make_state([y, x], spawns=[spawn_x, spawn_y], turn_order=[2, 1])

    engine.select_direction(state, 2, Direction.RIGHT, state.move_seq)
    assert spawn_x.activated_by_other is True
    assert spawn_x.position != Position.from_algebraic("D4")

    result = _owner_lands_on_spawn(state, x, spawn_x)
    assert result.evolved is True
    assert x.piece_type == PieceType.BISHOP
    assert spawn_x.activated_by_other is True


def test_5_unlock_via_foreign_evolve_survives_own_spawn_relocation():
    x = make_player(1, PieceType.PAWN, "C4")
    y = make_player(2, PieceType.PAWN, "B1")
    spawn_x = Spawn(owner_user_id=1, position=Position.from_algebraic("H8"), activated_by_other=False)
    spawn_y = Spawn(owner_user_id=2, position=Position.from_algebraic("D4"), activated_by_other=False)
    state = make_state([x, y], spawns=[spawn_x, spawn_y])

    engine.select_direction(state, 1, Direction.RIGHT, state.move_seq)
    assert spawn_x.activated_by_other is True

    old = spawn_x.position
    relocate_spawn(spawn_x, state.spawns, state.occupied_positions())
    assert spawn_x.position != old
    assert spawn_x.activated_by_other is True
    assert can_use_spawn(x, spawn_x) is True

    result = _owner_lands_on_spawn(state, x, spawn_x)
    assert result.evolved is True
    assert spawn_x.activated_by_other is True


def test_6_permission_stays_unlocked_across_multiple_relocations():
    x = make_player(1, PieceType.PAWN, "C4")
    y = make_player(2, PieceType.PAWN, "B1")
    spawn_x = Spawn(owner_user_id=1, position=Position.from_algebraic("H8"), activated_by_other=False)
    spawn_y = Spawn(owner_user_id=2, position=Position.from_algebraic("D4"), activated_by_other=False)
    state = make_state([x, y], spawns=[spawn_x, spawn_y])

    engine.select_direction(state, 1, Direction.RIGHT, state.move_seq)
    assert spawn_x.activated_by_other is True

    for _ in range(4):
        relocate_spawn(spawn_x, state.spawns, state.occupied_positions())
        assert spawn_x.activated_by_other is True
        assert spawn_x.owner_user_id == 1
        assert can_use_spawn(x, spawn_x) is True


def test_7_no_unlock_without_either_condition():
    x = make_player(1, PieceType.PAWN, "C4")
    y = make_player(2, PieceType.PAWN, "B1")
    spawn_x = Spawn(owner_user_id=1, position=Position.from_algebraic("H8"), activated_by_other=False)
    state = make_state([x, y], spawns=[spawn_x])

    engine.select_direction(state, 1, Direction.UP, state.move_seq)

    assert spawn_x.activated_by_other is False
    assert can_use_spawn(x, spawn_x) is False
    assert x.piece_type == PieceType.PAWN


def test_8_unlock_belongs_to_spawn_identity_not_coordinate():
    x = make_player(1, PieceType.PAWN, "C4")
    y = make_player(2, PieceType.PAWN, "B1")
    spawn_x = Spawn(owner_user_id=1, position=Position.from_algebraic("H8"), activated_by_other=False)
    spawn_y = Spawn(owner_user_id=2, position=Position.from_algebraic("D4"), activated_by_other=False)
    state = make_state([x, y], spawns=[spawn_x, spawn_y])

    engine.select_direction(state, 1, Direction.RIGHT, state.move_seq)
    old_coord = spawn_x.position
    spawn_x.position = Position.from_algebraic("A2")

    assert state.get_spawn_for_owner(1) is spawn_x
    assert state.get_spawn_at(Position.from_algebraic("A2")) is spawn_x
    assert state.get_spawn_at(old_coord) is None
    assert can_use_spawn(x, spawn_x) is True

    impostor = Spawn(owner_user_id=1, position=old_coord, activated_by_other=False)
    assert can_use_spawn(x, impostor) is False


def test_queen_evolution_unlocks_own_spawn_then_removes_used_point():
    x = make_player(1, PieceType.ROOK, "C4")
    y = make_player(2, PieceType.PAWN, "B1")
    spawn_x = Spawn(owner_user_id=1, position=Position.from_algebraic("H8"), activated_by_other=False)
    spawn_y = Spawn(owner_user_id=2, position=Position.from_algebraic("D4"), activated_by_other=False)
    state = make_state([x, y], spawns=[spawn_x, spawn_y])

    opened = engine.select_direction(state, 1, Direction.RIGHT, 0)
    assert opened.pending_distances
    result = engine.select_distance(state, 1, Direction.RIGHT, 1, state.move_seq)

    assert result.evolved is True
    assert x.piece_type == PieceType.QUEEN
    assert spawn_y not in state.spawns
    assert state.get_spawn_for_owner(2) is None
    assert not any(s.position == Position.from_algebraic("D4") for s in state.spawns)
    remaining = state.get_spawn_for_owner(1)
    assert remaining is spawn_x
    assert remaining.activated_by_other is True
    assert remaining.owner_user_id == 1


def test_spawn_json_round_trip_preserves_unlock_and_reads_legacy_key():
    spawn = Spawn(owner_user_id=7, position=Position.from_algebraic("C3"), activated_by_other=True)
    payload = _spawn_to_dict(spawn)
    assert payload["activated_by_other"] is True
    restored = _spawn_from_dict(payload)
    assert restored.owner_user_id == 7
    assert restored.position == Position.from_algebraic("C3")
    assert restored.activated_by_other is True

    legacy = _spawn_from_dict(
        {"owner_user_id": 7, "position": [2, 2], "activated": True}
    )
    assert legacy.activated_by_other is True
