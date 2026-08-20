"""Buckshot Roulette engine tests — isolated from Chess Royale."""
from __future__ import annotations

import random
import tempfile
from pathlib import Path

from bot.buckshot import engine
from bot.buckshot.engine import allowed_item_types, load_shotgun, unique_item_types
from bot.buckshot.models import (
    MAX_INVENTORY,
    MAX_PLAYERS,
    BlockKind,
    EventKind,
    GameState,
    GameStatus,
    ItemType,
    Player,
)
from bot.buckshot.persistence import load_all_active, save_game, state_from_json, state_to_json
from bot.database import db
from bot.database import repository as chess_repository
from bot.game.models import GameState as ChessState
from bot.game.models import GameStatus as ChessStatus
from bot.manager import GameManager


def _state(*names: str) -> GameState:
    state = GameState(game_id=0, chat_id=-100, topic_id=9, status=GameStatus.LOBBY)
    for index, name in enumerate(names, start=1):
        engine.join_lobby(state, index, name, name.title())
    return state


def _start(*names: str, rng: random.Random | None = None) -> GameState:
    state = _state(*names)
    result = engine.start_game(state, rng or random.Random(0))
    assert result.ok
    return state


def test_lobby_player_limits():
    state = _state("a")
    assert len(state.players) == 1
    assert engine.start_game(state).ok is False
    engine.join_lobby(state, 2, "b", "B")
    assert engine.join_lobby(state, 2, "b", "B").reason == "already_joined"
    engine.join_lobby(state, 3, "c", "C")
    engine.join_lobby(state, 4, "d", "D")
    extra = engine.join_lobby(state, 5, "e", "E")
    assert extra.ok is False
    assert extra.reason == "lobby_full"
    assert len(state.players) == MAX_PLAYERS
    assert engine.leave_lobby(state, 99).reason == "not_joined"


def test_turn_order_is_shuffled_and_circular():
    rng = random.Random(1)
    state = _start("a", "b", "c", rng=rng)
    assert set(state.turn_order) == {1, 2, 3}
    assert state.current_player() is not None
    first = state.current_player().user_id
    engine._advance_index(state)
    second = state.current_player().user_id
    engine._advance_index(state)
    third = state.current_player().user_id
    engine._advance_index(state)
    assert state.current_player().user_id == first
    assert len({first, second, third}) == 3


def test_hp_and_round_creation():
    state = _start("a", "b", rng=random.Random(2))
    assert state.round_number == 1
    assert 2 <= state.round_max_hp <= 4
    for player in state.active_players():
        assert player.hp == state.round_max_hp
        assert 2 <= len(state.last_item_drops[player.user_id]) <= 5
        assert len(player.inventory) <= MAX_INVENTORY


def test_item_restrictions_two_and_many_players():
    two = allowed_item_types(2)
    assert ItemType.HANDCUFFS in two
    assert ItemType.JAMMER not in two
    assert ItemType.REMOTE not in two
    many = allowed_item_types(3)
    assert ItemType.HANDCUFFS not in many
    assert ItemType.JAMMER in many
    assert ItemType.REMOTE in many


def test_inventory_cap_records_no_space():
    state = _start("a", "b", rng=random.Random(0))
    a = state.get_player(1)
    a.inventory = [ItemType.BEER] * MAX_INVENTORY
    engine._deal_items(state, random.Random(0))
    assert 1 in state.last_no_space
    assert len(a.inventory) == MAX_INVENTORY


def test_shotgun_always_has_blank_and_live_and_hidden_order():
    rng = random.Random(3)
    for _ in range(30):
        shotgun, display = load_shotgun(rng)
        assert 3 <= len(shotgun.cartridges) <= 8
        assert True in shotgun.cartridges
        assert False in shotgun.cartridges
        assert sorted(display) == sorted(shotgun.cartridges)


def test_unique_item_buttons():
    inventory = [ItemType.BEER, ItemType.BEER, ItemType.KNIFE]
    assert unique_item_types(inventory) == [ItemType.BEER, ItemType.KNIFE]


