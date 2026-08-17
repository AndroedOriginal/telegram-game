import copy

from bot.game import engine
from bot.game.board import Position
from bot.game.models import (
    Direction,
    GameState,
    GameStatus,
    PieceColor,
    PieceType,
    Player,
    Spawn,
)


def make_player(user_id, piece_type, position, username=None, color=PieceColor.WHITE):
    return Player(
        user_id=user_id,
        username=username or f"user{user_id}",
        display_name=f"User {user_id}",
        color=color,
        piece_type=piece_type,
        position=Position.from_algebraic(position) if isinstance(position, str) else position,
    )


def make_state(players, spawns=None, move_seq=0):
    state = GameState(
        game_id=1,
        chat_id=-100,
        topic_id=1,
        status=GameStatus.ACTIVE,
        players=players,
        spawns=spawns or [],
        turn_order=[p.user_id for p in players],
        turn_index=0,
        move_seq=move_seq,
    )
    return state


def test_pawn_move_advances_turn_and_updates_position():
    a = make_player(1, PieceType.PAWN, "D4")
    b = make_player(2, PieceType.PAWN, "A1")
    state = make_state([a, b])

    result = engine.select_direction(state, 1, Direction.UP, state.move_seq)

    assert result.ok
    assert result.move_completed
    assert a.position == Position.from_algebraic("D5")
    assert state.current_player().user_id == 2
    assert state.move_seq == 1


def test_wrong_turn_player_is_rejected_and_state_unchanged():
    a = make_player(1, PieceType.PAWN, "D4")
    b = make_player(2, PieceType.PAWN, "A1")
    state = make_state([a, b])
    snapshot = copy.deepcopy(state)

    result = engine.select_direction(state, 2, Direction.UP, state.move_seq)

    assert not result.ok
    assert result.reason == "not_your_turn"
    assert state.players == snapshot.players
    assert state.turn_index == snapshot.turn_index


def test_invalid_move_out_of_bounds_does_not_mutate_state():
    a = make_player(1, PieceType.PAWN, "D8")
    b = make_player(2, PieceType.PAWN, "A1")
    state = make_state([a, b])
    snapshot = copy.deepcopy(state)

    result = engine.select_direction(state, 1, Direction.UP, state.move_seq)

    assert not result.ok
    assert result.invalid
    assert result.reason == engine.INVALID_MOVE_MESSAGE
    assert a.position == snapshot.players[0].position
    assert state.turn_index == 0
    assert state.move_seq == 0


def test_invalid_move_onto_occupied_cell():
    a = make_player(1, PieceType.PAWN, "D4")
    b = make_player(2, PieceType.PAWN, "D5")
    state = make_state([a, b])

    result = engine.select_direction(state, 1, Direction.UP, state.move_seq)

    assert not result.ok
    assert result.invalid
    assert a.position == Position.from_algebraic("D4")


def test_pawn_diagonal_attack_requires_enemy_present():
    a = make_player(1, PieceType.PAWN, "D4")
    b = make_player(2, PieceType.PAWN, "A1")
    state = make_state([a, b])

    result = engine.select_direction(state, 1, Direction.UP_LEFT, state.move_seq)

    assert not result.ok
    assert result.invalid


def test_pawn_diagonal_attack_eliminates_enemy_and_attacker_stays():
    a = make_player(1, PieceType.PAWN, "D4")
    b = make_player(2, PieceType.PAWN, "C5")  # up-left diagonal of D4
    state = make_state([a, b])

    result = engine.select_direction(state, 1, Direction.UP_LEFT, state.move_seq)

    assert result.ok
    assert result.move_completed
    assert a.position == Position.from_algebraic("D4")  # attacker did not move
    assert b.alive is False
    assert state.active_players() == [a]
    assert result.victory  # only one player remains


def test_bishop_direction_selection_opens_distance_menu():
    a = make_player(1, PieceType.BISHOP, "D4")
    b = make_player(2, PieceType.PAWN, "A1")
    state = make_state([a, b])

    result = engine.select_direction(state, 1, Direction.UP_RIGHT, state.move_seq)

    assert result.ok
    assert result.pending_distances == [1, 2, 3, 4]  # D4 -> E5,F6,G7,H8
    assert state.pending_action is not None
    assert a.position == Position.from_algebraic("D4")  # not moved yet


def test_bishop_distance_selection_moves_piece():
    a = make_player(1, PieceType.BISHOP, "D4")
    b = make_player(2, PieceType.PAWN, "A1")
    state = make_state([a, b])

    dir_result = engine.select_direction(state, 1, Direction.UP_RIGHT, state.move_seq)
    seq = state.move_seq
    result = engine.select_distance(state, 1, Direction.UP_RIGHT, 3, seq)

    assert result.ok
    assert a.position == Position.from_algebraic("G7")
    assert state.pending_action is None
    assert state.current_player().user_id == 2


def test_bishop_blocked_reduces_available_distances():
    a = make_player(1, PieceType.BISHOP, "D4")
    blocker = make_player(2, PieceType.PAWN, "F6")
    state = make_state([a, blocker])

    result = engine.select_direction(state, 1, Direction.UP_RIGHT, state.move_seq)

    assert result.ok
    assert result.pending_distances == [1]  # only E5 is reachable before the blocker


