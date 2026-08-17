"""In-memory game registry backed by SQLite persistence.

Live gameplay always operates on the in-memory :class:`GameState` objects
(fast, no per-move DB round trip needed for reads); every mutation is
written through to SQLite immediately so state survives a bot restart.
"""
from __future__ import annotations

import asyncio

from .database import db as db_module
from .database import repository
from .game.models import GameState, GameStatus

GameKey = tuple[int, int | None]


class GameManager:
    def __init__(self, database_path: str):
        self.conn = db_module.connect(database_path)
        self._by_key: dict[GameKey, GameState] = {}
        self._by_id: dict[int, GameState] = {}
        self._locks: dict[GameKey, asyncio.Lock] = {}
        self._load_existing()

    def _load_existing(self) -> None:
        for state in repository.load_all_active(self.conn):
            key = (state.chat_id, state.topic_id)
            self._by_key[key] = state
            self._by_id[state.game_id] = state

    def get_by_key(self, chat_id: int, topic_id: int | None) -> GameState | None:
        return self._by_key.get((chat_id, topic_id))

    def get_by_id(self, game_id: int) -> GameState | None:
        return self._by_id.get(game_id)

    def create(self, chat_id: int, topic_id: int | None) -> GameState:
        state = GameState(game_id=0, chat_id=chat_id, topic_id=topic_id, status=GameStatus.LOBBY)
        repository.save_game(self.conn, state)
        key = (chat_id, topic_id)
        self._by_key[key] = state
        self._by_id[state.game_id] = state
        return state

    def get_or_create(self, chat_id: int, topic_id: int | None) -> GameState:
        state = self.get_by_key(chat_id, topic_id)
        if state is None:
            state = self.create(chat_id, topic_id)
        return state

    def lock_for(self, chat_id: int, topic_id: int | None) -> asyncio.Lock:
        key = (chat_id, topic_id)
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        return lock

    def save(self, state: GameState) -> None:
        repository.save_game(self.conn, state)
        key = (state.chat_id, state.topic_id)
        self._by_key[key] = state
        self._by_id[state.game_id] = state
