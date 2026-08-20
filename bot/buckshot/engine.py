"""Pure-Python Buckshot Roulette engine. No Telegram imports."""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from . import texts
from .models import (
    KIND,
    MAX_CARTRIDGES,
    MAX_INVENTORY,
    MAX_ITEMS_PER_ROUND,
    MAX_PLAYERS,
    MAX_ROUND_HP,
    MIN_CARTRIDGES,
    MIN_ITEMS_PER_ROUND,
    MIN_PLAYERS,
    MIN_ROUND_HP,
    BlockKind,
    EventKind,
    GameEvent,
    GameState,
    GameStatus,
    ItemType,
    PendingAction,
    PendingKind,
    Player,
    Shotgun,
)


@dataclass
class ActionResult:
    ok: bool
    reason: str | None = None
    invalid: bool = False
    announcements: list[str] = field(default_factory=list)
    events: list[GameEvent] = field(default_factory=list)
    died: bool = False
    victory: bool = False
    pending: PendingAction | None = None
    private_alert: str | None = None
    private_user_id: int | None = None
    delete_magnify: bool = False
    open_lobby: bool = False
    item_used: ItemType | None = None
    stolen_item: ItemType | None = None
    stolen_from: int | None = None
    ui_sync_at: int | None = None


def allowed_item_types(player_count: int) -> list[ItemType]:
    items = list(ItemType)
    if player_count <= 2:
        return [item for item in items if item not in (ItemType.JAMMER, ItemType.REMOTE)]
    return [item for item in items if item != ItemType.HANDCUFFS]


def unique_item_types(inventory: list[ItemType]) -> list[ItemType]:
    seen: list[ItemType] = []
    for item in inventory:
        if item not in seen:
            seen.append(item)
    return seen


def _status(state: GameState, result: ActionResult, text: str) -> None:
    result.announcements.append(text)
    result.events.append(GameEvent(kind=EventKind.STATUS, text=text))
    state.status_line = text


def _emit(result: ActionResult, event: GameEvent) -> None:
    result.events.append(event)


def _bump(state: GameState) -> None:
    state.action_seq += 1
    state.pending = None


def _remove_item(player: Player, item: ItemType) -> bool:
    try:
        player.inventory.remove(item)
        return True
    except ValueError:
        return False


def join_lobby(state: GameState, user_id: int, username: str | None, display_name: str) -> ActionResult:
    if state.status != GameStatus.LOBBY:
        return ActionResult(ok=False, reason="not_in_lobby")
    if state.get_player(user_id) is not None:
        return ActionResult(ok=False, reason="already_joined")
    if len(state.players) >= MAX_PLAYERS:
        return ActionResult(ok=False, reason="lobby_full")
    player = Player(
        user_id=user_id,
        username=username,
        display_name=display_name,
        join_order=len(state.players),
    )
    state.players.append(player)
    result = ActionResult(ok=True)
    _status(state, result, texts.lobby_join(player))
    return result


def leave_lobby(state: GameState, user_id: int) -> ActionResult:
    if state.status != GameStatus.LOBBY:
        return ActionResult(ok=False, reason="not_in_lobby")
    player = state.get_player(user_id)
    if player is None:
        return ActionResult(ok=False, reason="not_joined")
    state.players.remove(player)
    result = ActionResult(ok=True)
    if len(state.players) < MIN_PLAYERS:
        _status(state, result, texts.not_enough_players())
    else:
        _status(state, result, texts.lobby_leave(player))
    return result


def _deal_items(state: GameState, rng: random.Random) -> None:
    alive = state.active_players()
    pool = allowed_item_types(len(alive))
    state.last_item_drops = {}
    state.last_no_space = set()
    for player in alive:
        count = rng.randint(MIN_ITEMS_PER_ROUND, MAX_ITEMS_PER_ROUND)
        received: list[ItemType] = []
        no_space = False
        for _ in range(count):
            item = rng.choice(pool)
            if len(player.inventory) >= MAX_INVENTORY:
                no_space = True
                break
            player.inventory.append(item)
            received.append(item)
        state.last_item_drops[player.user_id] = received
        if no_space or (count > 0 and len(received) < count and len(player.inventory) >= MAX_INVENTORY):
            state.last_no_space.add(player.user_id)


