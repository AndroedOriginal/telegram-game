"""UI lifecycle tests for the persistent info / board / Ходы: messages."""
from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field

from bot.emoji_assets import divider
from bot.game import engine
from bot.game.models import (
    DIRECTION_EMOJI,
    Direction,
    GameState,
    GameStatus,
    PieceType,
)
from bot.handlers import game as game_handlers
from bot.handlers.keyboards import DIRECTION_ORDER
from bot.rendering.board_renderer import render_board
from bot.rendering.messages import distance_prompt_text, moves_prompt_text


@dataclass
class FakeMessage:
    message_id: int
    text: str
    reply_markup: object = None


@dataclass
class FakeBot:
    sent: list[FakeMessage] = field(default_factory=list)
    edited: list[tuple[int, str, object]] = field(default_factory=list)
    deleted: list[int] = field(default_factory=list)
    _next_id: int = 1

    async def send_message(self, chat_id, text, **kwargs):
        msg = FakeMessage(self._next_id, text, kwargs.get("reply_markup"))
        self._next_id += 1
        self.sent.append(msg)
        return msg

    async def edit_message_text(self, chat_id, message_id, text, **kwargs):
        self.edited.append((message_id, text, kwargs.get("reply_markup")))
        return FakeMessage(message_id, text, kwargs.get("reply_markup"))

    async def edit_message_reply_markup(self, chat_id, message_id, reply_markup=None, **kwargs):
        self.edited.append((message_id, "", reply_markup))
        return FakeMessage(message_id, "", reply_markup)

    async def delete_message(self, chat_id, message_id):
        self.deleted.append(message_id)

    async def delete_messages(self, chat_id, message_ids):
        self.deleted.extend(message_ids)


def _started_state() -> GameState:
    state = GameState(game_id=1, chat_id=-100, topic_id=7, status=GameStatus.LOBBY)
    engine.join_lobby(state, 1, "alice", "Alice")
    engine.join_lobby(state, 2, "bob", "Bob")
    result = engine.start_game(state, rng=random.Random(0))
    assert result.ok
    return state


def _run(coro):
    return asyncio.run(coro)


def test_starting_a_game_creates_separate_board_and_moves_messages():
    state = _started_state()
    bot = FakeBot()
    _run(game_handlers.send_game_start_messages(bot, state))

    assert len(bot.sent) == 3
    info, board, moves = bot.sent
    assert info.message_id != board.message_id != moves.message_id
    assert info.message_id == state.info_message_id
    assert board.message_id == state.board_message_id
    assert moves.message_id == state.moves_message_id

    assert "Информация по игре" in info.text
    assert info.reply_markup is not None

    lines = board.text.split("\n")
    assert lines[0] == divider().to_html()
    assert board.text.count(divider().to_html()) == 1
    assert "<blockquote" not in board.text
    assert len(lines) == 10
    assert board.text.count("<tg-emoji") == 9 * 9 + 1
    assert board.reply_markup is None

    assert moves.text == moves_prompt_text()
    assert moves.text == "Ходы:"
    buttons = moves.reply_markup.inline_keyboard[0]
    assert len(buttons) == 8
    assert [b.text for b in buttons] == [DIRECTION_EMOJI[d] for d in DIRECTION_ORDER]
    assert len(DIRECTION_ORDER) == 8


def test_board_updates_after_a_move_and_moves_message_is_reused():
    state = _started_state()
    bot = FakeBot()
    _run(game_handlers.send_game_start_messages(bot, state))
    board_id = state.board_message_id
    moves_id = state.moves_message_id
    sent_before = len(bot.sent)

    current = state.current_player()
    other = next(p for p in state.players if p.user_id != current.user_id)
    from bot.game.board import Position

    current.position = Position.from_algebraic("D4")
    current.piece_type = PieceType.PAWN
    other.position = Position.from_algebraic("A1")
    other.piece_type = PieceType.PAWN

    result = engine.select_direction(state, current.user_id, Direction.UP, state.move_seq)
    assert result.ok and result.move_completed

    _run(game_handlers.update_game_messages(bot, state))

    assert state.board_message_id == board_id
    assert state.moves_message_id == moves_id
    assert len(bot.sent) == sent_before
    edited_ids = [item[0] for item in bot.edited]
    assert board_id in edited_ids
    assert moves_id in edited_ids
    board_edits = [text for mid, text, _ in bot.edited if mid == board_id]
    assert board_edits[-1] == render_board(state)
    assert board_edits[-1].startswith(divider().to_html() + "\n")


def test_distance_prompt_does_not_replace_moves_message():
    state = _started_state()
    bot = FakeBot()
    _run(game_handlers.send_game_start_messages(bot, state))
    moves_id = state.moves_message_id

    current = state.current_player()
    from bot.game.board import Position

    current.piece_type = PieceType.ROOK
    current.position = Position.from_algebraic("D4")
    opened = engine.select_direction(state, current.user_id, Direction.UP, state.move_seq)
    assert opened.ok
    assert opened.pending_distances

    from bot.callback_data import DirectionCallback

    callback = DirectionCallback(game_id=state.game_id, move_seq=state.move_seq, direction=Direction.UP)
    _run(game_handlers.send_distance_prompt(bot, state, callback, len(opened.pending_distances)))

    assert state.moves_message_id == moves_id
    assert state.distance_message_id is not None
    assert state.distance_message_id != moves_id
    assert state.distance_message_id != state.board_message_id
    distance_msg = bot.sent[-1]
    assert distance_msg.text == distance_prompt_text()
    assert "Ходы:" not in distance_msg.text


def test_game_messages_are_deleted_on_end():
    state = _started_state()
    bot = FakeBot()
    _run(game_handlers.send_game_start_messages(bot, state))
    ids = {
        state.info_message_id,
        state.board_message_id,
        state.moves_message_id,
    }
    _run(game_handlers.delete_game_messages(bot, state))
    assert ids <= set(bot.deleted)
    assert state.board_message_id is None
    assert state.moves_message_id is None
    assert state.info_message_id is None
