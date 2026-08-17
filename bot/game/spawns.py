"""Spawn / evolution point generation, activation and relocation logic."""
from __future__ import annotations

import random
from typing import Iterable

from .attacks import attacked_squares
from .board import Position, all_positions, is_adjacent
from .models import PieceType, Spawn

MAX_PLACEMENT_ATTEMPTS = 500


def find_valid_spawn_position(
    occupied_by_players: Iterable[Position],
    occupied_by_spawns: Iterable[Position],
    rng: random.Random | None = None,
) -> Position:
    """Return a random board cell that does not overlap any player or any
    other spawn. Retries candidates until a valid one is found.

    Raises ``RuntimeError`` if the board is completely full (should never
    happen with at most 8 players and 8 spawns on 64 squares).
    """

    rng = rng or random
    forbidden = set(occupied_by_players) | set(occupied_by_spawns)
    candidates = [pos for pos in all_positions() if pos not in forbidden]
    if not candidates:
        raise RuntimeError("No valid spawn position available: board is full")
    for _ in range(MAX_PLACEMENT_ATTEMPTS):
        candidate = rng.choice(candidates)
        if candidate not in forbidden:
            return candidate
    # Fallback (unreachable in practice given the pre-filtered candidate list).
    return candidates[0]  # pragma: no cover


def relocate_spawn(
    spawn: Spawn,
    all_spawns: list[Spawn],
    player_positions: Iterable[Position],
    rng: random.Random | None = None,
) -> None:
    """Move ``spawn`` to a new random valid location, in place."""

    forbidden_spawn_positions = {s.position for s in all_spawns if s is not spawn}
    forbidden_spawn_positions.add(spawn.position)  # a relocation must land on a new cell
    new_position = find_valid_spawn_position(player_positions, forbidden_spawn_positions, rng)
    spawn.position = new_position


def generate_initial_layout(
    user_ids: list[int], rng: random.Random | None = None
) -> dict[int, Position]:
    """Randomly generate distinct, mutually-safe starting positions for all
    players (all start as pawns). Retries until constraints are satisfied:

    - no two players share a square;
    - no two players are adjacent (king-distance <= 1);
    - no player starts under attack by another player's pawn diagonals.
    """

    rng = rng or random
    all_cells = list(all_positions())

    for _ in range(MAX_PLACEMENT_ATTEMPTS):
        candidate_cells = rng.sample(all_cells, len(user_ids))
        positions = dict(zip(user_ids, candidate_cells))
        if _layout_is_valid(positions):
            return positions

    raise RuntimeError("Failed to generate a valid initial layout")  # pragma: no cover


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