def _emit_round_intro(state: GameState, result: ActionResult) -> None:
    for player in state.players_in_turn_order():
        if not player.is_active:
            continue
        received = list(state.last_item_drops.get(player.user_id) or [])
        _emit(
            result,
            GameEvent(
                kind=EventKind.ITEMS,
                player_id=player.user_id,
                items=received,
                no_space=player.user_id in state.last_no_space,
            ),
        )
    _emit(result, GameEvent(kind=EventKind.SHOTGUN))
    state.round_intro_pending = False


def load_shotgun(rng: random.Random, total: int | None = None) -> tuple[Shotgun, list[bool]]:
    if total is None:
        total = rng.randint(MIN_CARTRIDGES, MAX_CARTRIDGES)
    total = max(MIN_CARTRIDGES, min(MAX_CARTRIDGES, total))
    live = rng.randint(1, total - 1)
    blank = total - live
    real = [True] * live + [False] * blank
    display = list(real)
    rng.shuffle(display)
    rng.shuffle(real)
    return Shotgun(cartridges=real, knife_active=False), display


def _begin_round(state: GameState, rng: random.Random) -> None:
    state.round_number += 1
    state.round_max_hp = rng.randint(MIN_ROUND_HP, MAX_ROUND_HP)
    for player in state.active_players():
        if state.round_number == 1:
            player.max_hp = state.round_max_hp
            player.hp = state.round_max_hp
        else:
            player.max_hp = state.round_max_hp
            if player.hp > player.max_hp:
                player.hp = player.max_hp
    _deal_items(state, rng)
    shotgun, display = load_shotgun(rng)
    state.shotgun = shotgun
    state.shotgun_display = display
    state.round_intro_pending = True


def _alive_in_order(state: GameState) -> list[Player]:
    players = []
    n = len(state.turn_order)
    if not n:
        return players
    for step in range(n):
        index = (state.turn_index + step * state.turn_direction) % n
        player = state.get_player(state.turn_order[index])
        if player is not None and player.is_active:
            players.append(player)
    return players


def _check_victory(state: GameState, result: ActionResult) -> bool:
    alive = state.active_players()
    if len(alive) == 1:
        winner = alive[0]
        state.status = GameStatus.FINISHED
        state.winner_user_id = winner.user_id
        result.victory = True
        result.open_lobby = True
        _status(state, result, texts.victory_announcement(winner))
        return True
    if len(alive) == 0:
        state.status = GameStatus.FINISHED
        result.open_lobby = True
        return True
    return False


def _kill(state: GameState, player: Player, result: ActionResult) -> None:
    player.alive = False
    player.block = None
    result.died = True
    _status(state, result, texts.dies_announcement(player))


def _damage(state: GameState, player: Player, amount: int, result: ActionResult) -> None:
    if amount <= 0 or not player.is_active:
        return
    player.hp = max(0, player.hp - amount)
    if amount >= 2:
        _status(state, result, texts.lose_two_hp(player))
    else:
        _status(state, result, texts.lose_one_hp(player))
    if player.hp <= 0:
        _kill(state, player, result)


def _heal(state: GameState, player: Player, amount: int, cap: int, result: ActionResult) -> None:
    if amount <= 0:
        return
    before = player.hp
    player.hp = min(cap, player.hp + amount)
    if amount >= 2:
        _status(state, result, texts.restore_two_hp(player))
    else:
        _status(state, result, texts.restore_one_hp(player))
    if player.hp == before:
        return


def _advance_index(state: GameState) -> None:
    if not state.turn_order:
        return
    n = len(state.turn_order)
    state.turn_index = (state.turn_index + state.turn_direction) % n


def _set_own_inventory_commentary(state: GameState) -> None:
    current = state.current_player()
    if current is None:
        state.commentary = ""
        return
    state.looking_at_user_id = current.user_id
    # Handlers render inventory HTML; engine stores a plain marker plus names.
    names = ", ".join(texts.item_name(item) for item in current.inventory) or "пусто"
    state.commentary = f"inventory:{current.user_id}:{names}"


