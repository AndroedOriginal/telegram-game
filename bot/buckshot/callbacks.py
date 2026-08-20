"""Encode/decode Buckshot Roulette callback_data. Prefixes never overlap Chess Royale."""
from __future__ import annotations

from dataclasses import dataclass

from .models import CODE_TO_ITEM, ITEM_CODE, ItemType

JOIN = "bj"
LEAVE = "bl"
START = "bk"
RULES = "bru"
QUIT = "bqt"
SHOOT = "bsh"
TARGET = "btg"
USE = "bus"
ITEM = "bit"
JAMMER = "bjm"
ADR_TARGET = "bad"
ADR_ITEM = "bai"
INSPECT = "bin"
LOOK = "blk"
BACK = "bbk"
MAGNIFY = "bmg"


class CallbackParseError(ValueError):
    pass


@dataclass
class LobbyCallback:
    kind: str
    game_id: int


@dataclass
class SeqCallback:
    kind: str
    game_id: int
    action_seq: int
    target_id: int | None = None
    item: ItemType | None = None


def encode_lobby(kind: str, game_id: int) -> str:
    return f"{kind}:{game_id}"


def encode_seq(kind: str, game_id: int, action_seq: int) -> str:
    return f"{kind}:{game_id}:{action_seq}"


def encode_target(kind: str, game_id: int, action_seq: int, target_id: int) -> str:
    return f"{kind}:{game_id}:{action_seq}:{target_id}"


def encode_item(kind: str, game_id: int, action_seq: int, item: ItemType) -> str:
    return f"{kind}:{game_id}:{action_seq}:{ITEM_CODE[item]}"


def is_buckshot_callback(data: str) -> bool:
    kind = data.split(":", 1)[0]
    return kind in {
        JOIN,
        LEAVE,
        START,
        RULES,
        QUIT,
        SHOOT,
        TARGET,
        USE,
        ITEM,
        JAMMER,
        ADR_TARGET,
        ADR_ITEM,
        INSPECT,
        LOOK,
        BACK,
        MAGNIFY,
    }


def decode(data: str) -> LobbyCallback | SeqCallback:
    parts = data.split(":")
    if not parts:
        raise CallbackParseError("empty")
    kind = parts[0]
    try:
        if kind in (JOIN, LEAVE, START, RULES, QUIT):
            return LobbyCallback(kind=kind, game_id=int(parts[1]))
        game_id = int(parts[1])
        action_seq = int(parts[2])
        if kind in (SHOOT, USE, INSPECT, BACK, MAGNIFY):
            return SeqCallback(kind=kind, game_id=game_id, action_seq=action_seq)
        if kind in (TARGET, JAMMER, ADR_TARGET, LOOK):
            return SeqCallback(
                kind=kind, game_id=game_id, action_seq=action_seq, target_id=int(parts[3])
            )
        if kind in (ITEM, ADR_ITEM):
            item = CODE_TO_ITEM[parts[3]]
            return SeqCallback(kind=kind, game_id=game_id, action_seq=action_seq, item=item)
    except (ValueError, IndexError, KeyError) as exc:
        raise CallbackParseError(str(exc)) from exc
    raise CallbackParseError(f"unknown kind {kind}")
