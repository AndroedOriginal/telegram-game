"""Static and dynamic text for lobby / game messages (all HTML parse-mode)."""
from __future__ import annotations

from html import escape

from ..emoji_assets import piece
from ..game.board import cell_color
from ..game.models import GameState, Player

RULES_TEXT = (
    "Chess Royale — шахматная королевская битва.\n\n"
    "• Доска 8x8, без команд, у каждого игрока одна фигура.\n"
    "• Все начинают пешками и эволюционируют: пешка → слон → конь → ладья → королева.\n"
    "• Пешка ходит на 1 клетку по горизонтали/вертикали, а бьёт по диагонали.\n"
    "• Слон, ладья и королева ходят как в обычных шахматах на любое число клеток.\n"
    "• Конь прыгает буквой «Г»: 4 диагональные кнопки — 4 фиксированных прыжка.\n"
    "• Нельзя ходить на занятую клетку (кроме особой атаки пешки по диагонали).\n"
    "• Точки эволюции — это стартовые клетки игроков. Свою точку нельзя использовать, "
    "пока её не активирует другой игрок; после этого она навсегда доступна владельцу.\n"
    "• После использования точка эволюции переезжает в новое случайное место.\n"
    "• Если после хода фигура игрока оказывается под боем — игрок погибает.\n"
    "• Если у всех оставшихся игроков одинаковая фигура — ничья.\n"
    "• Победа, когда остаётся ровно один игрок."
)


def html_quote_block(inner_html: str, expandable: bool = True) -> str:
    attr = " expandable" if expandable else ""
    return f"<blockquote{attr}>{inner_html}</blockquote>"


def rules_message_text() -> str:
    return f"\U0001f50e Правила игры:\n\n{html_quote_block(escape(RULES_TEXT))}"


def lobby_message_text(player_count: int) -> str:
    return f"\U0001f9e9 Лобби({player_count} игроков):"


def start_button_message_text() -> str:
    return "\u2705 Начать игру:"


def lobby_join_system_message(player: Player) -> str:
    return f"\U0001f508{escape(player.mention)} зашел в лобби."


def lobby_leave_system_message(player: Player) -> str:
    return f"\U0001f508{escape(player.mention)} вышел из лобби."


def lobby_not_enough_players_message() -> str:
    return "\U0001f508Недостаточно игроков."


def lobby_join_progress_message(player: Player, current: int, required: int) -> str:
    return (
        f"\U0001f508 {escape(player.mention)} присоиденяется к игре. "
        f"Игроков в лобби: {current}/{required}."
    )


def info_message_text(state: GameState, current: Player) -> str:
    color = cell_color(current.position)
    piece_html = piece(current.piece_type.value, current.color.value, color).to_html()
    position_text = current.position.to_algebraic()
    mention = escape(current.mention)
    quote = html_quote_block(f"{piece_html} {mention}: {position_text}")
    turn_line = f"\U0001f508 {mention} делает ход."
    return f"\U0001f4ce Информация по игре:\n\n{quote}\n\n{turn_line}"


def distance_prompt_text() -> str:
    return "Выберите количество клеток:"


def game_over_footer(text: str) -> str:
    return text