def begin_current_turn(state: GameState, result: ActionResult | None = None) -> ActionResult:
    """Skip blocked players until an acting player is found, or victory."""

    result = result or ActionResult(ok=True)
    if state.status != GameStatus.ACTIVE:
        return result
    n = len(state.turn_order)
    for _ in range(n + 1):
        if _check_victory(state, result):
            return result
        player = state.current_player()
        if player is None or not player.is_active:
            _advance_index(state)
            continue
        if player.block is not None:
            _status(state, result, texts.skip_turn(player))
            player.block = None
            _advance_index(state)
            continue
        state.pending = None
        state.looking_at_user_id = player.user_id
        _set_own_inventory_commentary(state)
        _status(state, result, texts.turn_announcement(player))
        _emit(result, GameEvent(kind=EventKind.INVENTORY, player_id=player.user_id))
        return result
    return result


def start_game(state: GameState, rng: random.Random | None = None) -> ActionResult:
    if state.status != GameStatus.LOBBY:
        return ActionResult(ok=False, reason="not_in_lobby")
    if len(state.players) < MIN_PLAYERS:
        return ActionResult(ok=False, reason="not_enough_players")
    rng = rng or random
    for player in state.players:
        player.alive = True
        player.left = False
        player.inventory = []
        player.block = None
    order = [p.user_id for p in state.players]
    rng.shuffle(order)
    state.turn_order = order
    state.turn_index = 0
    state.turn_direction = 1
    state.round_number = 0
    state.winner_user_id = None
    state.status = GameStatus.ACTIVE
    _begin_round(state, rng)
    result = ActionResult(ok=True)
    _emit_round_intro(state, result)
    result.ui_sync_at = len(result.events)
    begin_current_turn(state, result)
    return result


def _ensure_actor(state: GameState, user_id: int, action_seq: int | None) -> tuple[Player | None, str | None]:
    if state.status != GameStatus.ACTIVE:
        return None, "not_active"
    current = state.current_player()
    if current is None or current.user_id != user_id:
        return None, "not_your_turn"
    if not current.is_active:
        return None, "not_a_player"
    if action_seq is not None and action_seq != state.action_seq:
        return None, "stale"
    return current, None


def _maybe_reload(state: GameState, rng: random.Random, result: ActionResult) -> None:
    if state.shotgun.cartridges:
        return
    _begin_round(state, rng)
    _emit_round_intro(state, result)


def open_shoot(state: GameState, user_id: int, action_seq: int) -> ActionResult:
    player, error = _ensure_actor(state, user_id, action_seq)
    if error:
        return ActionResult(ok=False, reason=error)
    _bump(state)
    state.pending = PendingAction(
        kind=PendingKind.SHOOT_TARGET, user_id=user_id, action_seq=state.action_seq
    )
    result = ActionResult(ok=True, pending=state.pending)
    _status(state, result, texts.shotgun_pickup_announcement(player))
    return result


def shoot(state: GameState, user_id: int, target_id: int, action_seq: int, rng: random.Random | None = None) -> ActionResult:
    rng = rng or random
    player, error = _ensure_actor(state, user_id, action_seq)
    if error:
        return ActionResult(ok=False, reason=error)
    target = state.get_player(target_id)
    if target is None or not target.is_active:
        return ActionResult(ok=False, reason="bad_target", invalid=True)
    result = ActionResult(ok=True)
    if not state.shotgun.cartridges:
        _maybe_reload(state, rng, result)
        if not state.shotgun.cartridges:
            return ActionResult(ok=False, reason="empty_shotgun")

    self_shot = target.user_id == player.user_id
    if self_shot:
        _status(state, result, texts.shoots_self_announcement(player))
    else:
        _status(state, result, texts.shoots_other_announcement(player, target))

    live = state.shotgun.pop()
    doubled = state.shotgun.knife_active
    state.shotgun.knife_active = False
    state.round_intro_pending = False
    if live:
        _status(state, result, texts.live_shot())
        amount = 2 if doubled else 1
        _damage(state, target, amount, result)
    else:
        _status(state, result, texts.blank_click())

    _bump(state)
    if _check_victory(state, result):
        return result

    keep_turn = self_shot and not live and player.is_active
    _maybe_reload(state, rng, result)
    result.ui_sync_at = len(result.events)
    if keep_turn:
        _set_own_inventory_commentary(state)
    else:
        if player.is_active:
            _advance_index(state)
        begin_current_turn(state, result)
    result.delete_magnify = True
    return result


