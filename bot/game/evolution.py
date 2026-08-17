"""Evolution-point usage rules: who can evolve where, and the evolution
order (Pawn -> Bishop -> Knight -> Rook -> Queen)."""
from __future__ import annotations

from .models import PIECE_NAME_RU, Player, Spawn, next_piece_type


def can_use_spawn(player: Player, spawn: Spawn) -> bool:
    """A player may evolve on any spawn except their own un-activated one.

    Section 6/49: the owner cannot use their own spawn for a free evolution
    until another player has activated it (section 7). Once activated, the
    owner's access is permanent (section 7), even if the spawn relocates.
    """

    if spawn.owner_user_id != player.user_id:
        return True
    return spawn.activated


def evolve_player(player: Player) -> bool:
    """Advance ``player``'s piece to the next evolution stage in place.

    Returns ``True`` if evolution happened, ``False`` if the player was
    already a Queen (max stage, cannot evolve further).
    """

    upgraded = next_piece_type(player.piece_type)
    if upgraded is None:
        return False
    player.piece_type = upgraded
    return True


def evolution_announcement(player: Player) -> str:
    piece_name = PIECE_NAME_RU[player.piece_type]
    return f"\U0001f508 {player.mention} меняет фигуру на {piece_name}."


def mark_spawn_used(player: Player, spawn: Spawn) -> None:
    """Update the spawn's activation flag after ``player`` uses it.

    The flag only matters for the owner's own spawn, and only ever
    transitions False -> True (it is never reset, even after relocation).
    """

    if spawn.owner_user_id != player.user_id and not spawn.activated:
        spawn.activated = True