def test_shoot_self_blank_and_other_live():
    state = _start("a", "b", rng=random.Random(4))
    actor = state.current_player()
    other = next(p for p in state.active_players() if p.user_id != actor.user_id)
    seq = state.action_seq
    state.shotgun.cartridges = [False]
    result = engine.shoot(state, actor.user_id, actor.user_id, seq)
    assert result.ok
    assert actor.alive
    assert state.current_player().user_id == actor.user_id
    assert any("холостого" in a for a in result.announcements)

    hp = other.hp
    state.shotgun.cartridges = [True]
    seq = state.action_seq
    result = engine.shoot(state, actor.user_id, other.user_id, seq)
    assert result.ok
    assert other.hp == hp - 1 or not other.alive
    if actor.is_active and other.is_active:
        assert state.current_player().user_id != actor.user_id


def test_beer_ejects_and_keeps_turn():
    state = _start("a", "b", rng=random.Random(5))
    actor = state.current_player()
    actor.inventory.append(ItemType.BEER)
    state.shotgun.cartridges = [True, False]
    seq = state.action_seq
    uid = actor.user_id
    result = engine.use_item(state, uid, ItemType.BEER, seq)
    assert result.ok
    assert True not in state.shotgun.cartridges or state.shotgun.cartridges == [False]
    assert state.current_player().user_id == uid
    assert ItemType.BEER not in actor.inventory or actor.inventory.count(ItemType.BEER) >= 0
    assert any("боевой" in a or "холостой" in a for a in result.announcements)


def test_inverter_flips_silently():
    state = _start("a", "b", rng=random.Random(6))
    actor = state.current_player()
    actor.inventory.append(ItemType.INVERTER)
    state.shotgun.cartridges = [True]
    seq = state.action_seq
    result = engine.use_item(state, actor.user_id, ItemType.INVERTER, seq)
    assert result.ok
    assert state.shotgun.cartridges == [False]
    assert "боевой" not in "".join(result.announcements)
    assert "холостой" not in "".join(result.announcements).replace("холостого", "")


def test_magnifying_glass_is_private():
    state = _start("a", "b", rng=random.Random(7))
    actor = state.current_player()
    other = next(p for p in state.players if p.user_id != actor.user_id)
    actor.inventory.append(ItemType.MAGNIFYING_GLASS)
    state.shotgun.cartridges = [True]
    seq = state.action_seq
    engine.use_item(state, actor.user_id, ItemType.MAGNIFYING_GLASS, seq)
    peek = engine.peek_cartridge(state, actor.user_id, state.action_seq)
    assert peek.ok
    assert peek.private_alert is not None
    assert "Боевой" in peek.private_alert
    denied = engine.peek_cartridge(state, other.user_id, state.action_seq)
    assert not denied.ok
    assert "не можете" in (denied.private_alert or "")


def test_cigarettes_cap_at_round_max():
    state = _start("a", "b", rng=random.Random(8))
    actor = state.current_player()
    actor.hp = state.round_max_hp
    actor.inventory = [ItemType.CIGARETTES]
    engine.use_item(state, actor.user_id, ItemType.CIGARETTES, state.action_seq)
    assert actor.hp == state.round_max_hp
    assert ItemType.CIGARETTES not in actor.inventory


def test_handcuffs_skip_in_duel():
    state = _start("a", "b", rng=random.Random(9))
    actor = state.current_player()
    other = next(p for p in state.active_players() if p.user_id != actor.user_id)
    actor.inventory.append(ItemType.HANDCUFFS)
    engine.use_item(state, actor.user_id, ItemType.HANDCUFFS, state.action_seq)
    assert other.block == BlockKind.HANDCUFFS
    uid = actor.user_id
    state.shotgun.cartridges = [False]
    engine.shoot(state, uid, uid, state.action_seq)
    assert state.current_player().user_id == uid
    assert other.block == BlockKind.HANDCUFFS
    state.shotgun.cartridges = [False]
    engine.shoot(state, uid, other.user_id, state.action_seq)
    assert other.block is None
    assert state.current_player().user_id == uid


def test_jammer_forbidden_in_duel_allowed_in_multi():
    duel = _start("a", "b", rng=random.Random(10))
    actor = duel.current_player()
    actor.inventory.append(ItemType.JAMMER)
    result = engine.use_item(duel, actor.user_id, ItemType.JAMMER, duel.action_seq)
    assert not result.ok
    triple = _start("a", "b", "c", rng=random.Random(11))
    actor = triple.current_player()
    actor.inventory.append(ItemType.JAMMER)
    result = engine.use_item(triple, actor.user_id, ItemType.JAMMER, triple.action_seq)
    assert result.ok
    target = next(p for p in triple.active_players() if p.user_id != actor.user_id)
    blocked = engine.choose_jammer_target(triple, actor.user_id, target.user_id, triple.action_seq)
    assert blocked.ok
    assert target.block == BlockKind.JAMMER
    self_target = engine.choose_jammer_target(triple, actor.user_id, actor.user_id, triple.action_seq)
    assert not self_target.ok or target.block == BlockKind.JAMMER


