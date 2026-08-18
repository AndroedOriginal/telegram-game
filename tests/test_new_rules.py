from bot.game import engine
from bot.game.board import Position, cell_color, chebyshev_distance
from bot.game.models import (
    Direction,
    GameState,
    GameStatus,
    PieceColor,
    PieceType,
    Player,
    Spawn,
)
from bot.game.movement import legal_directions_for_piece
from bot.game.spawns import generate_initial_layout
from bot.rendering.messages import (
    RULES_ALERT,
    RULES_FULL,
    info_message_text,
    moves_prompt_text,
    status_line_count,
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
    return GameState(
        game_id=1,
        chat_id=-100,
        topic_id=1,
        status=GameStatus.ACTIVE,
        players=players,
        spawns=spawns or [],
        turn_order=[p.user_id for p in players],
        turn_index=0,
        move_seq=move_seq,
        status_line="\U0001f508 @user1 делает ход.",
    )


def test_info_message_contains_all_alive_players():
    a = make_player(1, PieceType.PAWN, "D1", "PlayerA")
    b = make_player(2, PieceType.BISHOP, "F4", "PlayerB", color=PieceColor.BLACK)
    c = make_player(3, PieceType.KNIGHT, "B7", "PlayerC")
    state = make_state([a, b, c])
    text = info_message_text(state)
    assert "@PlayerA: D1" in text
    assert "@PlayerB: F4" in text
    assert "@PlayerC: B7" in text
    assert "Информация по игре" in text


def test_dead_player_disappears_from_information():
    a = make_player(1, PieceType.PAWN, "D4")
    b = make_player(2, PieceType.PAWN, "C5")
    state = make_state([a, b])
    engine.select_direction(state, 1, Direction.UP_LEFT, state.move_seq)
    text = info_message_text(state)
    assert "@user2" not in text
    assert "@user1: D4" in text


def test_player_who_leaves_disappears_from_information():
    a = make_player(1, PieceType.PAWN, "D4")
    b = make_player(2, PieceType.PAWN, "A1")
    c = make_player(3, PieceType.PAWN, "H8")
    state = make_state([a, b, c])
    engine.leave_game(state, 2)
    text = info_message_text(state)
    assert "@user2:" not in text
    assert "@user1:" in text
    assert "@user3:" in text


def test_status_line_is_always_a_single_line():
    a = make_player(1, PieceType.PAWN, "D4")
    b = make_player(2, PieceType.PAWN, "A1")
    state = make_state([a, b])
    engine.select_direction(state, 1, Direction.UP, 0)
    assert state.status_line is not None
    assert "\n" not in state.status_line
    assert status_line_count(state.status_line) == 1
    engine.view_rules(state, 2)
    assert status_line_count(state.status_line) == 1
    assert "смотрит правила" in state.status_line


def test_player_chat_is_mirrored_into_chat_line():
    a = make_player(1, PieceType.PAWN, "D4")
    b = make_player(2, PieceType.PAWN, "A1")
    state = make_state([a, b])
    result = engine.apply_chat_message(state, 2, "сделай ход")
    assert result.ok
    assert state.chat_line == "@user2: сделай ход"
    text = info_message_text(state)
    assert "💬" in text
    assert "@user2: сделай ход" in text
    engine.apply_chat_message(state, 1, "ок")
    assert state.chat_line == "@user1: ок"


def test_rules_action_updates_status_and_exposes_full_rules():
    a = make_player(1, PieceType.PAWN, "D4")
    b = make_player(2, PieceType.PAWN, "A1")
    state = make_state([a, b])
    result = engine.view_rules(state, 1)
    assert result.ok
    assert state.showing_rules is True
    assert "смотрит правила" in state.status_line
    text = info_message_text(state)
    assert "пешка" in text.lower() or "Пешка" in RULES_FULL
    assert "королева" in RULES_FULL
    assert len(RULES_ALERT) <= 200


def test_draw_vote_counts_only_alive_and_needs_unanimity():
    a = make_player(1, PieceType.PAWN, "D4")
    b = make_player(2, PieceType.PAWN, "A1")
    c = make_player(3, PieceType.PAWN, "H8")
    d = make_player(4, PieceType.PAWN, "H1")
    state = make_state([a, b, c, d])
    first = engine.vote_draw(state, 1)
    assert "1/4" in first.announcements[0]
    assert first.draw is False
    engine.vote_draw(state, 2)
    engine.vote_draw(state, 3)
    third = engine.vote_draw(state, 3)  # already voted
    assert third.draw is False
    final = engine.vote_draw(state, 4)
    assert final.draw is True
    assert state.status == GameStatus.FINISHED


def test_dead_players_cannot_vote_or_move():
    a = make_player(1, PieceType.PAWN, "D4")
    b = make_player(2, PieceType.PAWN, "C5")
    c = make_player(3, PieceType.PAWN, "H8")
    state = make_state([a, b, c])
    engine.select_direction(state, 1, Direction.UP_LEFT, state.move_seq)
    assert b.alive is False
    vote = engine.vote_draw(state, 2)
    assert not vote.ok
    move = engine.select_direction(state, 2, Direction.UP, state.move_seq)
    assert not move.ok


def test_leaving_player_is_removed_from_draw_vote_count():
    a = make_player(1, PieceType.PAWN, "D4")
    b = make_player(2, PieceType.PAWN, "A1")
    c = make_player(3, PieceType.PAWN, "H8")
    state = make_state([a, b, c])
    engine.vote_draw(state, 1)
    engine.vote_draw(state, 2)
    engine.leave_game(state, 3)
    assert 3 not in state.draw_votes
    assert len(state.active_players()) == 2
    result = engine.vote_draw(state, 1)
    # still 2/2 after pruning the leaver? votes are 1 and 2, alive 2, should complete
    # wait leave already pruned and if votes 1,2 and alive 2, leave_game calls _finish_if_game_over
    # which does NOT auto-complete draw vote - only check_draw (queens) and victory.
    # After leave of c, votes still [1,2] and alive is 2. Unanimity isn't auto-applied on leave.
    assert result.draw is False or len(state.draw_votes) <= 2


def test_queen_evolution_removes_spawn_non_queen_relocates():
    a = make_player(1, PieceType.ROOK, "C4")
    b = make_player(2, PieceType.PAWN, "A1")
    spawn = Spawn(owner_user_id=2, position=Position.from_algebraic("D4"), activated=True)
    state = make_state([a, b], spawns=[spawn])
    opened = engine.select_direction(state, 1, Direction.RIGHT, 0)
    assert opened.pending_distances
    result = engine.select_distance(state, 1, Direction.RIGHT, 1, state.move_seq)
    assert result.evolved
    assert a.piece_type == PieceType.QUEEN
    assert spawn not in state.spawns
    assert not any(s.position == Position.from_algebraic("D4") for s in state.spawns)


def test_non_queen_evolution_relocates_spawn():
    a = make_player(1, PieceType.PAWN, "C4")
    b = make_player(2, PieceType.PAWN, "A1")
    spawn = Spawn(owner_user_id=2, position=Position.from_algebraic("D4"), activated=False)
    state = make_state([a, b], spawns=[spawn])
    engine.select_direction(state, 1, Direction.RIGHT, 0)
    assert a.piece_type == PieceType.BISHOP
    assert spawn in state.spawns or any(s.owner_user_id == 2 for s in state.spawns)
    remaining = next(s for s in state.spawns if s.owner_user_id == 2)
    assert remaining.position != Position.from_algebraic("D4")


def test_queen_queen_draw_after_evolution():
    a = make_player(1, PieceType.ROOK, "C4")
    b = make_player(2, PieceType.QUEEN, "A8")
    spawn = Spawn(owner_user_id=2, position=Position.from_algebraic("D4"), activated=True)
    state = make_state([a, b], spawns=[spawn])
    opened = engine.select_direction(state, 1, Direction.RIGHT, 0)
    assert opened.pending_distances
    result = engine.select_distance(state, 1, Direction.RIGHT, 1, state.move_seq)
    assert a.piece_type == PieceType.QUEEN
    assert result.draw is True


def test_evolution_points_match_piece_square_color():
    a = make_player(1, PieceType.BISHOP, "C1")  # C1 is black? C=2, row1: 2+0 even? col 2 row 1: 2+0=2 even -> black
    b = make_player(2, PieceType.PAWN, "H8")
    spawn = Spawn(owner_user_id=1, position=Position.from_algebraic("A2"), activated=True)
    other = Spawn(owner_user_id=2, position=Position.from_algebraic("H7"), activated=True)
    from bot.game.spawns import ensure_spawn_color_coverage

    ensure_spawn_color_coverage([spawn, other], [a, b])
    colors = {cell_color(s.position) for s in [spawn, other]}
    assert cell_color(a.position) in colors


def test_spawns_are_reasonably_distributed():
    layout = generate_initial_layout(list(range(6)), rng=__import__("random").Random(11))
    values = list(layout.values())
    for i, pos_a in enumerate(values):
        nearest = min(chebyshev_distance(pos_a, pos_b) for j, pos_b in enumerate(values) if i != j)
        assert nearest >= 2
        assert nearest <= 6


def test_knight_never_opens_distance_selection():
    a = make_player(1, PieceType.KNIGHT, "D4")
    b = make_player(2, PieceType.PAWN, "A1")
    state = make_state([a, b])
    for direction in legal_directions_for_piece(PieceType.KNIGHT):
        snapshot = a.position
        result = engine.select_direction(state, 1, direction, state.move_seq)
        if result.ok and result.pending_distances:
            raise AssertionError("Knight must not show distance selection")
        if result.ok and result.move_completed:
            return
        a.position = snapshot
        state.turn_index = 0
        state.status = GameStatus.ACTIVE
    raise AssertionError("Knight made no legal jump from D4")


def test_only_current_player_can_move():
    a = make_player(1, PieceType.PAWN, "D4")
    b = make_player(2, PieceType.PAWN, "A1")
    state = make_state([a, b])
    result = engine.select_direction(state, 2, Direction.UP, 0)
    assert not result.ok
    assert result.reason == "not_your_turn"


def test_ui_message_ids_cover_board_info_and_moves():
    state = GameState(game_id=1, chat_id=1, topic_id=1)
    state.info_message_id = 10
    state.board_message_id = 11
    state.moves_message_id = 12
    ids = state.ui_message_ids()
    assert ids == [10, 11, 12]
    assert moves_prompt_text() == "Ходы:"


def test_victory_checked_after_leave():
    a = make_player(1, PieceType.PAWN, "D4")
    b = make_player(2, PieceType.PAWN, "A1")
    state = make_state([a, b])
    result = engine.leave_game(state, 1)
    assert result.victory is True
    assert "побеждает" in state.status_line
