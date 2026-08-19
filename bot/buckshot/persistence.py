"""JSON persistence for Buckshot Roulette in the shared ``games`` table."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from .models import (
    KIND,
    BlockKind,
    GameState,
    GameStatus,
    ItemType,
    PendingAction,
    PendingKind,
    Player,
    Shotgun,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _player_to_dict(player: Player) -> dict:
    return {
        "user_id": player.user_id,
        "username": player.username,
        "display_name": player.display_name,
        "hp": player.hp,
        "max_hp": player.max_hp,
        "alive": player.alive,
        "left": player.left,
        "inventory": [item.value for item in player.inventory],
        "block": player.block.value if player.block else None,
        "join_order": player.join_order,
    }


def _player_from_dict(data: dict) -> Player:
    block = data.get("block")
    return Player(
        user_id=data["user_id"],
        username=data["username"],
        display_name=data["display_name"],
        hp=data.get("hp", 0),
        max_hp=data.get("max_hp", 0),
        alive=data.get("alive", True),
        left=data.get("left", False),
        inventory=[ItemType(value) for value in data.get("inventory") or []],
        block=BlockKind(block) if block else None,
        join_order=data.get("join_order", 0),
    )


def _pending_to_dict(pending: PendingAction | None) -> dict | None:
    if pending is None:
        return None
    return {
        "kind": pending.kind.value,
        "user_id": pending.user_id,
        "action_seq": pending.action_seq,
        "target_user_id": pending.target_user_id,
        "item": pending.item.value if pending.item else None,
        "stolen_from_user_id": pending.stolen_from_user_id,
        "message_id": pending.message_id,
    }


def _pending_from_dict(data: dict | None) -> PendingAction | None:
    if data is None:
        return None
    item = data.get("item")
    return PendingAction(
        kind=PendingKind(data["kind"]),
        user_id=data["user_id"],
        action_seq=data["action_seq"],
        target_user_id=data.get("target_user_id"),
        item=ItemType(item) if item else None,
        stolen_from_user_id=data.get("stolen_from_user_id"),
        message_id=data.get("message_id"),
    )


def state_to_json(state: GameState) -> str:
    payload = {
        "kind": KIND,
        "game_id": state.game_id,
        "chat_id": state.chat_id,
        "topic_id": state.topic_id,
        "status": state.status.value,
        "players": [_player_to_dict(p) for p in state.players],
        "turn_order": state.turn_order,
        "turn_index": state.turn_index,
        "turn_direction": state.turn_direction,
        "round_number": state.round_number,
        "round_max_hp": state.round_max_hp,
        "shotgun": {
            "cartridges": list(state.shotgun.cartridges),
            "knife_active": state.shotgun.knife_active,
        },
        "shotgun_display": list(state.shotgun_display),
        "pending": _pending_to_dict(state.pending),
        "action_seq": state.action_seq,
        "status_line": state.status_line,
        "commentary": state.commentary,
        "looking_at_user_id": state.looking_at_user_id,
        "winner_user_id": state.winner_user_id,
        "info_message_id": state.info_message_id,
        "commentary_message_id": state.commentary_message_id,
        "actions_message_id": state.actions_message_id,
        "rules_message_id": state.rules_message_id,
        "lobby_message_id": state.lobby_message_id,
        "start_message_id": state.start_message_id,
        "announce_message_id": state.announce_message_id,
        "magnify_message_id": state.magnify_message_id,
        "temp_message_ids": state.temp_message_ids,
        "tracked_message_ids": state.tracked_message_ids,
        "last_item_drops": {
            str(uid): [item.value for item in items] for uid, items in state.last_item_drops.items()
        },
        "last_no_space": list(state.last_no_space),
        "round_intro_pending": state.round_intro_pending,
    }
    return json.dumps(payload)


def state_from_json(raw: str) -> GameState:
    payload = json.loads(raw)
    shotgun_data = payload.get("shotgun") or {}
    drops = {}
    for key, values in (payload.get("last_item_drops") or {}).items():
        drops[int(key)] = [ItemType(v) for v in values]
    return GameState(
        game_id=payload["game_id"],
        chat_id=payload["chat_id"],
        topic_id=payload["topic_id"],
        status=GameStatus(payload["status"]),
        players=[_player_from_dict(p) for p in payload.get("players") or []],
        turn_order=payload.get("turn_order") or [],
        turn_index=payload.get("turn_index", 0),
        turn_direction=payload.get("turn_direction", 1),
        round_number=payload.get("round_number", 0),
        round_max_hp=payload.get("round_max_hp", 3),
        shotgun=Shotgun(
            cartridges=list(shotgun_data.get("cartridges") or []),
            knife_active=bool(shotgun_data.get("knife_active")),
        ),
        shotgun_display=list(payload.get("shotgun_display") or []),
        pending=_pending_from_dict(payload.get("pending")),
        action_seq=payload.get("action_seq", 0),
        status_line=payload.get("status_line"),
        commentary=payload.get("commentary") or "",
        looking_at_user_id=payload.get("looking_at_user_id"),
        winner_user_id=payload.get("winner_user_id"),
        info_message_id=payload.get("info_message_id"),
        commentary_message_id=payload.get("commentary_message_id"),
        actions_message_id=payload.get("actions_message_id"),
        rules_message_id=payload.get("rules_message_id"),
        lobby_message_id=payload.get("lobby_message_id"),
        start_message_id=payload.get("start_message_id"),
        announce_message_id=payload.get("announce_message_id"),
        magnify_message_id=payload.get("magnify_message_id"),
        temp_message_ids=payload.get("temp_message_ids") or [],
        tracked_message_ids=payload.get("tracked_message_ids") or [],
        last_item_drops=drops,
        last_no_space=set(payload.get("last_no_space") or []),
        round_intro_pending=payload.get("round_intro_pending", False),
    )


def is_buckshot_json(raw: str) -> bool:
    try:
        return json.loads(raw).get("kind") == KIND
    except json.JSONDecodeError:
        return False


def save_game(conn: sqlite3.Connection, state: GameState) -> int:
    now = _now()
    if not state.game_id:
        row = conn.execute(
            "SELECT game_id, state_json FROM games WHERE chat_id = ? AND topic_id IS ?",
            (state.chat_id, state.topic_id),
        ).fetchone()
        if row is not None:
            state.game_id = row["game_id"]
    blob = state_to_json(state)
    if state.game_id:
        conn.execute(
            """
            UPDATE games
            SET chat_id = ?, topic_id = ?, status = ?, state_json = ?, updated_at = ?
            WHERE game_id = ?
            """,
            (state.chat_id, state.topic_id, state.status.value, blob, now, state.game_id),
        )
        conn.commit()
        return state.game_id
    cursor = conn.execute(
        """
        INSERT INTO games (chat_id, topic_id, status, state_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (state.chat_id, state.topic_id, state.status.value, blob, now, now),
    )
    conn.commit()
    state.game_id = cursor.lastrowid
    conn.execute("UPDATE games SET state_json = ? WHERE game_id = ?", (state_to_json(state), state.game_id))
    conn.commit()
    return state.game_id


def load_all_active(conn: sqlite3.Connection) -> list[GameState]:
    rows = conn.execute(
        "SELECT state_json FROM games WHERE status != ?",
        (GameStatus.FINISHED.value,),
    ).fetchall()
    games = []
    for row in rows:
        if is_buckshot_json(row["state_json"]):
            games.append(state_from_json(row["state_json"]))
    return games
