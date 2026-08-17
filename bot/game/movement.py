"""Legal-move calculation for each piece type.

This module is pure Python: it only knows about :class:`Position`,
:class:`Direction`, and sets of occupied squares. It has no knowledge of
Telegram, players, or turns.
"""
from __future__ import annotations

from .board import Position
from .models import (
    CARDINAL_DIRECTIONS,
    DIAGONAL_DIRECTIONS,
    DIRECTION_VECTORS,
    KNIGHT_JUMP_VECTORS,
    Direction,
    PieceType,
)

MAX_SLIDE_DISTANCE = 7


def sliding_destinations(
    position: Position, direction: Direction, occupied: set[Position]
) -> list[Position]:
    """Ordered list (closest first) of legal landing squares for a sliding
    piece (bishop/rook/queen) moving in ``direction`` from ``position``.

    The ray stops at the board edge or just before the first occupied
    square (pieces cannot jump over or land on another player).
    """

    dcol, drow = DIRECTION_VECTORS[direction]
    destinations: list[Position] = []
    for distance in range(1, MAX_SLIDE_DISTANCE + 1):
        candidate = position.translate(dcol * distance, drow * distance)
        if not candidate.in_bounds():
            break
        if candidate in occupied:
            break
        destinations.append(candidate)
    return destinations


def pawn_step_destination(
    position: Position, direction: Direction, occupied: set[Position]
) -> Position | None:
    """Return the destination for a one-square cardinal pawn move, or
    ``None`` if illegal (out of bounds or occupied)."""

    if direction not in CARDINAL_DIRECTIONS:
        return None
    dcol, drow = DIRECTION_VECTORS[direction]
    candidate = position.translate(dcol, drow)
    if not candidate.in_bounds():
        return None
    if candidate in occupied:
        return None
    return candidate


def pawn_attack_target(position: Position, direction: Direction) -> Position | None:
    """Return the diagonal square for a pawn attack direction, if in bounds."""

    if direction not in DIAGONAL_DIRECTIONS:
        return None
    dcol, drow = DIRECTION_VECTORS[direction]
    candidate = position.translate(dcol, drow)
    if not candidate.in_bounds():
        return None
    return candidate


def knight_jump_destination(
    position: Position, direction: Direction, occupied: set[Position]
) -> Position | None:
    """Return the fixed knight-jump destination for one of the four
    diagonal quadrant buttons, or ``None`` if illegal."""

    vector = KNIGHT_JUMP_VECTORS.get(direction)
    if vector is None:
        return None
    candidate = position.translate(*vector)
    if not candidate.in_bounds():
        return None
    if candidate in occupied:
        return None
    return candidate


def legal_directions_for_piece(piece_type: PieceType) -> tuple[Direction, ...]:
    if piece_type == PieceType.PAWN:
        return CARDINAL_DIRECTIONS + DIAGONAL_DIRECTIONS
    if piece_type == PieceType.BISHOP:
        return DIAGONAL_DIRECTIONS
    if piece_type == PieceType.KNIGHT:
        return DIAGONAL_DIRECTIONS
    if piece_type == PieceType.ROOK:
        return CARDINAL_DIRECTIONS
    if piece_type == PieceType.QUEEN:
        return CARDINAL_DIRECTIONS + DIAGONAL_DIRECTIONS
    raise ValueError(piece_type)  # pragma: no cover - exhaustive enum
