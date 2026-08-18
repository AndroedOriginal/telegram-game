"""The authoritative, pure-Python Chess Royale game engine.

The engine mutates a :class:`GameState` in place and returns result objects
describing what happened, so callers (Telegram handlers) can render the
appropriate messages. It has zero dependencies on the Telegram API.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from . import rules
from .attacks import attacked_squares
from .board import Position, cell_color
from .evolution import can_use_spawn, evolution_announcement, evolve_player, mark_spawn_used
from .movement import (
    knight_jump_destination,
    legal_directions_for_piece,
    pawn_attack_target,
    pawn_step_destination,
    sliding_destinations,
)
from .models import (
    CARDINAL_DIRECTIONS,
    DIAGONAL_DIRECTIONS,
    MAX_PLAYERS,
    MIN_PLAYERS_TO_START,
    Direction,
    GameState,
    GameStatus,
    PendingAction,
    Player,
    PieceColor,
    PieceType,
    Spawn,
)
from .spawns import ensure_spawn_color_coverage, generate_initial_layout, relocate_spawn

INVALID_MOVE_MESSAGE = "ход невозможен."


@dataclass
class LobbyResult:
    ok: bool
    reason: str | None = None
    player: Player | None = None
    announcement: str | None = None
    lobby_size: int = 0


@dataclass
class StartResult:
    ok: bool
    reason: str | None = None


@dataclass
class ActionResult:
    ok: bool
    reason: str | None = None
    invalid: bool = False
    pending_distances: list[int] | None = None
    direction: Direction | None = None
    announcements: list[str] = field(default_factory=list)
    move_completed: bool = False
    died: bool = False
    evolved: bool = False
    draw: bool = False
    victory: bool = False
    mover_user_id: int | None = None


def join_lobby(state: GameState, user_id: int, username: str | None, display_name: str) -> LobbyResult:
    if state.status != GameStatus.LOBBY:
        return LobbyResult(ok=False, reason="not_in_lobby")
    if state.get_player(user_id) is not None:
        return LobbyResult(ok=False, reason="already_joined")
    if len(state.players) >= MAX_PLAYERS:
        return LobbyResult(ok=False, reason="lobby_full")
    player = Player(
        user_id=user_id,
        username=username,
        display_name=display_name,
        join_order=len(state.players),
    )
    state.players.append(player)
    return LobbyResult(ok=True, player=player, lobby_size=len(state.players))


def leave_lobby(state: GameState, user_id: int) -> LobbyResult:
    if state.status != GameStatus.LOBBY:
        return LobbyResult(ok=False, reason="not_in_lobby")
    player = state.get_player(user_id)
    if player is None:
        return LobbyResult(ok=False, reason="not_joined")
    state.players.remove(player)
    return LobbyResult(ok=True, player=player, lobby_size=len(state.players))


def start_game(state: GameState, rng: random.Random | None = None) -> StartResult:
    if state.status != GameStatus.LOBBY:
        return StartResult(ok=False, reason="not_in_lobby")
    if len(state.players) < MIN_PLAYERS_TO_START:
        return StartResult(ok=False, reason="not_enough_players")

    rng = rng or random

    user_ids = [p.user_id for p in state.players]
    layout = generate_initial_layout(user_ids, rng)

    for index, player in enumerate(state.players):
        player.color = PieceColor.WHITE if index % 2 == 0 else PieceColor.BLACK
        player.piece_type = PieceType.PAWN
        player.position = layout[player.user_id]
        player.alive = True
        player.left = False

    state.spawns = [
        Spawn(owner_user_id=player.user_id, position=player.position, activated_by_other=False)
        for player in state.players
    ]
    ensure_spawn_color_coverage(state.spawns, state.players)

    turn_order = list(user_ids)
    rng.shuffle(turn_order)
    state.turn_order = turn_order
    state.turn_index = 0
    state.move_seq = 0
    state.pending_action = None
    first = state.current_player()
    state.status_line = rules.turn_announcement(first) if first else rules.game_start_announcement()
    state.chat_line = None
    state.showing_rules = False
    state.draw_votes = []
    state.draw_proposer_user_id = None
    state.status = GameStatus.ACTIVE
    return StartResult(ok=True)


def _advance_turn(state: GameState) -> None:
    if not state.turn_order:
        return
    n = len(state.turn_order)
    for step in range(1, n + 1):
        candidate_index = (state.turn_index + step) % n
        candidate = state.get_player(state.turn_order[candidate_index])
        if candidate is not None and candidate.is_active:
            state.turn_index = candidate_index
            return


def _set_status(state: GameState, text: str) -> None:
    """Replace the single 🔈 line. Never accumulate history."""

    state.status_line = text
    state.last_announcements = [text]


def _apply_status_from_result(state: GameState, result: ActionResult) -> None:
    preferred = None
    for text in result.announcements:
        if "побеждает" in text or text.startswith("Ничья") or "предлагает ничью" in text:
            preferred = text
            break
    if preferred is None and result.announcements:
        preferred = result.announcements[-1]
    if preferred is not None:
        _set_status(state, preferred)
        return
    current = state.current_player()
    if state.status == GameStatus.ACTIVE and current is not None:
        _set_status(state, rules.turn_announcement(current))


def _prune_draw_votes(state: GameState) -> None:
    alive_ids = {p.user_id for p in state.active_players()}
    state.draw_votes = [user_id for user_id in state.draw_votes if user_id in alive_ids]
    if state.draw_proposer_user_id not in alive_ids:
        state.draw_proposer_user_id = state.draw_votes[0] if state.draw_votes else None
    if not state.draw_votes:
        state.draw_proposer_user_id = None


def _finish_if_game_over(state: GameState, result: ActionResult) -> bool:
    _prune_draw_votes(state)
    active = state.active_players()
    if rules.check_draw(active):
        state.status = GameStatus.FINISHED
        state.draw_user_ids = [p.user_id for p in active]
        announcement = rules.draw_announcement(active)
        result.announcements.append(announcement)
        result.draw = True
        _set_status(state, announcement if announcement.startswith("\U0001f508") else f"\U0001f508 {announcement}")
        return True
    winner = rules.check_victory(active)
    if winner is not None:
        state.status = GameStatus.FINISHED
        state.winner_user_id = winner.user_id
        announcement = rules.victory_announcement(winner)
        result.announcements.append(announcement)
        result.victory = True
        _set_status(state, announcement)
        return True
    return False


def _maybe_evolve_on_landing(state: GameState, player: Player, destination: Position, result: ActionResult) -> None:
    spawn = state.get_spawn_at(destination)
    if spawn is None or not can_use_spawn(player, spawn):
        return
    mark_spawn_used(player, spawn, state.spawns)
    evolved = evolve_player(player)
    if not evolved:
        return
    result.evolved = True
    result.announcements.append(evolution_announcement(player))
    if player.piece_type == PieceType.QUEEN:
        state.spawns = [s for s in state.spawns if s is not spawn]
    else:
        relocate_spawn(
            spawn,
            state.spawns,
            state.occupied_positions(),
            required_color=cell_color(player.position),
        )
    ensure_spawn_color_coverage(state.spawns, state.active_players())


def _eliminate_players_in_mover_attack(state: GameState, player: Player, result: ActionResult) -> None:
    """Check is lethal and immediate: anyone the mover now attacks dies,
    with no chance to escape. Dead pieces leave the board, so a newly
    opened ray can eliminate another player in the same resolution."""

    if not player.is_active or player.position is None:
        return
    while True:
        occupied = state.occupied_positions()
        attacks = attacked_squares(player.piece_type, player.position, occupied)
        victims = [
            other
            for other in state.active_players()
            if other.user_id != player.user_id and other.position in attacks
        ]
        if not victims:
            return
        for victim in victims:
            victim.alive = False
            result.announcements.append(rules.check_announcement(player, victim))


def _kill_mover_if_still_attacked(state: GameState, player: Player, result: ActionResult) -> None:
    """After the mover's checks are resolved, standing in a remaining
    opponent's attack is still lethal — there is no persistent check."""

    if not player.is_active or player.position is None:
        return
    occupied = state.occupied_positions()
    others = [p for p in state.active_players() if p.user_id != player.user_id]
    if any(player.position in attacked_squares(o.piece_type, o.position, occupied) for o in others):
        player.alive = False
        result.died = True