def test_direction_with_no_legal_moves_is_invalid():
    a = make_player(1, PieceType.BISHOP, "A1")
    blockers = [
        make_player(2, PieceType.PAWN, "B2"),
    ]
    state = make_state([a] + blockers)

    result = engine.select_direction(state, 1, Direction.UP_RIGHT, state.move_seq)

    assert not result.ok
    assert result.invalid
    assert state.pending_action is None


def test_rook_cannot_pass_through_a_piece():
    a = make_player(1, PieceType.ROOK, "D1")
    blocker = make_player(2, PieceType.PAWN, "D4")
    state = make_state([a, blocker])

    result = engine.select_direction(state, 1, Direction.UP, state.move_seq)

    assert result.ok
    assert result.pending_distances == [1, 2]  # D2, D3 only


def test_knight_jump_moves_immediately_without_distance_menu():
    a = make_player(1, PieceType.KNIGHT, "D4")
    b = make_player(2, PieceType.PAWN, "A1")
    state = make_state([a, b])

    result = engine.select_direction(state, 1, Direction.UP_LEFT, state.move_seq)

    assert result.ok
    assert result.move_completed
    assert result.pending_distances is None
    assert a.position == Position.from_algebraic("C6")


def test_knight_invalid_destination():
    a = make_player(1, PieceType.KNIGHT, "A1")
    b = make_player(2, PieceType.PAWN, "H8")
    state = make_state([a, b])

    result = engine.select_direction(state, 1, Direction.DOWN_LEFT, state.move_seq)

    assert not result.ok
    assert result.invalid


def test_stale_pending_action_is_rejected():
    a = make_player(1, PieceType.BISHOP, "D4")
    b = make_player(2, PieceType.PAWN, "A1")
    state = make_state([a, b])

    engine.select_direction(state, 1, Direction.UP_RIGHT, state.move_seq)  # seq becomes 1
    stale_seq = 0

    result = engine.select_distance(state, 1, Direction.UP_RIGHT, 2, stale_seq)

    assert not result.ok
    assert result.reason == "stale"
    assert a.position == Position.from_algebraic("D4")


def test_selecting_a_new_direction_invalidates_previous_menu():
    a = make_player(1, PieceType.BISHOP, "D4")
    b = make_player(2, PieceType.PAWN, "A1")
    state = make_state([a, b])

    first = engine.select_direction(state, 1, Direction.UP_RIGHT, state.move_seq)
    first_seq = state.move_seq
    second = engine.select_direction(state, 1, Direction.DOWN_RIGHT, state.move_seq)

    assert first.ok and second.ok

    stale_attempt = engine.select_distance(state, 1, Direction.UP_RIGHT, 1, first_seq)
    assert not stale_attempt.ok
    assert stale_attempt.reason == "stale"


def test_death_by_moving_into_attack():
    mover = make_player(1, PieceType.PAWN, "D4")
    attacker = make_player(2, PieceType.ROOK, "D8")
    bystander = make_player(3, PieceType.PAWN, "A1")
    state = make_state([mover, attacker, bystander])

    result = engine.select_direction(state, 1, Direction.UP, state.move_seq)

    assert result.ok
    assert result.died is True
    assert mover.alive is False
    assert mover.is_active is False
    # Turn should skip the now-dead mover and move on to the next active player.
    assert state.current_player().user_id == 2


def test_mutual_attack_last_mover_dies():
    # Two rooks facing each other on the same file with a gap; mover advances
    # into direct line of sight and dies even though it also attacks back.
    mover = make_player(1, PieceType.ROOK, "D1")
    other = make_player(2, PieceType.ROOK, "D8")
    state = make_state([mover, other])

    result = engine.select_direction(state, 1, Direction.UP, state.move_seq)
    seq = state.move_seq
    result = engine.select_distance(state, 1, Direction.UP, 6, seq)  # D1 -> D7, adjacent to D8

    assert result.ok
    assert result.died is True
    assert mover.alive is False
    assert other.alive is True
    assert result.victory is True


def test_check_announcement_emitted_when_move_threatens_another_player():
    mover = make_player(1, PieceType.ROOK, "D1", username="rooker")
    victim = make_player(2, PieceType.PAWN, "D8", username="victim")
    safe = make_player(3, PieceType.PAWN, "A1", username="safe")
    state = make_state([mover, victim, safe])

    result = engine.select_direction(state, 1, Direction.UP, state.move_seq)
    seq = state.move_seq
    result = engine.select_distance(state, 1, Direction.UP, 5, seq)  # D1 -> D6, attacks D8 down the file

    assert result.ok
    assert result.died is False
    assert any("ставит шах" in a and "@victim" in a for a in result.announcements)