def open_use_item(state: GameState, user_id: int, action_seq: int) -> ActionResult:
    player, error = _ensure_actor(state, user_id, action_seq)
    if error:
        return ActionResult(ok=False, reason=error)
    if not player.inventory:
        return ActionResult(ok=False, reason="no_items", invalid=True)
    _bump(state)
    state.pending = PendingAction(kind=PendingKind.USE_ITEM, user_id=user_id, action_seq=state.action_seq)
    result = ActionResult(ok=True, pending=state.pending)
    _status(state, result, texts.inventory_announcement(player))
    return result


def open_inspect(state: GameState, user_id: int, action_seq: int) -> ActionResult:
    _, error = _ensure_actor(state, user_id, action_seq)
    if error:
        return ActionResult(ok=False, reason=error)
    _bump(state)
    state.pending = PendingAction(
        kind=PendingKind.INSPECT_TARGET, user_id=user_id, action_seq=state.action_seq
    )
    return ActionResult(ok=True, pending=state.pending)


def inspect_player(state: GameState, user_id: int, target_id: int, action_seq: int) -> ActionResult:
    player, error = _ensure_actor(state, user_id, action_seq)
    if error:
        return ActionResult(ok=False, reason=error)
    target = state.get_player(target_id)
    if target is None or target.user_id == user_id or target.left:
        return ActionResult(ok=False, reason="bad_target", invalid=True)
    state.looking_at_user_id = target.user_id
    state.commentary = f"look:{player.user_id}:{target.user_id}"
    state.pending = PendingAction(
        kind=PendingKind.INSPECT_TARGET,
        user_id=user_id,
        action_seq=state.action_seq,
        target_user_id=target_id,
    )
    result = ActionResult(ok=True, pending=state.pending)
    _emit(
        result,
        GameEvent(kind=EventKind.LOOK, player_id=player.user_id, other_id=target.user_id),
    )
    return result


def inspect_back(state: GameState, user_id: int, action_seq: int) -> ActionResult:
    _, error = _ensure_actor(state, user_id, action_seq)
    if error:
        return ActionResult(ok=False, reason=error)
    _set_own_inventory_commentary(state)
    state.pending = None
    result = ActionResult(ok=True)
    _emit(result, GameEvent(kind=EventKind.INVENTORY, player_id=user_id))
    return result


def _start_item_flow(
    state: GameState,
    actor: Player,
    item: ItemType,
    result: ActionResult,
    rng: random.Random,
    *,
    stolen_from: Player | None = None,
) -> ActionResult:
    result.item_used = item
    if stolen_from is not None:
        result.stolen_item = item
        result.stolen_from = stolen_from.user_id
        _status(state, result, texts.steals(actor, texts.item_name(item), stolen_from))
        _emit(
            result,
            GameEvent(
                kind=EventKind.STEAL,
                player_id=actor.user_id,
                other_id=stolen_from.user_id,
                item=item,
            ),
        )

    if item == ItemType.BEER:
        return _use_beer(state, actor, result, rng)
    if item == ItemType.INVERTER:
        state.shotgun.invert_current()
        _bump(state)
        return result
    if item == ItemType.MAGNIFYING_GLASS:
        _bump(state)
        state.pending = PendingAction(
            kind=PendingKind.MAGNIFY, user_id=actor.user_id, action_seq=state.action_seq
        )
        result.pending = state.pending
        return result
    if item == ItemType.CIGARETTES:
        _heal(state, actor, 1, state.round_max_hp, result)
        _bump(state)
        return result
    if item == ItemType.HANDCUFFS:
        opponents = [p for p in state.active_players() if p.user_id != actor.user_id]
        if len(opponents) != 1:
            return ActionResult(ok=False, reason="handcuffs_need_duel", invalid=True)
        return _apply_block(state, actor, opponents[0], BlockKind.HANDCUFFS, result)
    if item == ItemType.JAMMER:
        _bump(state)
        state.pending = PendingAction(
            kind=PendingKind.JAMMER_TARGET, user_id=actor.user_id, action_seq=state.action_seq
        )
        result.pending = state.pending
        return result
    if item == ItemType.KNIFE:
        state.shotgun.knife_active = True
        _bump(state)
        return result
    if item == ItemType.EXPIRED_PILLS:
        return _use_pills(state, actor, result, rng)
    if item == ItemType.ADRENALINE:
        stealable = state.stealable_players(actor.user_id)
        if not stealable:
            return ActionResult(ok=False, reason="no_steal_target", invalid=True)
        _bump(state)
        if len(stealable) == 1:
            state.pending = PendingAction(
                kind=PendingKind.ADRENALINE_ITEM,
                user_id=actor.user_id,
                action_seq=state.action_seq,
                target_user_id=stealable[0].user_id,
            )
        else:
            state.pending = PendingAction(
                kind=PendingKind.ADRENALINE_TARGET,
                user_id=actor.user_id,
                action_seq=state.action_seq,
            )
        result.pending = state.pending
        return result
    if item == ItemType.REMOTE:
        state.turn_direction *= -1
        _bump(state)
        return result
    return ActionResult(ok=False, reason="unknown_item")