def test_knife_doubles_live_not_blank():
    state = _start("a", "b", rng=random.Random(12))
    actor = state.current_player()
    other = next(p for p in state.active_players() if p.user_id != actor.user_id)
    other.hp = 4
    state.round_max_hp = 4
    actor.inventory.append(ItemType.KNIFE)
    engine.use_item(state, actor.user_id, ItemType.KNIFE, state.action_seq)
    assert state.shotgun.knife_active
    state.shotgun.cartridges = [True]
    engine.shoot(state, actor.user_id, other.user_id, state.action_seq)
    assert other.hp == 2 or not other.alive


def test_expired_pills_can_heal_or_kill():
    class Hurt(random.Random):
        def random(self):
            return 0.9

    state = _start("a", "b", rng=random.Random(13))
    actor = state.current_player()
    actor.hp = 1
    actor.inventory.append(ItemType.EXPIRED_PILLS)
    engine.use_item(state, actor.user_id, ItemType.EXPIRED_PILLS, state.action_seq, rng=Hurt())
    assert actor.hp == 0
    assert actor.alive is False


def test_adrenaline_steals_and_activates_immediately():
    state = _start("a", "b", rng=random.Random(14))
    actor = state.current_player()
    other = next(p for p in state.active_players() if p.user_id != actor.user_id)
    other.inventory = [ItemType.CIGARETTES]
    actor.inventory.append(ItemType.ADRENALINE)
    actor.hp = 1
    opened = engine.use_item(state, actor.user_id, ItemType.ADRENALINE, state.action_seq)
    assert opened.ok
    stolen = engine.steal_and_use(state, actor.user_id, ItemType.CIGARETTES, state.action_seq)
    assert stolen.ok
    assert ItemType.CIGARETTES not in other.inventory
    assert ItemType.CIGARETTES not in actor.inventory
    assert actor.hp == 2
    assert stolen.stolen_item == ItemType.CIGARETTES


def test_adrenaline_cannot_target_self_or_missing_item():
    state = _start("a", "b", rng=random.Random(15))
    actor = state.current_player()
    actor.inventory.append(ItemType.ADRENALINE)
    engine.use_item(state, actor.user_id, ItemType.ADRENALINE, state.action_seq)
    bad = engine.choose_adrenaline_target(state, actor.user_id, actor.user_id, state.action_seq)
    assert not bad.ok
    other = next(p for p in state.players if p.user_id != actor.user_id)
    other.inventory = [ItemType.KNIFE]
    engine.choose_adrenaline_target(state, actor.user_id, other.user_id, state.action_seq)
    missing = engine.steal_and_use(state, actor.user_id, ItemType.BEER, state.action_seq)
    assert not missing.ok


def test_remote_reverses_direction():
    state = _start("a", "b", "c", rng=random.Random(16))
    actor = state.current_player()
    actor.inventory.append(ItemType.REMOTE)
    before = state.turn_direction
    engine.use_item(state, actor.user_id, ItemType.REMOTE, state.action_seq)
    assert state.turn_direction == -before
    assert state.current_player().user_id == actor.user_id


def test_death_removes_from_rotation_but_keeps_inventory():
    state = _start("a", "b", "c", rng=random.Random(17))
    actor = state.current_player()
    victim = next(p for p in state.active_players() if p.user_id != actor.user_id)
    victim.inventory = [ItemType.BEER, ItemType.KNIFE]
    victim.hp = 1
    state.shotgun.cartridges = [True]
    engine.shoot(state, actor.user_id, victim.user_id, state.action_seq)
    assert victim.alive is False
    assert victim not in state.active_players()
    assert victim.inventory == [ItemType.BEER, ItemType.KNIFE]
    assert state.get_player(victim.user_id) is not None


