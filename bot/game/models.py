"""Core dataclasses and enums representing a Chess Royale game."""
from __future__ import annotations

import enum
from dataclasses import dataclass, field

from .board import Position

MAX_PLAYERS = 8
MIN_PLAYERS_TO_START = 2


class PieceType(enum.Enum):
    PAWN = "pawn"
    BISHOP = "bishop"
    KNIGHT = "knight"
    ROOK = "rook"
    QUEEN = "queen"


# Evolution order: Pawn -> Bishop -> Knight -> Rook -> Queen. A Queen is final.
EVOLUTION_ORDER: tuple[PieceType, ...] = (
    PieceType.PAWN,
    PieceType.BISHOP,
    PieceType.KNIGHT,
    PieceType.ROOK,
    PieceType.QUEEN,
)

PIECE_NAME_RU = {
    PieceType.PAWN: "пешку",
    PieceType.BISHOP: "слона",
    PieceType.KNIGHT: "коня",
    PieceType.ROOK: "ладью",
    PieceType.QUEEN: "королеву",
}


def next_piece_type(current: PieceType) -> PieceType | None:
    """Return the next evolution stage, or ``None`` if already a Queen."""

    index = EVOLUTION_ORDER.index(current)
    if index + 1 >= len(EVOLUTION_ORDER):
        return None
    return EVOLUTION_ORDER[index + 1]


class PieceColor(enum.Enum):
    WHITE = "white"
    BLACK = "black"


class Direction(enum.Enum):
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    UP_LEFT = "up_left"
    UP_RIGHT = "up_right"
    DOWN_LEFT = "down_left"
    DOWN_RIGHT = "down_right"


DIRECTION_VECTORS: dict[Direction, tuple[int, int]] = {
    Direction.UP: (0, 1),
    Direction.DOWN: (0, -1),
    Direction.LEFT: (-1, 0),
    Direction.RIGHT: (1, 0),
    Direction.UP_LEFT: (-1, 1),
    Direction.UP_RIGHT: (1, 1),
    Direction.DOWN_LEFT: (-1, -1),
    Direction.DOWN_RIGHT: (1, -1),
}

DIRECTION_EMOJI = {
    Direction.LEFT: "\u2b05\ufe0f",
    Direction.RIGHT: "\u27a1\ufe0f",
    Direction.UP: "\u2b06\ufe0f",
    Direction.DOWN: "\u2b07\ufe0f",
    Direction.UP_LEFT: "\u2196\ufe0f",
    Direction.UP_RIGHT: "\u2197\ufe0f",
    Direction.DOWN_LEFT: "\u2199\ufe0f",
    Direction.DOWN_RIGHT: "\u2198\ufe0f",
}

CARDINAL_DIRECTIONS = (Direction.UP, Direction.DOWN, Direction.LEFT, Direction.RIGHT)
DIAGONAL_DIRECTIONS = (
    Direction.UP_LEFT,
    Direction.UP_RIGHT,
    Direction.DOWN_LEFT,
    Direction.DOWN_RIGHT,
)

# The knight only exposes 4 movement buttons (one per diagonal quadrant).
# Each button performs one fixed L-shaped jump. This is a deliberate design
# choice for a compact one-hand mobile control scheme (see section 13 of the
# spec): only half of the 8 classic knight destinations are reachable by a
# single button, but knight *attack* geometry (used for check detection)
# still uses the full classic 8-square L-shape (see attacks.py).
KNIGHT_JUMP_VECTORS: dict[Direction, tuple[int, int]] = {
    Direction.UP_LEFT: (-1, 2),
    Direction.UP_RIGHT: (1, 2),
    Direction.DOWN_LEFT: (-1, -2),
    Direction.DOWN_RIGHT: (1, -2),
}

# All 8 classic knight L-shapes, used only for attack/check detection.
KNIGHT_ATTACK_VECTORS: tuple[tuple[int, int], ...] = (
    (1, 2), (2, 1), (2, -1), (1, -2),
    (-1, -2), (-2, -1), (-2, 1), (-1, 2),
)


class GameStatus(enum.Enum):
    LOBBY = "lobby"
    ACTIVE = "active"
    FINISHED = "finished"


@dataclass
class Player:
    user_id: int
    username: str | None
    display_name: str
    color: PieceColor = PieceColor.WHITE
    piece_type: PieceType = PieceType.PAWN
    position: Position | None = None
    alive: bool = True
    left: bool = False
    join_order: int = 0

    @property
    def mention(self) -> str:
        if self.username:
            return f"@{self.username}"
        return self.display_name

    @property
    def is_active(self) -> bool:
        return self.alive and not self.left


@dataclass
class Spawn:
    owner_user_id: int
    position: Position
    activated: bool = False  # True once used by a player other than the owner


@dataclass
class PendingAction:
    """Represents an in-progress two-step move (direction chosen, awaiting
    a distance selection) for sliding pieces."""

    user_id: int
    direction: Direction
    max_distance: int
    move_seq: int
    message_id: int | None = None


@dataclass
class GameState:
    game_id: int
    chat_id: int
    topic_id: int | None
    status: GameStatus = GameStatus.LOBBY
    players: list[Player] = field(default_factory=list)
    spawns: list[Spawn] = field(default_factory=list)
    turn_order: list[int] = field(default_factory=list)
    turn_index: int = 0
    move_seq: int = 0
    pending_action: PendingAction | None = None
    info_message_id: int | None = None
    board_message_id: int | None = None
    rules_message_id: int | None = None
    lobby_message_id: int | None = None
    start_message_id: int | None = None
    distance_message_id: int | None = None
    winner_user_id: int | None = None
    draw_user_ids: list[int] = field(default_factory=list)

    def get_player(self, user_id: int) -> Player | None:
        for player in self.players:
            if player.user_id == user_id:
                return player
        return None

    def active_players(self) -> list[Player]:
        return [p for p in self.players if p.is_active]

    def current_player(self) -> Player | None:
        if not self.turn_order:
            return None
        user_id = self.turn_order[self.turn_index % len(self.turn_order)]
        return self.get_player(user_id)

    def occupied_positions(self, exclude_user_id: int | None = None) -> set[Position]:
        return {
            p.position
            for p in self.players
            if p.is_active and p.position is not None and p.user_id != exclude_user_id
        }

    def spawn_positions(self, exclude: Spawn | None = None) -> set[Position]:
        return {s.position for s in self.spawns if s is not exclude}

    def get_spawn_at(self, position: Position) -> Spawn | None:
        for spawn in self.spawns:
            if spawn.position == position:
                return spawn
        return None
