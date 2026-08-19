"""Serialization and CRUD for :class:`GameState` rows."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from ..game.board import Position
from ..game.models import (
    GameState,
    GameStatus,
    PendingAction,
    Player,
    PieceColor,
    PieceType,
    Direction,
    Spawn,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _position_to_json(position: Position | None) -> list[int] | None:
    if position is None:
        return None
    return [position.col, position.row]


def _position_from_json(data: list[int] | None) -> Position | None:
    if data is None:
        return None
    return Position(data[0], data[1])


def _player_to_dict(player: Player) -> dict:
    return {
        "user_id": player.user_id,
        "username": player.username,
        "display_name": player.display_name,
        "color": player.color.value,
        "piece_type": player.piece_type.value,
        "position": _position_to_json(player.position),
        "alive": player.alive,
        "left": player.left,
        "join_order": player.join_order,
    }


def _player_from_dict(data: dict) -> Player:
    return Player(
        user_id=data["user_id"],
        username=data["username"],
        display_name=data["display_name"],
        color=PieceColor(data["color"]),
        piece_type=PieceType(data["piece_type"]),
        position=_position_from_json(data["position"]),
        alive=data["alive"],
        left=data["left"],
        join_order=data["join_order"],
    )


def _spawn_to_dict(spawn: Spawn) -> dict:
    return {
        "owner_user_id": spawn.owner_user_id,
        "position": _position_to_json(spawn.position),
        "activated_by_other": spawn.activated_by_other,
        "activated": spawn.activated_by_other,
    }


def _spawn_from_dict(data: dict) -> Spawn:
    unlocked = bool(data.get("activated_by_other", data.get("activated", False)))
    return Spawn(
        owner_user_id=data["owner_user_id"],
        position=_position_from_json(data["position"]),
        activated_by_other=unlocked,
    )


def _pending_to_dict(pending: PendingAction | None) -> dict | None:
    if pending is None:
        return None
    return {
        "user_id": pending.user_id,
        "direction": pending.direction.value,
        "max_distance": pending.max_distance,
        "move_seq": pending.move_seq,
        "message_id": pending.message_id,
    }


def _pending_from_dict(data: dict | None) -> PendingAction | None:
    if data is None:
        return None
    return PendingAction(
        user_id=data["user_id"],
        direction=Direction(data["direction"]),
        max_distance=data["max_distance"],
        move_seq=data["move_seq"],
        message_id=data.get("message_id"),
    )


def state_to_json(state: GameState) -> str:
    payload = {
        "game_id": state.game_id,
        "chat_id": state.chat_id,
        "topic_id": state.topic_id,
        "status": state.status.value,
        "players": [_player_to_dict(p) for p in state.players],
        "spawns": [_spawn_to_dict(s) for s in state.spawns],
        "turn_order": state.turn_order,
        "turn_index": state.turn_index,
        "move_seq": state.move_seq,
        "pending_action": _pending_to_dict(state.pending_action),
        "info_message_id": state.info_message_id,
        "board_message_id": state.board_message_id,
        "rules_message_id": state.rules_message_id,
        "lobby_message_id": state.lobby_message_id,
        "start_message_id": state.start_message_id,
        "distance_message_id": state.distance_message_id,
        "announce_message_id": state.announce_message_id,
        "moves_message_id": state.moves_message_id,
        "last_announcements": state.last_announcements,
        "status_line": state.status_line,
        "chat_line": state.chat_line,
        "showing_rules": state.showing_rules,
        "draw_votes": state.draw_votes,
        "draw_proposer_user_id": state.draw_proposer_user_id,
        "tracked_message_ids": state.tracked_message_ids,
        "winner_user_id": state.winner_user_id,
        "draw_user_ids": state.draw_user_ids,
    }
    return json.dumps(payload)


def state_from_json(data: str) -> GameState:
    payload = json.loads(data)
    return GameState(
        game_id=payload["game_id"],
        chat_id=payload["chat_id"],
        topic_id=payload["topic_id"],
        status=GameStatus(payload["status"]),
        players=[_player_from_dict(p) for p in payload["players"]],
        spawns=[_spawn_from_dict(s) for s in payload["spawns"]],
        turn_order=payload["turn_order"],
        turn_index=payload["turn_index"],
        move_seq=payload["move_seq"],
        pending_action=_pending_from_dict(payload["pending_action"]),
        info_message_id=payload["info_message_id"],
        board_message_id=payload["board_message_id"],
        rules_message_id=payload["rules_message_id"],
        lobby_message_id=payload["lobby_message_id"],
        start_message_id=payload["start_message_id"],
        distance_message_id=payload["distance_message_id"],
        announce_message_id=payload.get("announce_message_id"),
        moves_message_id=payload.get("moves_message_id"),
        last_announcements=payload.get("last_announcements") or [],
        status_line=payload.get("status_line"),
        chat_line=payload.get("chat_line"),
        showing_rules=payload.get("showing_rules", False),
        draw_votes=payload.get("draw_votes") or [],
        draw_proposer_user_id=payload.get("draw_proposer_user_id"),
        tracked_message_ids=payload.get("tracked_message_ids") or [],
        winner_user_id=payload["winner_user_id"],
        draw_user_ids=payload["draw_user_ids"],
    )


def save_game(conn: sqlite3.Connection, state: GameState) -> int:
    now = _now()
    if not state.game_id:
        existing = load_game(conn, state.chat_id, state.topic_id)
        if existing is not None:
            state.game_id = existing.game_id

    state_json = state_to_json(state)
    if state.game_id:
        conn.execute(
            """
            UPDATE games
            SET chat_id = ?, topic_id = ?, status = ?, state_json = ?, updated_at = ?
            WHERE game_id = ?
            """,
            (state.chat_id, state.topic_id, state.status.value, state_json, now, state.game_id),
        )
        conn.commit()
        return state.game_id

    cursor = conn.execute(
        """
        INSERT INTO games (chat_id, topic_id, status, state_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (state.chat_id, state.topic_id, state.status.value, state_json, now, now),
    )
    conn.commit()
    new_id = cursor.lastrowid
    state.game_id = new_id
    conn.execute(
        "UPDATE games SET state_json = ? WHERE game_id = ?",
        (state_to_json(state), new_id),
    )
    conn.commit()
    return new_id


def load_game(conn: sqlite3.Connection, chat_id: int, topic_id: int | None) -> GameState | None:
    row = conn.execute(
        "SELECT state_json FROM games WHERE chat_id = ? AND topic_id IS ?",
        (chat_id, topic_id),
    ).fetchone()
    if row is None:
        return None
    payload = json.loads(row["state_json"])
    if payload.get("kind") == "buckshot":
        return None
    return state_from_json(row["state_json"])


def load_all_active(conn: sqlite3.Connection) -> list[GameState]:
    rows = conn.execute(
        "SELECT state_json FROM games WHERE status != ?", (GameStatus.FINISHED.value,)
    ).fetchall()
    loaded = []
    for row in rows:
        payload = json.loads(row["state_json"])
        if payload.get("kind") == "buckshot":
            continue
        loaded.append(state_from_json(row["state_json"]))
    return loaded


def delete_game(conn: sqlite3.Connection, game_id: int) -> None:
    conn.execute("DELETE FROM games WHERE game_id = ?", (game_id,))
    conn.commit()
