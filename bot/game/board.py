"""Board geometry: an 8x8 grid with helpers for coordinates and cell color."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator

BOARD_SIZE = 8
COLUMNS = "ABCDEFGH"  # column index 0 -> 'A' ... 7 -> 'H'
ROWS = (8, 7, 6, 5, 4, 3, 2, 1)  # top-to-bottom render order


@dataclass(frozen=True, order=True)
class Position:
    """A board square. ``col`` is 0-7 (A-H), ``row`` is 1-8."""

    col: int
    row: int

    def in_bounds(self) -> bool:
        return 0 <= self.col < BOARD_SIZE and 1 <= self.row <= BOARD_SIZE

    def translate(self, dcol: int, drow: int) -> "Position":
        return Position(self.col + dcol, self.row + drow)

    def to_algebraic(self) -> str:
        return f"{COLUMNS[self.col]}{self.row}"

    @classmethod
    def from_algebraic(cls, text: str) -> "Position":
        text = text.strip().upper()
        col = COLUMNS.index(text[0])
        row = int(text[1:])
        return cls(col, row)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.to_algebraic()


def cell_color(position: Position) -> str:
    """Return ``"white"`` or ``"black"`` for the square's board color.

    Matches standard chess coloring: A1 is a dark ("black") square.
    """

    return "black" if (position.col + (position.row - 1)) % 2 == 0 else "white"


def all_positions() -> Iterator[Position]:
    for row in ROWS:
        for col in range(BOARD_SIZE):
            yield Position(col, row)


def chebyshev_distance(a: Position, b: Position) -> int:
    return max(abs(a.col - b.col), abs(a.row - b.row))


def is_adjacent(a: Position, b: Position) -> bool:
    return a != b and chebyshev_distance(a, b) <= 1


def positions_occupied(positions: Iterable[Position]) -> set[Position]:
    return set(positions)
