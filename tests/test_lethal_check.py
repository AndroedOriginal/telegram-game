"""Lethal check: moving onto a square attacked by any alive player is death."""
from bot.game import engine
from bot.game.board import Position
from bot.game.models import Direction, GameState, GameStatus, PieceColor, PieceType, Player
from bot.rendering.messages import info_message_text


def make_player(user_id, piece_type, position, username=None, color=PieceColor.WHITE):
    return Player(
        user_id=user_id,
        username=username or f"user{user_id}",
        display_name=f"User {user_id}",
        color=color,
        piece_type=piece_type,
        position=Position.from_algebraic(position) if isinstance(position, str) else position,
    )


def make_state(players, turn_order=None):
    return GameState(
        game_id=1,
        chat_id=-100,
        topic_id=1,
        status=GameStatus.ACTIVE,
        players=players,
        turn_order=turn_order or [p.user_id for p in players],
        turn_index=0,
        move_seq=0,
        status_line="\U0001f508 @user1 делает ход.",
    )


def _slide(state, user_id, direction, distance):
    opened = engine.select_direction(state, user_id, direction, state.move_seq)
    assert opened.ok and opened.pending_distances
    return engine.select_distance(state, user_id, direction, distance, state.move_seq)


def test_moving_onto_a_pawn_attack_dies():
    mover = make_player(1, PieceType.PAWN, "E4", username="victim")
    attacker = make_player(2, PieceType.PAWN, "D4", username="attacker")
    state = make_state([mover, attacker, make_player(3, PieceType.PAWN, "A1")])
    result = engine.select_direction(state, 1, Direction.UP, 0)
    assert result.died is True
    assert mover.alive is False
    assert attacker.alive is True
    assert any("ставит шах" in text and "@victim" in text for text in result.announcements)


def test_moving_onto_a_bishop_attack_dies():
    mover = make_player(1, PieceType.PAWN, "D3", username="victim")
    attacker = make_player(2, PieceType.BISHOP, "A1", username="attacker")
    state = make_state([mover, attacker, make_player(3, PieceType.PAWN, "H2")])
    result = engine.select_direction(state, 1, Direction.UP, 0)  # D3 -> D4, bishop A1 hits D4
    assert result.died is True
    assert mover.alive is False
    assert attacker.alive is True


def test_moving_onto_a_knight_attack_dies():
    mover = make_player(1, PieceType.PAWN, "D4", username="victim")
    attacker = make_player(2, PieceType.KNIGHT, "F6", username="attacker")
    state = make_state([mover, attacker, make_player(3, PieceType.PAWN, "A1")])
    result = engine.select_direction(state, 1, Direction.UP, 0)  # D4 -> D5, knight F6 hits D5
    assert result.died is True
    assert mover.alive is False
    assert attacker.alive is True


def test_moving_onto_a_rook_attack_dies():
    mover = make_player(1, PieceType.PAWN, "C4", username="victim")
    attacker = make_player(2, PieceType.ROOK, "D8", username="attacker")
    state = make_state([mover, attacker, make_player(3, PieceType.PAWN, "A1")])
    result = engine.select_direction(state, 1, Direction.RIGHT, 0)  # C4 -> D4
    assert result.died is True
    assert mover.alive is False
    assert attacker.alive is True


def test_moving_onto_a_queen_attack_dies():
    mover = make_player(1, PieceType.PAWN, "C4", username="victim")
    attacker = make_player(2, PieceType.QUEEN, "H8", username="attacker")
    state = make_state([mover, attacker, make_player(3, PieceType.PAWN, "A1")])
    result = engine.select_direction(state, 1, Direction.RIGHT, 0)  # C4 -> D4, queen H8 hits D4
    assert result.died is True
    assert mover.alive is False
    assert attacker.alive is True


def test_attack_is_calculated_after_the_move_not_the_old_square():
    mover = make_player(1, PieceType.ROOK, "A4", username="victim")
    attacker = make_player(2, PieceType.BISHOP, "H8", username="attacker")
    state = make_state([mover, attacker, make_player(3, PieceType.PAWN, "H1")])
    # A4 is not on the H8 bishop's diagonal; D4 is.
    result = _slide(state, 1, Direction.RIGHT, 3)  # A4 -> D4
    assert mover.position == Position.from_algebraic("D4")
    assert result.died is True
    assert mover.alive is False
    assert attacker.alive is True


def test_all_other_alive_players_are_checked_as_attackers():
    mover = make_player(1, PieceType.PAWN, "E4", username="victim")
    bystander = make_player(2, PieceType.PAWN, "A1", username="bystander")
    hidden = make_player(3, PieceType.QUEEN, "H8", username="queen")
    state = make_state([mover, bystander, hidden])
    result = engine.select_direction(state, 1, Direction.UP, 0)  # E4 -> E5, queen H8 hits E5
    assert result.died is True
    assert mover.alive is False
    assert bystander.alive is True
    assert hidden.alive is True
    assert any("@queen ставит шах @victim" in text for text in result.announcements)


def test_blocking_saves_a_landing_that_would_otherwise_be_in_check():
    mover = make_player(1, PieceType.PAWN, "C4", username="mover")
    blocker = make_player(2, PieceType.PAWN, "D6", username="blocker")
    attacker = make_player(3, PieceType.ROOK, "D8", username="rook")
    state = make_state([mover, blocker, attacker])
    result = engine.select_direction(state, 1, Direction.RIGHT, 0)  # C4 -> D4, D6 blocks D8
    assert result.died is False
    assert mover.alive is True
    assert mover.position == Position.from_algebraic("D4")


def test_dead_player_no_longer_attacks():
    mover = make_player(1, PieceType.PAWN, "D4", username="mover")
    corpse = make_player(2, PieceType.ROOK, "D8", username="corpse")
    corpse.alive = False
    witness = make_player(3, PieceType.PAWN, "A1", username="witness")
    state = make_state([mover, corpse, witness])
    result = engine.select_direction(state, 1, Direction.UP, 0)  # D4 -> D5
    assert result.died is False
    assert mover.alive is True
    assert corpse.alive is False


def test_dead_mover_does_not_kill_someone_they_would_have_attacked():
    mover = make_player(1, PieceType.ROOK, "D1", username="victim")
    pawn = make_player(2, PieceType.PAWN, "E6", username="attacker")
    other = make_player(3, PieceType.PAWN, "D8", username="other")
    state = make_state([mover, pawn, other])
    result = _slide(state, 1, Direction.UP, 4)  # D1 -> D5: pawn E6 attacks D5; D8 is on the rook file
    assert result.died is True
    assert mover.alive is False
    assert pawn.alive is True
    assert other.alive is True


def test_killed_player_is_removed_from_board_and_game_information():
    mover = make_player(1, PieceType.PAWN, "E4", username="victim")
    attacker = make_player(2, PieceType.PAWN, "D4", username="attacker")
    witness = make_player(3, PieceType.PAWN, "A1", username="witness")
    state = make_state([mover, attacker, witness])
    engine.select_direction(state, 1, Direction.UP, 0)

    assert mover.alive is False
    assert mover not in state.active_players()
    assert Position.from_algebraic("E5") not in state.occupied_positions()
    text = info_message_text(state)
    assert "@victim:" not in text
    assert "@attacker:" in text
    assert "@witness:" in text