def test_dead_cannot_shoot_or_be_shot():
    state = _start("a", "b", "c", rng=random.Random(18))
    actor = state.current_player()
    victim = next(p for p in state.active_players() if p.user_id != actor.user_id)
    victim.hp = 1
    state.shotgun.cartridges = [True, True]
    engine.shoot(state, actor.user_id, victim.user_id, state.action_seq)
    current = state.current_player()
    result = engine.shoot(state, current.user_id, victim.user_id, state.action_seq)
    assert not result.ok


def test_steal_from_dead_player():
    state = _start("a", "b", rng=random.Random(19))
    actor = state.current_player()
    other = next(p for p in state.players if p.user_id != actor.user_id)
    other.alive = False
    other.inventory = [ItemType.CIGARETTES]
    actor.inventory.append(ItemType.ADRENALINE)
    actor.hp = 1
    engine.use_item(state, actor.user_id, ItemType.ADRENALINE, state.action_seq)
    stolen = engine.steal_and_use(state, actor.user_id, ItemType.CIGARETTES, state.action_seq)
    assert stolen.ok
    assert actor.hp == 2


def test_leave_and_victory():
    state = _start("a", "b", rng=random.Random(20))
    actor = state.current_player()
    other = next(p for p in state.active_players() if p.user_id != actor.user_id)
    result = engine.leave_game(state, other.user_id)
    assert result.victory
    assert state.status == GameStatus.FINISHED
    assert state.winner_user_id == actor.user_id


def test_stale_and_wrong_turn_rejected():
    state = _start("a", "b", rng=random.Random(21))
    actor = state.current_player()
    other = next(p for p in state.players if p.user_id != actor.user_id)
    assert engine.open_shoot(state, other.user_id, state.action_seq).reason == "not_your_turn"
    assert engine.open_shoot(state, actor.user_id, state.action_seq + 5).reason == "stale"


def test_callback_prefixes_do_not_collide_with_chess():
    from bot.buckshot.callbacks import is_buckshot_callback
    from bot.callback_data import decode

    assert is_buckshot_callback("bj:1")
    assert is_buckshot_callback("bru:1")
    assert is_buckshot_callback("bqt:1")
    assert not is_buckshot_callback("lj:1")
    chess = decode("lj:1")
    assert chess.kind == "lj"


def test_persistence_round_trip_and_chess_isolation(tmp_path: Path | None = None):
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "both.sqlite3")
        conn = db.connect(path)
        state = _start("a", "b", rng=random.Random(22))
        save_game(conn, state)
        loaded = load_all_active(conn)
        assert len(loaded) == 1
        assert loaded[0].shotgun.cartridges == state.shotgun.cartridges
        assert loaded[0].players[0].inventory == state.players[0].inventory

        chess = ChessState(game_id=0, chat_id=-1, topic_id=1, status=ChessStatus.LOBBY)
        chess_repository.save_game(conn, chess)
        chess_active = chess_repository.load_all_active(conn)
        assert all(getattr(g, "kind", None) != "buckshot" for g in chess_active)
        assert chess_repository.load_game(conn, state.chat_id, state.topic_id) is None
        conn.close()


def test_manager_keeps_games_in_separate_topics():
    with tempfile.TemporaryDirectory() as tmp:
        manager = GameManager(str(Path(tmp) / "mgr.sqlite3"))
        chess = manager.create(-100, 1)
        buckshot = manager.create_buckshot(-100, 2)
        assert manager.get_by_key(-100, 1) is chess
        assert manager.get_by_key(-100, 2) is None
        assert manager.get_buckshot_by_key(-100, 2) is buckshot
        assert manager.get_buckshot_by_key(-100, 1) is None
        chess.status = ChessStatus.ACTIVE
        manager.save(chess)
        buckshot.status = GameStatus.ACTIVE
        manager.save_buckshot(buckshot)
        assert manager.get_by_id(chess.game_id).topic_id == 1
        assert manager.get_buckshot_by_id(buckshot.game_id).topic_id == 2
        manager.conn.close()


def test_json_hides_real_sequence_from_commentary_builder():
    from bot.buckshot.ui import shotgun_commentary_html

    state = _start("a", "b", rng=random.Random(23))
    state.round_intro_pending = True
    state.shotgun.cartridges = [True, False, True]
    state.shotgun_display = [False, False, True]
    html = shotgun_commentary_html(state)
    assert "холостых" in html
    assert "заряженных" in html
    assert html.count("холостых") == 1


def _other(state: GameState, actor: Player) -> Player:
    return next(p for p in state.players if p.user_id != actor.user_id)