def _use_beer(state: GameState, actor: Player, result: ActionResult, rng: random.Random) -> ActionResult:
    if not state.shotgun.cartridges:
        _maybe_reload(state, rng, result)
    if not state.shotgun.cartridges:
        return ActionResult(ok=False, reason="empty_shotgun")
    live = state.shotgun.pop()
    state.shotgun.knife_active = False
    _status(state, result, texts.live_ejected() if live else texts.blank_ejected())
    _bump(state)
    if _check_victory(state, result):
        return result
    _maybe_reload(state, rng, result)
    _set_own_inventory_commentary(state)
    return result


def _use_pills(state: GameState, actor: Player, result: ActionResult, rng: random.Random) -> ActionResult:
    if rng.random() < 0.5:
        _heal(state, actor, 2, state.round_max_hp, result)
    else:
        _damage(state, actor, 1, result)
    _bump(state)
    if _check_victory(state, result):
        return result
    result.ui_sync_at = len(result.events)
    if not actor.is_active:
        begin_current_turn(state, result)
        return result
    return result


def _apply_block(
    state: GameState, actor: Player, target: Player, kind: BlockKind, result: ActionResult
) -> ActionResult:
    if not target.is_active or target.user_id == actor.user_id:
        return ActionResult(ok=False, reason="bad_target", invalid=True)
    target.block = kind
    _status(state, result, texts.blocks(actor, target))
    _bump(state)
    return result


def use_item(state: GameState, user_id: int, item: ItemType, action_seq: int, rng: random.Random | None = None) -> ActionResult:
    rng = rng or random
    player, error = _ensure_actor(state, user_id, action_seq)
    if error:
        return ActionResult(ok=False, reason=error)
    if item not in player.inventory:
        return ActionResult(ok=False, reason="missing_item", invalid=True)
    if item == ItemType.HANDCUFFS and len(state.active_players()) != 2:
        return ActionResult(ok=False, reason="handcuffs_forbidden", invalid=True)
    if item in (ItemType.JAMMER, ItemType.REMOTE) and len(state.active_players()) <= 2:
        return ActionResult(ok=False, reason="item_forbidden", invalid=True)
    consume_now = item not in (ItemType.JAMMER, ItemType.ADRENALINE)
    if consume_now and not _remove_item(player, item):
        return ActionResult(ok=False, reason="missing_item", invalid=True)
    result = ActionResult(ok=True)
    started = _start_item_flow(state, player, item, result, rng)
    if not started.ok and consume_now:
        player.inventory.append(item)
    if started.ok:
        state.round_intro_pending = False
    return started


def choose_jammer_target(state: GameState, user_id: int, target_id: int, action_seq: int) -> ActionResult:
    player, error = _ensure_actor(state, user_id, action_seq)
    if error:
        return ActionResult(ok=False, reason=error)
    pending = state.pending
    if pending is None or pending.kind != PendingKind.JAMMER_TARGET:
        return ActionResult(ok=False, reason="stale")
    target = state.get_player(target_id)
    if target is None:
        return ActionResult(ok=False, reason="bad_target", invalid=True)
    if ItemType.JAMMER in player.inventory:
        _remove_item(player, ItemType.JAMMER)
    result = ActionResult(ok=True)
    return _apply_block(state, player, target, BlockKind.JAMMER, result)