def test_evolution_on_reaching_another_players_spawn():
    a = make_player(1, PieceType.PAWN, "C4")
    b = make_player(2, PieceType.PAWN, "A1")
    spawn = Spawn(owner_user_id=2, position=Position.from_algebraic("D4"), activated=False)
    state = make_state([a, b], spawns=[spawn])

    result = engine.select_direction(state, 1, Direction.RIGHT, state.move_seq)

    assert result.ok
    assert result.evolved is True
    assert a.piece_type == PieceType.BISHOP
    assert any("меняет фигуру" in msg for msg in result.announcements)
    assert spawn.activated is True
    assert spawn.position != Position.from_algebraic("D4")  # relocated


def test_owner_cannot_use_own_unactivated_spawn():
    a = make_player(1, PieceType.PAWN, "C4")
    b = make_player(2, PieceType.PAWN, "A1")
    spawn = Spawn(owner_user_id=1, position=Position.from_algebraic("D4"), activated=False)
    state = make_state([a, b], spawns=[spawn])

    result = engine.select_direction(state, 1, Direction.RIGHT, state.move_seq)

    assert result.ok
    assert result.evolved is False
    assert a.piece_type == PieceType.PAWN
    assert spawn.activated is False
    assert spawn.position == Position.from_algebraic("D4")  # not relocated: not "used"


def test_owner_can_use_previously_activated_spawn():
    a = make_player(1, PieceType.PAWN, "C4")
    b = make_player(2, PieceType.PAWN, "A1")
    spawn = Spawn(owner_user_id=1, position=Position.from_algebraic("D4"), activated=True)
    state = make_state([a, b], spawns=[spawn])

    result = engine.select_direction(state, 1, Direction.RIGHT, state.move_seq)

    assert result.ok
    assert result.evolved is True
    assert a.piece_type == PieceType.BISHOP


def test_draw_when_remaining_players_share_piece_type():
    a = make_player(1, PieceType.KNIGHT, "C4")
    b = make_player(2, PieceType.KNIGHT, "A1")
    state = make_state([a, b])

    result = engine.select_direction(state, 1, Direction.UP_LEFT, state.move_seq)

    assert result.ok
    assert result.draw is True
    assert state.status == GameStatus.FINISHED
    assert set(state.draw_user_ids) == {1, 2}


def test_victory_when_one_player_remains():
    a = make_player(1, PieceType.PAWN, "D4")
    b = make_player(2, PieceType.PAWN, "C5")
    state = make_state([a, b])

    result = engine.select_direction(state, 1, Direction.UP_LEFT, state.move_seq)

    assert result.victory is True
    assert state.status == GameStatus.FINISHED
    assert state.winner_user_id == 1


def test_player_leaving_mid_game_causes_victory_for_sole_survivor():
    a = make_player(1, PieceType.PAWN, "D4")
    b = make_player(2, PieceType.PAWN, "A1")
    state = make_state([a, b])

    result = engine.leave_game(state, 1)

    assert result.ok
    assert any("покидает игру" in msg for msg in result.announcements)
    assert result.victory is True
    assert state.winner_user_id == 2


def test_player_leaving_advances_turn_if_it_was_their_turn():
    a = make_player(1, PieceType.PAWN, "D4")
    b = make_player(2, PieceType.PAWN, "A1")
    c = make_player(3, PieceType.PAWN, "H8")
    state = make_state([a, b, c])

    result = engine.leave_game(state, 1)

    assert result.ok
    assert result.victory is False
    assert result.draw is False
    assert state.current_player().user_id == 2


def test_left_player_cannot_act():
    a = make_player(1, PieceType.PAWN, "D4")
    b = make_player(2, PieceType.PAWN, "A1")
    c = make_player(3, PieceType.PAWN, "H8")
    state = make_state([a, b, c])
    engine.leave_game(state, 2)  # b leaves, but it is not currently their turn

    result = engine.select_direction(state, 2, Direction.UP, state.move_seq)
    assert not result.ok
    assert result.reason == "not_your_turn"


def test_lobby_join_and_leave_and_start():
    state = GameState(game_id=1, chat_id=-1, topic_id=None)

    r1 = engine.join_lobby(state, 1, "alice", "Alice")
    r2 = engine.join_lobby(state, 2, "bob", "Bob")
    assert r1.ok and r2.ok
    assert len(state.players) == 2

    dup = engine.join_lobby(state, 1, "alice", "Alice")
    assert not dup.ok
    assert dup.reason == "already_joined"

    start = engine.start_game(state)
    assert start.ok
    assert state.status == GameStatus.ACTIVE
    assert len(state.turn_order) == 2
    assert all(p.piece_type == PieceType.PAWN for p in state.players)
    assert len(state.spawns) == 2


def test_lobby_cannot_start_with_fewer_than_two_players():
    state = GameState(game_id=1, chat_id=-1, topic_id=None)
    engine.join_lobby(state, 1, "alice", "Alice")

    result = engine.start_game(state)
    assert not result.ok
    assert result.reason == "not_enough_players"


def test_lobby_max_players_enforced():
    state = GameState(game_id=1, chat_id=-1, topic_id=None)
    for i in range(8):
        assert engine.join_lobby(state, i, f"u{i}", f"U{i}").ok
    overflow = engine.join_lobby(state, 100, "extra", "Extra")
    assert not overflow.ok
    assert overflow.reason == "lobby_full"
