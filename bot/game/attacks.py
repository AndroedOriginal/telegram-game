"""Attack-area computation, following classic chess geometry.

Attack areas are used for check/death detection and are intentionally more
generous than the restricted movement controls exposed to the player (see
``movement.py`` for the knight's 4-button restriction). Section 17 of the
spec requires bishop/knight/rook/queen attack geometry to match "original
chess", while pawns use the custom four-diagonal rule.
"""
from __future__ import annotations

from .board import Position
from .models import (
    CARDINAL_DIRECTIONS,
    DIAGONAL_DIRECTIONS,
    DIRECTION_VECTORS,
    KNIGHT_ATTACK_VECTORS,
    PieceType,
)

MAX_SLIDE_DISTANCE = 7


def _sliding_attacks(
    position: Position, directions: tuple, occupied: set[Position]
) -> set[Position]:
    attacked: set[Position] = set()
    for direction in directions:
        dcol, drow = DIRECTION_VECTORS[direction]
        for distance in range(1, MAX_SLIDE_DISTANCE + 1):
            candidate = position.translate(dcol * distance, drow * distance)
            if not candidate.in_bounds():
                break
            attacked.add(candidate)
            if candidate in occupied:
                break
    return attacked


def _knight_attacks(position: Position) -> set[Position]:
    attacked = set()
    for dcol, drow in KNIGHT_ATTACK_VECTORS:
        candidate = position.translate(dcol, drow)
        if candidate.in_bounds():
            attacked.add(candidate)
    return attacked


def _pawn_attacks(position: Position) -> set[Position]:
    attacked = set()
    for direction in DIAGONAL_DIRECTIONS:
        dcol, drow = DIRECTION_VECTORS[direction]
        candidate = position.translate(dcol, drow)
        if candidate.in_bounds():
            attacked.add(candidate)
    return attacked


def attacked_squares(
    piece_type: PieceType, position: Position, occupied: set[Position]
) -> set[Position]:
    """Return every square attacked by a piece of ``piece_type`` standing on
    ``position``, given the set of all occupied squares (including its own,
    which callers should exclude beforehand if desired -- it has no effect
    since a piece never attacks its own square)."""

    blockers = occupied - {position}
    if piece_type == PieceType.PAWN:
        return _pawn_attacks(position)
    if piece_type == PieceType.BISHOP:
        return _sliding_attacks(position, DIAGONAL_DIRECTIONS, blockers)
    if piece_type == PieceType.KNIGHT:
        return _knight_attacks(position)
    if piece_type == PieceType.ROOK:
        return _sliding_attacks(position, CARDINAL_DIRECTIONS, blockers)
    if piece_type == PieceType.QUEEN:
        return _sliding_attacks(
            position, CARDINAL_DIRECTIONS + DIAGONAL_DIRECTIONS, blockers
        )
    raise ValueError(piece_type)  # pragma: no cover - exhaustive enum


def is_square_attacked_by(
    piece_type: PieceType,
    piece_position: Position,
    target: Position,
    occupied: set[Position],
) -> bool:
    return target in attacked_squares(piece_type, piece_position, occupied)