def _finalize_completed_move(state: GameState, player: Player, result: ActionResult) -> None:
    result.move_completed = True
    result.mover_user_id = player.user_id
    game_over = _finish_if_game_over(state, result)
    if not game_over:
        _advance_turn(state)
        state.pending_action = None
        state.showing_rules = False
    state.move_seq += 1
    _apply_status_from_result(state, result)


def _apply_successful_landing(state: GameState, player: Player, destination: Position, result: ActionResult) -> None:
    """Common post-move pipeline once a legal destination has been computed:
    move, evolve, immediately eliminate anyone now in the mover's attack
    area, then die if the mover is still under fire, then draw/victory,
    then advance the turn past anyone who just died."""

    player.position = destination
    _maybe_evolve_on_landing(state, player, destination, result)
    _eliminate_players_in_mover_attack(state, player, result)
    _kill_mover_if_still_attacked(state, player, result)
    _finalize_completed_move(state, player, result)


def _validate_actor(state: GameState, user_id: int) -> tuple[Player | None, str | None]:
    if state.status != GameStatus.ACTIVE:
        return None, "not_active"
    current = state.current_player()
    if current is None or current.user_id != user_id:
        return None, "not_your_turn"
    return current, None


def select_direction(
    state: GameState, user_id: int, direction: Direction, move_seq: int
) -> ActionResult:
    player, error = _validate_actor(state, user_id)
    if error:
        return ActionResult(ok=False, reason=error)
    if move_seq != state.move_seq:
        return ActionResult(ok=False, reason="stale")
    if not player.is_active:
        return ActionResult(ok=False, reason="not_a_player")
    if state.pending_action is not None and state.pending_action.user_id == user_id:
        state.pending_action = None

    piece_type = player.piece_type
    if direction not in legal_directions_for_piece(piece_type):
        _set_status(state, INVALID_MOVE_MESSAGE)
        return ActionResult(ok=False, invalid=True, reason=INVALID_MOVE_MESSAGE)

    occupied = state.occupied_positions(exclude_user_id=user_id)

    if piece_type == PieceType.PAWN:
        if direction in CARDINAL_DIRECTIONS:
            destination = pawn_step_destination(player.position, direction, occupied)
            if destination is None:
                return ActionResult(ok=False, invalid=True, reason=INVALID_MOVE_MESSAGE)
            result = ActionResult(ok=True, direction=direction)
            _apply_successful_landing(state, player, destination, result)
            return result
        else:  # diagonal attack
            target = pawn_attack_target(player.position, direction)
            if target is None or target not in occupied:
                return ActionResult(ok=False, invalid=True, reason=INVALID_MOVE_MESSAGE)
            victim = next(
                (p for p in state.active_players() if p.position == target and p.user_id != user_id),
                None,
            )
            if victim is None:
                return ActionResult(ok=False, invalid=True, reason=INVALID_MOVE_MESSAGE)
            return _apply_pawn_attack(state, player, victim)

    if piece_type == PieceType.KNIGHT:
        destination = knight_jump_destination(player.position, direction, occupied)
        if destination is None:
            return ActionResult(ok=False, invalid=True, reason=INVALID_MOVE_MESSAGE)
        result = ActionResult(ok=True, direction=direction)
        _apply_successful_landing(state, player, destination, result)
        return result

    # Sliding pieces: bishop, rook, queen -> open a distance-selection menu.
    destinations = sliding_destinations(player.position, direction, occupied)
    if not destinations:
        return ActionResult(ok=False, invalid=True, reason=INVALID_MOVE_MESSAGE)

    state.move_seq += 1
    state.pending_action = PendingAction(
        user_id=user_id,
        direction=direction,
        max_distance=len(destinations),
        move_seq=state.move_seq,
    )
    return ActionResult(
        ok=True,
        direction=direction,
        pending_distances=list(range(1, len(destinations) + 1)),
    )


