"""Dataclasses and enums for the Buckshot Roulette engine."""
from __future__ import annotations

import enum
from dataclasses import dataclass, field

KIND = "buckshot"

MIN_PLAYERS = 2
MAX_PLAYERS = 4
MIN_ITEMS_PER_ROUND = 2
MAX_ITEMS_PER_ROUND = 5
MAX_INVENTORY = 8
MIN_CARTRIDGES = 3
MAX_CARTRIDGES = 8
MIN_ROUND_HP = 2
MAX_ROUND_HP = 4


class ItemType(enum.Enum):
    BEER = "beer"
    INVERTER = "inverter"
    MAGNIFYING_GLASS = "magnifying_glass"
    CIGARETTES = "cigarettes"
    HANDCUFFS = "handcuffs"
    KNIFE = "knife"
    EXPIRED_PILLS = "expired_pills"
    JAMMER = "jammer"
    ADRENALINE = "adrenaline"
    REMOTE = "remote"


ITEM_NAME_RU: dict[ItemType, str] = {
    ItemType.BEER: "Банка пива",
    ItemType.INVERTER: "Инвертор",
    ItemType.MAGNIFYING_GLASS: "Лупа",
    ItemType.CIGARETTES: "Сигареты",
    ItemType.HANDCUFFS: "Наручники",
    ItemType.KNIFE: "Нож",
    ItemType.EXPIRED_PILLS: "Просроченные таблетки",
    ItemType.JAMMER: "Джаммер",
    ItemType.ADRENALINE: "Адреналин",
    ItemType.REMOTE: "Пульт",
}

ITEM_CODE: dict[ItemType, str] = {
    ItemType.BEER: "be",
    ItemType.INVERTER: "in",
    ItemType.MAGNIFYING_GLASS: "mg",
    ItemType.CIGARETTES: "ci",
    ItemType.HANDCUFFS: "hc",
    ItemType.KNIFE: "kn",
    ItemType.EXPIRED_PILLS: "ep",
    ItemType.JAMMER: "ja",
    ItemType.ADRENALINE: "ad",
    ItemType.REMOTE: "re",
}

CODE_TO_ITEM: dict[str, ItemType] = {code: item for item, code in ITEM_CODE.items()}


class BlockKind(enum.Enum):
    HANDCUFFS = "handcuffs"
    JAMMER = "jammer"


class GameStatus(enum.Enum):
    LOBBY = "lobby"
    ACTIVE = "active"
    FINISHED = "finished"


class PendingKind(enum.Enum):
    SHOOT_TARGET = "shoot_target"
    USE_ITEM = "use_item"
    JAMMER_TARGET = "jammer_target"
    HANDCUFFS_TARGET = "handcuffs_target"
    ADRENALINE_TARGET = "adrenaline_target"
    ADRENALINE_ITEM = "adrenaline_item"
    INSPECT_TARGET = "inspect_target"
    MAGNIFY = "magnify"


@dataclass
class Player:
    user_id: int
    username: str | None
    display_name: str
    hp: int = 0
    max_hp: int = 0
    alive: bool = True
    left: bool = False
    inventory: list[ItemType] = field(default_factory=list)
    block: BlockKind | None = None
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
class Shotgun:
    cartridges: list[bool] = field(default_factory=list)  # True = live
    knife_active: bool = False

    @property
    def current(self) -> bool | None:
        if not self.cartridges:
            return None
        return self.cartridges[0]

    def pop(self) -> bool:
        return self.cartridges.pop(0)

    def invert_current(self) -> None:
        if self.cartridges:
            self.cartridges[0] = not self.cartridges[0]


@dataclass
class PendingAction:
    kind: PendingKind
    user_id: int
    action_seq: int
    target_user_id: int | None = None
    item: ItemType | None = None
    stolen_from_user_id: int | None = None
    message_id: int | None = None


@dataclass
class GameState:
    game_id: int
    chat_id: int
    topic_id: int | None
    status: GameStatus = GameStatus.LOBBY
    players: list[Player] = field(default_factory=list)
    turn_order: list[int] = field(default_factory=list)
    turn_index: int = 0
    turn_direction: int = 1
    round_number: int = 0
    round_max_hp: int = 3
    shotgun: Shotgun = field(default_factory=Shotgun)
    shotgun_display: list[bool] = field(default_factory=list)
    pending: PendingAction | None = None
    action_seq: int = 0
    status_line: str | None = None
    commentary: str = ""
    looking_at_user_id: int | None = None
    winner_user_id: int | None = None
    info_message_id: int | None = None
    commentary_message_id: int | None = None
    actions_message_id: int | None = None
    rules_message_id: int | None = None
    lobby_message_id: int | None = None
    start_message_id: int | None = None
    announce_message_id: int | None = None
    magnify_message_id: int | None = None
    temp_message_ids: list[int] = field(default_factory=list)
    tracked_message_ids: list[int] = field(default_factory=list)
    last_item_drops: dict[int, list[ItemType]] = field(default_factory=dict)
    last_no_space: set[int] = field(default_factory=set)
    round_intro_pending: bool = False

    kind: str = KIND

    def track_message(self, message_id: int | None) -> None:
        if message_id is not None and message_id not in self.tracked_message_ids:
            self.tracked_message_ids.append(message_id)

    def ui_message_ids(self) -> list[int]:
        ids: list[int] = []
        for value in (
            self.info_message_id,
            self.commentary_message_id,
            self.actions_message_id,
            self.rules_message_id,
            self.lobby_message_id,
            self.start_message_id,
            self.announce_message_id,
            self.magnify_message_id,
            *self.temp_message_ids,
            *self.tracked_message_ids,
        ):
            if value is not None and value not in ids:
                ids.append(value)
        return ids

    def get_player(self, user_id: int) -> Player | None:
        for player in self.players:
            if player.user_id == user_id:
                return player
        return None

    def active_players(self) -> list[Player]:
        return [p for p in self.players if p.is_active]

    def stealable_players(self, exclude_user_id: int) -> list[Player]:
        """Alive or dead, but not left and not the thief. Must have items."""

        return [
            p
            for p in self.players
            if p.user_id != exclude_user_id and not p.left and p.inventory
        ]

    def current_player(self) -> Player | None:
        if not self.turn_order:
            return None
        user_id = self.turn_order[self.turn_index % len(self.turn_order)]
        return self.get_player(user_id)

    def players_in_turn_order(self) -> list[Player]:
        ordered: list[Player] = []
        for user_id in self.turn_order:
            player = self.get_player(user_id)
            if player is not None:
                ordered.append(player)
        for player in self.players:
            if player.user_id not in self.turn_order:
                ordered.append(player)
        return ordered
