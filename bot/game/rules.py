"""Draw and victory detection."""
from __future__ import annotations

from .models import PieceType, Player


def check_draw(active_players: list[Player]) -> bool:
    """Automatic draw only when every remaining alive player is a Queen."""

    if len(active_players) < 2:
        return False
    return all(p.piece_type == PieceType.QUEEN for p in active_players)


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


def rules_view_announcement(player: Player) -> str:
    return f"\U0001f508 {player.mention} смотрит правила."


def draw_vote_announcement(proposer: Player, votes: int, total: int) -> str:
    return f"\U0001f508 {proposer.mention} предлагает ничью({votes}/{total})"


def impossible_move_announcement() -> str:
    return "ход невозможен."