def _apply_pawn_attack(state: GameState, attacker: Player, victim: Player) -> ActionResult:
    """A pawn diagonal attack eliminates the victim without the attacker
    moving. That is the same lethal check as any other attack: the victim
    dies immediately, then remaining attack rays and the attacker's own
    square are resolved."""

    result = ActionResult(ok=True)
    victim.alive = False
    result.announcements.append(rules.check_announcement(attacker, victim))
    _eliminate_players_in_mover_attack(state, attacker, result)
    _kill_mover_if_still_attacked(state, attacker, result)
    _finalize_completed_move(state, attacker, result)
    return result


def select_distance(
    state: GameState, user_id: int, direction: Direction, distance: int, move_seq: int
) -> ActionResult:
    player, error = _validate_actor(state, user_id)
    if error:
        return ActionResult(ok=False, reason=error)

    pending = state.pending_action
    if (
        pending is None
        or pending.user_id != user_id
        or pending.direction != direction
        or pending.move_seq != move_seq
        or move_seq != state.move_seq
    ):
        return ActionResult(ok=False, reason="stale")

    if distance < 1 or distance > pending.max_distance:
        return ActionResult(ok=False, invalid=True, reason=INVALID_MOVE_MESSAGE)

    occupied = state.occupied_positions(exclude_user_id=user_id)
    destinations = sliding_destinations(player.position, direction, occupied)
    if distance > len(destinations):
        return ActionResult(ok=False, invalid=True, reason=INVALID_MOVE_MESSAGE)

    destination = destinations[distance - 1]
    result = ActionResult(ok=True, direction=direction)
    _apply_successful_landing(state, player, destination, result)
    return result