def choose_adrenaline_target(state: GameState, user_id: int, target_id: int, action_seq: int) -> ActionResult:
    _, error = _ensure_actor(state, user_id, action_seq)
    if error:
        return ActionResult(ok=False, reason=error)
    pending = state.pending
    if pending is None or pending.kind != PendingKind.ADRENALINE_TARGET:
        return ActionResult(ok=False, reason="stale")
    target = state.get_player(target_id)
    if target is None or target.user_id == user_id or target.left or not target.inventory:
        return ActionResult(ok=False, reason="bad_target", invalid=True)
    _bump(state)
    state.pending = PendingAction(
        kind=PendingKind.ADRENALINE_ITEM,
        user_id=user_id,
        action_seq=state.action_seq,
        target_user_id=target_id,
    )
    return ActionResult(ok=True, pending=state.pending)


def steal_and_use(
    state: GameState, user_id: int, item: ItemType, action_seq: int, rng: random.Random | None = None
) -> ActionResult:
    rng = rng or random
    player, error = _ensure_actor(state, user_id, action_seq)
    if error:
        return ActionResult(ok=False, reason=error)
    pending = state.pending
    if pending is None or pending.kind != PendingKind.ADRENALINE_ITEM or pending.target_user_id is None:
        return ActionResult(ok=False, reason="stale")
    victim = state.get_player(pending.target_user_id)
    if victim is None or victim.left or item not in victim.inventory:
        return ActionResult(ok=False, reason="missing_item", invalid=True)
    if ItemType.ADRENALINE in player.inventory:
        _remove_item(player, ItemType.ADRENALINE)
    _remove_item(victim, item)
    result = ActionResult(ok=True)
    return _start_item_flow(state, player, item, result, rng, stolen_from=victim)


def peek_cartridge(state: GameState, user_id: int, action_seq: int) -> ActionResult:
    _, error = _ensure_actor(state, user_id, action_seq)
    if error:
        alert = "\u26a0\ufe0f Вы не можете посмотреть действующий патрон."
        return ActionResult(ok=False, reason=error, private_alert=alert, private_user_id=user_id)
    pending = state.pending
    if pending is None or pending.kind != PendingKind.MAGNIFY:
        return ActionResult(ok=False, reason="stale")
    current = state.shotgun.current
    if current is None:
        return ActionResult(ok=False, reason="empty_shotgun")
    alert = "\u2620\ufe0f Боевой" if current else "\U0001f6e1\ufe0f Холостой"
    _bump(state)
    return ActionResult(
        ok=True,
        private_alert=alert,
        private_user_id=user_id,
        delete_magnify=True,
    )


def peek_denied() -> ActionResult:
    return ActionResult(
        ok=False,
        reason="not_your_turn",
        private_alert="\u26a0\ufe0f Вы не можете посмотреть действующий патрон.",
    )


def leave_game(state: GameState, user_id: int) -> ActionResult:
    if state.status != GameStatus.ACTIVE:
        return ActionResult(ok=False, reason="not_active")
    player = state.get_player(user_id)
    if player is None or not player.is_active:
        return ActionResult(ok=False, reason="not_a_player")
    was_current = state.current_player() is not None and state.current_player().user_id == user_id
    player.left = True
    player.alive = False
    player.block = None
    player.inventory = []
    result = ActionResult(ok=True)
    _status(state, result, texts.leave_announcement(player))
    if _check_victory(state, result):
        return result
    _bump(state)
    result.ui_sync_at = len(result.events)
    if was_current:
        begin_current_turn(state, result)
    return result


def end_game(state: GameState) -> ActionResult:
    state.status = GameStatus.FINISHED
    state.pending = None
    result = ActionResult(ok=True, open_lobby=True)
    _status(state, result, "\U0001f508 Игра завершена.")
    return result


def game_kind() -> str:
    return KIND
