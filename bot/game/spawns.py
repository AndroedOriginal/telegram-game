"""Spawn / evolution point generation, activation and relocation logic."""
from __future__ import annotations

import random
from typing import Iterable

from .attacks import attacked_squares
from .board import Position, all_positions, cell_color, chebyshev_distance, is_adjacent
from .models import PieceType, Player, Spawn

MAX_PLACEMENT_ATTEMPTS = 800
MIN_SPAWN_SEPARATION = 2


def _nearest_neighbor(candidate: Position, others: Iterable[Position]) -> int | None:
    others = list(others)
    if not others:
        return None
    return min(chebyshev_distance(candidate, other) for other in others)


def _max_nearest_allowed(count: int) -> int:
    if count <= 3:
        return 5
    if count <= 5:
        return 4
    return 3


def _score_spawn_candidate(candidate: Position, others: list[Position]) -> float:
    nearest = _nearest_neighbor(candidate, others)
    if nearest is None:
        return 0.0
    if nearest < MIN_SPAWN_SEPARATION:
        return -1000.0
    max_near = _max_nearest_allowed(len(others) + 1)
    penalty = 0.0
    if nearest > max_near:
        penalty += (nearest - max_near) * 3.0
    average = sum(chebyshev_distance(candidate, other) for other in others) / len(others)
    return nearest * 2.0 + average - penalty


def find_valid_spawn_position(
    occupied_by_players: Iterable[Position],
    occupied_by_spawns: Iterable[Position],
    rng: random.Random | None = None,
    required_color: str | None = None,
) -> Position:
    """Return a random board cell that does not overlap any player or any
    other spawn, is not clustered against other spawns, and optionally
    matches ``required_color`` ("white" or "black").
    """

    rng = rng or random
    player_set = set(occupied_by_players)
    spawn_set = set(occupied_by_spawns)
    forbidden = player_set | spawn_set
    others = list(spawn_set)
    candidates = [
        pos
        for pos in all_positions()
        if pos not in forbidden
        and (required_color is None or cell_color(pos) == required_color)
    ]
    if not candidates:
        # Relax color first, then clustering, rather than fail the game.
        candidates = [pos for pos in all_positions() if pos not in forbidden]
    if not candidates:
        raise RuntimeError("No valid spawn position available: board is full")

    scored: list[tuple[float, Position]] = []
    sample = candidates if len(candidates) <= 32 else rng.sample(candidates, 32)
    for candidate in sample:
        scored.append((_score_spawn_candidate(candidate, others), candidate))
    scored.sort(key=lambda item: item[0], reverse=True)
    best_score, best = scored[0]
    if best_score > -1000:
        return best
    return rng.choice(candidates)


def relocate_spawn(
    spawn: Spawn,
    all_spawns: list[Spawn],
    player_positions: Iterable[Position],
    rng: random.Random | None = None,
    required_color: str | None = None,
) -> None:
    """Move ``spawn`` to a new random valid location, in place."""

    other_spawn_positions = {s.position for s in all_spawns if s is not spawn}
    other_spawn_positions.add(spawn.position)
    new_position = find_valid_spawn_position(
        player_positions, other_spawn_positions, rng, required_color=required_color
    )
    spawn.position = new_position


def ensure_spawn_color_coverage(
    spawns: list[Spawn],
    players: Iterable[Player],
    rng: random.Random | None = None,
) -> None:
    """Guarantee each non-queen alive player has at least one evolution
    point on the same square color as their piece."""

    rng = rng or random
    active = [p for p in players if p.is_active and p.position is not None]
    player_positions = {p.position for p in active}

    for player in active:
        if player.piece_type == PieceType.QUEEN:
            continue
        need = cell_color(player.position)
        if any(cell_color(spawn.position) == need for spawn in spawns):
            continue
        if not spawns:
            return
        target = max(spawns, key=lambda spawn: chebyshev_distance(spawn.position, player.position))
        relocate_spawn(target, spawns, player_positions, rng, required_color=need)


def generate_initial_layout(
    user_ids: list[int], rng: random.Random | None = None
) -> dict[int, Position]:
    """Randomly generate distinct, mutually-safe starting positions for all
    players (all start as pawns). Retries until constraints are satisfied:

    - no two players share a square;
    - players must not spawn adjacent to each other;
    - players must not start under attack;
    - spawn/player points are reasonably distributed across the board.
    """

    rng = rng or random
    all_cells = list(all_positions())
    best: dict[int, Position] | None = None
    best_score = float("-inf")

    for _ in range(MAX_PLACEMENT_ATTEMPTS):
        candidate_cells = rng.sample(all_cells, len(user_ids))
        positions = dict(zip(user_ids, candidate_cells))
        if not _layout_is_valid(positions):
            continue
        score = _layout_distribution_score(list(positions.values()))
        if score > best_score:
            best = positions
            best_score = score
        if score >= 0:
            return positions

    if best is not None:
        return best
    raise RuntimeError("Failed to generate a valid initial layout")  # pragma: no cover


def _layout_distribution_score(values: list[Position]) -> float:
    if len(values) < 2:
        return 0.0
    nearest: list[int] = []
    for i, pos_a in enumerate(values):
        nearest.append(min(chebyshev_distance(pos_a, pos_b) for j, pos_b in enumerate(values) if i != j))
    min_near = min(nearest)
    max_near = max(nearest)
    allowed = _max_nearest_allowed(len(values))
    if min_near < MIN_SPAWN_SEPARATION:
        return -1000.0
    penalty = 0.0
    if max_near > allowed:
        penalty += (max_near - allowed) * 4.0
    return float(min_near) + (sum(nearest) / len(nearest)) - penalty


def _layout_is_valid(positions: dict[int, Position]) -> bool:
    values = list(positions.values())
    for i, pos_a in enumerate(values):
        for pos_b in values[i + 1 :]:
            if pos_a == pos_b:
                return False
            if is_adjacent(pos_a, pos_b):
                return False

    occupied = set(values)
    for pos in values:
        others = occupied - {pos}
        for other_pos in others:
            if pos in attacked_squares(PieceType.PAWN, other_pos, occupied):
                return False
    return True