def leave_game(state: GameState, user_id: int) -> ActionResult:
    """Handle a player leaving an active game (section 24)."""

    if state.status != GameStatus.ACTIVE:
        return ActionResult(ok=False, reason="not_active")
    player = state.get_player(user_id)
    if player is None or not player.is_active:
        return ActionResult(ok=False, reason="not_a_player")

    was_current = state.current_player() is not None and state.current_player().user_id == user_id
    player.left = True
    if state.pending_action is not None and state.pending_action.user_id == user_id:
        state.pending_action = None

    result = ActionResult(ok=True, mover_user_id=user_id)
    result.announcements.append(rules.leave_announcement(player))

    game_over = _finish_if_game_over(state, result)
    if not game_over and was_current:
        _advance_turn(state)
        state.showing_rules = False
    state.move_seq += 1
    _apply_status_from_result(state, result)
    return result


def view_rules(state: GameState, user_id: int) -> ActionResult:
    if state.status != GameStatus.ACTIVE:
        return ActionResult(ok=False, reason="not_active")
    player = state.get_player(user_id)
    if player is None or not player.is_active:
        return ActionResult(ok=False, reason="not_a_player")
    state.showing_rules = True
    announcement = rules.rules_view_announcement(player)
    result = ActionResult(ok=True)
    result.announcements.append(announcement)
    _set_status(state, announcement)
    return result


def vote_draw(state: GameState, user_id: int) -> ActionResult:
    if state.status != GameStatus.ACTIVE:
        return ActionResult(ok=False, reason="not_active")
    player = state.get_player(user_id)
    if player is None or not player.is_active:
        return ActionResult(ok=False, reason="not_a_player")

    _prune_draw_votes(state)
    if user_id in state.draw_votes:
        proposer = state.get_player(state.draw_proposer_user_id) if state.draw_proposer_user_id else player
        announcement = rules.draw_vote_announcement(
            proposer or player, len(state.draw_votes), len(state.active_players())
        )
        result = ActionResult(ok=True)
        result.announcements.append(announcement)
        _set_status(state, announcement)
        return result

    if not state.draw_votes:
        state.draw_proposer_user_id = user_id
        state.draw_votes = [user_id]
    else:
        state.draw_votes.append(user_id)

    proposer = state.get_player(state.draw_proposer_user_id) or player
    alive = state.active_players()
    announcement = rules.draw_vote_announcement(proposer, len(state.draw_votes), len(alive))
    result = ActionResult(ok=True)
    result.announcements.append(announcement)
    _set_status(state, announcement)

    if len(state.draw_votes) >= len(alive) and len(alive) >= 2:
        state.status = GameStatus.FINISHED
        state.draw_user_ids = [p.user_id for p in alive]
        draw_text = rules.draw_announcement(alive)
        if not draw_text.startswith("\U0001f508"):
            draw_text = f"\U0001f508 {draw_text}"
        result.announcements = [draw_text]
        result.draw = True
        _set_status(state, draw_text)
    return result


def apply_chat_message(state: GameState, user_id: int, text: str) -> ActionResult:
    if state.status != GameStatus.ACTIVE:
        return ActionResult(ok=False, reason="not_active")
    player = state.get_player(user_id)
    if player is None or not player.is_active:
        return ActionResult(ok=False, reason="not_a_player")
    cleaned = " ".join(text.split())
    if not cleaned:
        return ActionResult(ok=False, reason="empty")
    state.chat_line = f"{player.mention}: {cleaned}"
    return ActionResult(ok=True)


GAME_ENDED_MESSAGE = "\U0001f508 Игра завершена."


def end_game(state: GameState) -> ActionResult:
    """Force-end the current lobby or match so a new lobby can be opened."""

    state.status = GameStatus.FINISHED
    state.pending_action = None
    state.move_seq += 1
    result = ActionResult(ok=True)
    result.announcements.append(GAME_ENDED_MESSAGE)
    _set_status(state, GAME_ENDED_MESSAGE)
    return result
