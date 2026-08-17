"""Draw and victory detection."""
from __future__ import annotations

from .models import PieceType, Player


def check_draw(active_players: list[Player]) -> bool:
    """A draw occurs when 2+ players remain and they all share the same
    piece type (section 22).

    The shared-Pawn case is intentionally excluded: every game starts with
    all players as pawns, so treating that as a draw would end every game
    before a single move is made. All of the spec's own examples (Bishop,
    Knight) involve evolved pieces, so this is the smallest safe reading
    that preserves the intended "everyone converged to the same evolved
    tier" draw condition without breaking normal play.
    """

    if len(active_players) < 2:
        return False
    piece_types = {p.piece_type for p in active_players}
    if piece_types == {PieceType.PAWN}:
        return False
    return len(piece_types) == 1


def check_victory(active_players: list[Player]) -> Player | None:
    """Return the sole remaining active player, or ``None`` if 0 or 2+
    players remain."""

    if len(active_players) == 1:
        return active_players[0]
    return None


def draw_announcement(players: list[Player]) -> str:
    mentions = [p.mention for p in players]
    if len(mentions) == 2:
        body = f"{mentions[0]} и {mentions[1]}"
    else:
        body = ", ".join(mentions[:-1]) + f"... и {mentions[-1]}"
    return f"Ничья между {body}."


def victory_announcement(player: Player) -> str:
    return f"\U0001f508 {player.mention} побеждает."


def leave_announcement(player: Player) -> str:
    return f"\U0001f508 {player.mention} покидает игру."


def turn_announcement(player: Player) -> str:
    return f"\U0001f508 {player.mention} делает ход."


def check_announcement(attacker: Player, victim: Player) -> str:
    return f"\U0001f508 {attacker.mention} ставит шах {victim.mention}."


def game_start_announcement() -> str:
    return "\U0001f508 Игра начинается."