def test_round_intro_emits_separate_commentary_events():
    state = _state("a", "b")
    result = engine.start_game(state, random.Random(24))
    kinds = [event.kind for event in result.events]
    item_events = [event for event in result.events if event.kind == EventKind.ITEMS]
    assert len(item_events) == 2
    assert item_events[0].player_id != item_events[1].player_id
    assert kinds.count(EventKind.SHOTGUN) == 1
    shotgun_at = kinds.index(EventKind.SHOTGUN)
    assert kinds.index(EventKind.ITEMS) < shotgun_at
    assert kinds[shotgun_at + 1] == EventKind.STATUS
    assert kinds[shotgun_at + 2] == EventKind.INVENTORY
    from bot.buckshot.ui import render_event

    rendered = [render_event(state, event) for event in result.events]
    assert all(text for text in rendered)
    assert rendered[0] != rendered[1]


def test_status_events_are_separate_and_ordered_for_shot():
    state = _start("a", "b", rng=random.Random(25))
    actor = state.current_player()
    other = _other(state, actor)
    other.hp = 3
    state.shotgun.cartridges = [True]
    result = engine.shoot(state, actor.user_id, other.user_id, state.action_seq)
    statuses = [event.text for event in result.events if event.kind == EventKind.STATUS]
    assert statuses[0].endswith("стреляет в @b.") or "стреляет в" in statuses[0]
    assert any("выстрел" in text for text in statuses)
    assert any("теряет одно" in text for text in statuses)
    assert statuses.index(next(t for t in statuses if "стреляет" in t)) < statuses.index(
        next(t for t in statuses if "выстрел" in t)
    )


def test_self_blank_preserves_turn():
    state = _start("a", "b", rng=random.Random(26))
    actor = state.current_player()
    uid = actor.user_id
    state.shotgun.cartridges = [False, True]
    result = engine.shoot(state, uid, uid, state.action_seq)
    assert result.ok
    assert actor.alive
    assert state.current_player().user_id == uid
    assert any("холостого" in text for text in result.announcements)
    assert not any("делает ход" in text for text in result.announcements[2:])


def test_self_live_advances_turn():
    state = _start("a", "b", rng=random.Random(27))
    actor = state.current_player()
    uid = actor.user_id
    actor.hp = 3
    state.shotgun.cartridges = [True, False]
    result = engine.shoot(state, uid, uid, state.action_seq)
    assert result.ok
    assert actor.alive
    assert state.current_player().user_id != uid
    assert any("выстрел" in text for text in result.announcements)
    assert any("делает ход" in text for text in result.announcements)


def test_other_blank_advances_turn():
    state = _start("a", "b", rng=random.Random(28))
    actor = state.current_player()
    other = next(p for p in state.active_players() if p.user_id != actor.user_id)
    uid = actor.user_id
    hp = other.hp
    state.shotgun.cartridges = [False, True]
    result = engine.shoot(state, uid, other.user_id, state.action_seq)
    assert result.ok
    assert other.hp == hp
    assert state.current_player().user_id != uid
    assert any("холостого" in text for text in result.announcements)


def test_other_live_advances_turn():
    state = _start("a", "b", rng=random.Random(29))
    actor = state.current_player()
    other = next(p for p in state.active_players() if p.user_id != actor.user_id)
    uid = actor.user_id
    other.hp = 3
    state.shotgun.cartridges = [True, False]
    result = engine.shoot(state, uid, other.user_id, state.action_seq)
    assert result.ok
    assert other.alive
    assert state.current_player().user_id != uid
    assert any("выстрел" in text for text in result.announcements)


def test_self_live_death_does_not_keep_turn():
    state = _start("a", "b", rng=random.Random(30))
    actor = state.current_player()
    uid = actor.user_id
    actor.hp = 1
    state.shotgun.cartridges = [True]
    result = engine.shoot(state, uid, uid, state.action_seq)
    assert not actor.alive
    if result.victory:
        assert state.status == GameStatus.FINISHED
        assert state.winner_user_id != uid
    else:
        assert state.current_player() is not None
        assert state.current_player().user_id != uid


def test_victory_checked_before_advancing_dead_player():
    state = _start("a", "b", rng=random.Random(31))
    actor = state.current_player()
    other = next(p for p in state.active_players() if p.user_id != actor.user_id)
    other.hp = 1
    state.shotgun.cartridges = [True]
    result = engine.shoot(state, actor.user_id, other.user_id, state.action_seq)
    assert result.victory
    assert state.status == GameStatus.FINISHED
    assert not other.alive
    assert state.winner_user_id == actor.user_id
    assert not any(event.kind == EventKind.INVENTORY for event in result.events if event.player_id == other.user_id)


