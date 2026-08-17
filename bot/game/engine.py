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
from .board import Position
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
from .spawns import generate_initial_layout, relocate_spawn

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
        Spawn(owner_user_id=player.user_id, position=player.position, activated=False)
        for player in state.players
    ]

    turn_order = list(user_ids)
    rng.shuffle(turn_order)
    state.turn_order = turn_order
    state.turn_index = 0
    state.move_seq = 0
    state.pending_action = None
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


def _finish_if_game_over(state: GameState, result: ActionResult) -> bool:
    active = state.active_players()
    if rules.check_draw(active):
        state.status = GameStatus.FINISHED
        state.draw_user_ids = [p.user_id for p in active]
        result.announcements.append(rules.draw_announcement(active))
        result.draw = True
        return True
    winner = rules.check_victory(active)
    if winner is not None:
        state.status = GameStatus.FINISHED
        state.winner_user_id = winner.user_id
        result.announcements.append(rules.victory_announcement(winner))
        result.victory = True
        return True
    return False


def _apply_successful_landing(state: GameState, player: Player, destination: Position, result: ActionResult) -> None:
    """Common post-move pipeline once a legal destination has been computed:
    move the piece, check death, check evolution, check announcements, then
    draw/victory, then advance the turn."""

    player.position = destination
    occupied = state.occupied_positions()

    others = [p for p in state.active_players() if p.user_id != player.user_id]
    is_attacked = any(
        destination in attacked_squares(o.piece_type, o.position, occupied) for o in others
    )

    if is_attacked:
        player.alive = False
        result.died = True
    else:
        spawn = state.get_spawn_at(destination)
        if spawn is not None and can_use_spawn(player, spawn):
            mark_spawn_used(player, spawn)
            evolved = evolve_player(player)
            if evolved:
                result.evolved = True
                result.announcements.append(evolution_announcement(player))
            relocate_spawn(spawn, state.spawns, state.occupied_positions())

        # Recompute checks caused by the mover's (possibly upgraded) piece.
        occupied_after = state.occupied_positions()
        mover_attacks = attacked_squares(player.piece_type, player.position, occupied_after)
        for other in state.active_players():
            if other.user_id == player.user_id:
                continue
            if other.position in mover_attacks:
                result.announcements.append(rules.check_announcement(player, other))

    result.move_completed = True
    result.mover_user_id = player.user_id

    game_over = _finish_if_game_over(state, result)
    if not game_over:
        _advance_turn(state)
        state.pending_action = None
    state.move_seq += 1


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

    piece_type = player.piece_type
    if direction not in legal_directions_for_piece(piece_type):
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
    moving. The attacker's square is then re-evaluated for danger, matching
    the "recalculate attacks after every move" rule."""

    result = ActionResult(ok=True)
    victim.alive = False

    occupied_after = state.occupied_positions()
    others = [p for p in state.active_players() if p.user_id != attacker.user_id]
    is_attacked = any(
        attacker.position in attacked_squares(o.piece_type, o.position, occupied_after)
        for o in others
    )
    if is_attacked:
        attacker.alive = False
        result.died = True
    else:
        mover_attacks = attacked_squares(attacker.piece_type, attacker.position, occupied_after)
        for other in state.active_players():
            if other.user_id == attacker.user_id:
                continue
            if other.position in mover_attacks:
                result.announcements.append(rules.check_announcement(attacker, other))

    result.move_completed = True
    result.mover_user_id = attacker.user_id

    game_over = _finish_if_game_over(state, result)
    if not game_over:
        _advance_turn(state)
        state.pending_action = None
    state.move_seq += 1
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
    state.move_seq += 1
    return result
