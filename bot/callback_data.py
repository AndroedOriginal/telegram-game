"""Compact, parseable callback_data encoding/decoding.

Callback data never carries a player identity -- the authenticated Telegram
user id from the callback query is always used instead (section 41 of the
spec). Data only carries: the action kind, which game it targets, a
move-sequence token (to reject stale/replayed buttons), and action
parameters (direction / distance).
"""
from __future__ import annotations

from dataclasses import dataclass

from .game.models import Direction

LOBBY_JOIN = "lj"
LOBBY_LEAVE = "ll"
LOBBY_START = "ls"
DIRECTION = "dir"
DISTANCE = "dst"
RULES = "ru"
QUIT = "qt"
DRAW = "dv"


class CallbackParseError(ValueError):
    pass


@dataclass
class LobbyCallback:
    kind: str
    game_id: int


@dataclass
class DirectionCallback:
    game_id: int
    move_seq: int
    direction: Direction


@dataclass
class DistanceCallback:
    game_id: int
    move_seq: int
    direction: Direction
    distance: int


@dataclass
class GameButtonCallback:
    kind: str
    game_id: int
    move_seq: int


def encode_lobby(kind: str, game_id: int) -> str:
    return f"{kind}:{game_id}"


def encode_direction(game_id: int, move_seq: int, direction: Direction) -> str:
    return f"{DIRECTION}:{game_id}:{move_seq}:{direction.value}"


def encode_distance(game_id: int, move_seq: int, direction: Direction, distance: int) -> str:
    return f"{DISTANCE}:{game_id}:{move_seq}:{direction.value}:{distance}"


def encode_game_button(kind: str, game_id: int, move_seq: int) -> str:
    return f"{kind}:{game_id}:{move_seq}"


def decode(data: str) -> "LobbyCallback | DirectionCallback | DistanceCallback | GameButtonCallback":
    parts = data.split(":")
    if not parts:
        raise CallbackParseError("empty callback data")
    kind = parts[0]
    try:
        if kind in (LOBBY_JOIN, LOBBY_LEAVE, LOBBY_START):
            return LobbyCallback(kind=kind, game_id=int(parts[1]))
        if kind in (RULES, QUIT, DRAW):
            _, game_id, move_seq = parts
            return GameButtonCallback(kind=kind, game_id=int(game_id), move_seq=int(move_seq))
        if kind == DIRECTION:
            _, game_id, move_seq, direction = parts
            return DirectionCallback(
                game_id=int(game_id), move_seq=int(move_seq), direction=Direction(direction)
            )
        if kind == DISTANCE:
            _, game_id, move_seq, direction, distance = parts
            return DistanceCallback(
                game_id=int(game_id),
                move_seq=int(move_seq),
                direction=Direction(direction),
                distance=int(distance),
            )
    except (ValueError, IndexError) as exc:  # pragma: no cover - defensive
        raise CallbackParseError(str(exc)) from exc
    raise CallbackParseError(f"unknown callback kind: {kind}")
