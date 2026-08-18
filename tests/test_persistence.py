import tempfile
from pathlib import Path

from bot.database import db, repository
from bot.game import engine
from bot.game.models import Direction, GameState, GameStatus


def test_save_and_load_game_round_trip():
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "test.sqlite3")
        conn = db.connect(path)

        state = GameState(game_id=0, chat_id=-100, topic_id=5)
        engine.join_lobby(state, 1, "alice", "Alice")
        engine.join_lobby(state, 2, "bob", "Bob")
        engine.start_game(state)

        game_id = repository.save_game(conn, state)
        assert game_id == state.game_id

        loaded = repository.load_game(conn, -100, 5)
        assert loaded is not None
        assert loaded.status == GameStatus.ACTIVE
        assert len(loaded.players) == 2
        assert len(loaded.spawns) == 2
        assert loaded.turn_order == state.turn_order
        assert all(s.activated_by_other is False for s in loaded.spawns)
        assert all(s.owner_user_id in {p.user_id for p in loaded.players} for s in loaded.spawns)

        conn.close()


def test_load_all_active_excludes_finished_games():
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "test2.sqlite3")
        conn = db.connect(path)

        active_state = GameState(game_id=0, chat_id=-1, topic_id=1)
        engine.join_lobby(active_state, 1, "a", "A")
        engine.join_lobby(active_state, 2, "b", "B")
        engine.start_game(active_state)
        repository.save_game(conn, active_state)

        finished_state = GameState(game_id=0, chat_id=-2, topic_id=2, status=GameStatus.FINISHED)
        repository.save_game(conn, finished_state)

        loaded = repository.load_all_active(conn)
        assert len(loaded) == 1
        assert loaded[0].chat_id == -1

        conn.close()


def test_pending_action_round_trips():
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "test3.sqlite3")
        conn = db.connect(path)

        state = GameState(game_id=0, chat_id=-1, topic_id=None)
        engine.join_lobby(state, 1, "a", "A")
        engine.join_lobby(state, 2, "b", "B")
        engine.start_game(state)
        # Force a bishop so we can create a pending distance-selection action.
        state.players[0].position = state.players[0].position
        from bot.game.models import PieceType

        state.players[0].piece_type = PieceType.BISHOP
        state.turn_order = [state.players[0].user_id, state.players[1].user_id]
        state.turn_index = 0

        repository.save_game(conn, state)
        loaded = repository.load_game(conn, -1, None)
        assert loaded.players[0].piece_type == PieceType.BISHOP

        conn.close()
