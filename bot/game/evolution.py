"""Evolution-point usage rules: who can evolve where, and the evolution
order (Pawn -> Bishop -> Knight -> Rook -> Queen)."""
from __future__ import annotations

from .models import PIECE_NAME_RU, Player, Spawn, next_piece_type


def can_use_spawn(player: Player, spawn: Spawn) -> bool:
    """A player may evolve on any foreign spawn. Their own spawn is locked
    until ``activated_by_other`` is True.

    Unlock (permanent, tied to spawn identity / owner, not coordinates):
    1. the owner evolves on another player's spawn, or
    2. another player evolves on this spawn.
    """

    if spawn.owner_user_id != player.user_id:
        return True
    return spawn.activated_by_other


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


def _unlock_spawn(spawn: Spawn) -> None:
    spawn.activated_by_other = True


def mark_spawn_used(player: Player, spawn: Spawn, all_spawns: list[Spawn] | None = None) -> None:
    """Record that ``player`` evolved on ``spawn``.

    * Case B — another player used this spawn: unlock it for its owner.
    * Case A — the player used a foreign spawn: unlock *their own* spawn
      (looked up by owner id, not by coordinate).

    The flag only ever transitions False → True and survives relocation.
    Using your own already-unlocked spawn does not change anything.
    """

    if spawn.owner_user_id == player.user_id:
        return

    _unlock_spawn(spawn)
    if all_spawns is None:
        return
    for own in all_spawns:
        if own.owner_user_id == player.user_id:
            _unlock_spawn(own)
            return
