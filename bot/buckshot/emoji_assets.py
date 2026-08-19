"""Centralized custom-emoji IDs for Buckshot Roulette.

Every Buckshot custom emoji ID used by the bot must be defined here and
only here. Chess Royale IDs stay in ``bot.emoji_assets``.
"""
from __future__ import annotations

from typing import NamedTuple

BLANK_CARTRIDGE_ID = "5199448152536555700"
LIVE_CARTRIDGE_ID = "5199700816872648490"
BEER_ID = "5199659864359483842"
INVERTER_ID = "5199652464130830193"
MAGNIFYING_GLASS_ID = "5199937774513334249"
CIGARETTES_ID = "5201798753777918748"
HANDCUFFS_ID = "5199844401924319618"
KNIFE_ID = "5201745814011028430"
EXPIRED_PILLS_ID = "5199578401714774987"
JAMMER_ID = "5199865503098644195"
ADRENALINE_ID = "5201865922771462916"
ENERGY_HP_ID = "5201953385485478489"
REMOTE_ID = "5201869397400004071"
SHOTGUN_ID = "5951542323870437815"

# Placeholders must be real emoji so Telegram accepts custom-emoji entities.
BLANK_PLACEHOLDER = "\U0001f6e1\ufe0f"  # 🛡️
LIVE_PLACEHOLDER = "\u2620\ufe0f"  # ☠️
BEER_PLACEHOLDER = "\U0001f37a"  # 🍺
INVERTER_PLACEHOLDER = "\U0001f504"  # 🔄
MAGNIFYING_PLACEHOLDER = "\U0001f50e"  # 🔎
CIGARETTES_PLACEHOLDER = "\U0001f6ac"  # 🚬
HANDCUFFS_PLACEHOLDER = "\U0001f517"  # 🔗
KNIFE_PLACEHOLDER = "\U0001f52a"  # 🔪
PILLS_PLACEHOLDER = "\U0001f48a"  # 💊
JAMMER_PLACEHOLDER = "\U0001f6ab"  # 🚫
ADRENALINE_PLACEHOLDER = "\U0001f489"  # 💉
HP_PLACEHOLDER = "\u26a1"  # ⚡
REMOTE_PLACEHOLDER = "\U0001f4e1"  # 📡
SHOTGUN_PLACEHOLDER = "\U0001f52b"  # 🔫


class EmojiRef(NamedTuple):
    placeholder: str
    custom_emoji_id: str

    def to_html(self) -> str:
        return f'<tg-emoji emoji-id="{self.custom_emoji_id}">{self.placeholder}</tg-emoji>'


def blank_cartridge() -> EmojiRef:
    return EmojiRef(BLANK_PLACEHOLDER, BLANK_CARTRIDGE_ID)


def live_cartridge() -> EmojiRef:
    return EmojiRef(LIVE_PLACEHOLDER, LIVE_CARTRIDGE_ID)


def beer() -> EmojiRef:
    return EmojiRef(BEER_PLACEHOLDER, BEER_ID)


def inverter() -> EmojiRef:
    return EmojiRef(INVERTER_PLACEHOLDER, INVERTER_ID)


def magnifying_glass() -> EmojiRef:
    return EmojiRef(MAGNIFYING_PLACEHOLDER, MAGNIFYING_GLASS_ID)


def cigarettes() -> EmojiRef:
    return EmojiRef(CIGARETTES_PLACEHOLDER, CIGARETTES_ID)


def handcuffs() -> EmojiRef:
    return EmojiRef(HANDCUFFS_PLACEHOLDER, HANDCUFFS_ID)


def knife() -> EmojiRef:
    return EmojiRef(KNIFE_PLACEHOLDER, KNIFE_ID)


def expired_pills() -> EmojiRef:
    return EmojiRef(PILLS_PLACEHOLDER, EXPIRED_PILLS_ID)


def jammer() -> EmojiRef:
    return EmojiRef(JAMMER_PLACEHOLDER, JAMMER_ID)


def adrenaline() -> EmojiRef:
    return EmojiRef(ADRENALINE_PLACEHOLDER, ADRENALINE_ID)


def energy_hp() -> EmojiRef:
    return EmojiRef(HP_PLACEHOLDER, ENERGY_HP_ID)


def remote() -> EmojiRef:
    return EmojiRef(REMOTE_PLACEHOLDER, REMOTE_ID)


def shotgun() -> EmojiRef:
    return EmojiRef(SHOTGUN_PLACEHOLDER, SHOTGUN_ID)