def test_rules_are_collapsed_quote():
    from bot.buckshot.ui import rules_message_text

    html = rules_message_text()
    assert "blockquote expandable" in html
    assert "Правила" in html
    assert "Если игрок стреляет в себя и патрон холостой" in html
    assert "ход всегда переходит к следующему" in html


def test_info_message_has_rules_and_leave_buttons():
    from bot.buckshot.ui import actions_keyboard, info_keyboard, info_message_html

    state = _start("a", "b", rng=random.Random(32))
    html = info_message_html(state)
    assert "Информация по игре" in html
    assert "\U0001f508" not in html
    info_labels = [button.text for row in info_keyboard(state).inline_keyboard for button in row]
    assert info_labels == ["Правила", "Выйти"]
    action_labels = [button.text for row in actions_keyboard(state).inline_keyboard for button in row]
    assert "Правила" not in action_labels
    assert "Выйти" not in action_labels
    from bot.buckshot.callbacks import QUIT, RULES, decode

    rules_cb = decode(info_keyboard(state).inline_keyboard[0][0].callback_data)
    quit_cb = decode(info_keyboard(state).inline_keyboard[0][1].callback_data)
    assert rules_cb.kind == RULES
    assert quit_cb.kind == QUIT


def test_sequencer_sends_separate_messages_in_order():
    import asyncio
    import inspect
    from types import SimpleNamespace

    from bot.buckshot.sequencer import EVENT_DELAY_SECONDS, OutgoingMessage, send_sequence

    async def _run():
        sleeps: list[float] = []

        async def fake_sleep(delay: float) -> None:
            sleeps.append(delay)

        sent: list[str] = []

        class Bot:
            async def send_message(self, **kwargs):
                sent.append(kwargs["text"])
                return SimpleNamespace(message_id=len(sent) + 40)

        state = GameState(game_id=1, chat_id=-100, topic_id=9)
        ids = await send_sequence(
            Bot(),
            state,
            [
                OutgoingMessage("🔈 @a стреляет в @b.", parse_mode=None),
                OutgoingMessage("☠️ выстрел.", parse_mode=None),
                OutgoingMessage("🔈 @b теряет одно ⚡️хп.", parse_mode=None),
            ],
            delay=0.5,
            sleep=fake_sleep,
        )
        assert sent == [
            "🔈 @a стреляет в @b.",
            "☠️ выстрел.",
            "🔈 @b теряет одно ⚡️хп.",
        ]
        assert sleeps == [0.5, 0.5]
        assert ids == [41, 42, 43]
        assert state.tracked_message_ids == ids
        assert inspect.iscoroutinefunction(send_sequence)
        assert EVENT_DELAY_SECONDS > 0

    asyncio.run(_run())


def test_sequencer_is_async_and_does_not_block():
    import inspect

    import bot.buckshot.sequencer as seq

    source = inspect.getsource(seq)
    assert "time.sleep" not in source
    assert "asyncio.sleep" in source
    assert inspect.iscoroutinefunction(seq.send_sequence)


def test_event_messages_are_tracked_for_cleanup():
    state = _start("a", "b", rng=random.Random(33))
    state.track_message(101)
    state.track_message(102)
    state.track_message(103)
    engine.end_game(state)
    ids = state.ui_message_ids()
    assert 101 in ids and 102 in ids and 103 in ids
    state.tracked_message_ids = []
    state.info_message_id = None
    state.actions_message_id = None
    assert state.ui_message_ids() == []


def test_commentary_events_render_as_separate_html_messages():
    from bot.buckshot.ui import render_event

    state = _state("a", "b")
    result = engine.start_game(state, random.Random(34))
    item_html = [
        render_event(state, event)
        for event in result.events
        if event.kind == EventKind.ITEMS
    ]
    assert len(item_html) == 2
    assert item_html[0] != item_html[1]
    assert "берет предметы" in item_html[0]
    assert "берет предметы" in item_html[1]
    shotgun = next(event for event in result.events if event.kind == EventKind.SHOTGUN)
    assert "Заряжается дробовик" in (render_event(state, shotgun) or "")
