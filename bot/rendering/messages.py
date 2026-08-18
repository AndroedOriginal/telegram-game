"""Static and dynamic text for lobby / game messages (all HTML parse-mode)."""
from __future__ import annotations

from html import escape

from ..emoji_assets import piece
from ..game.board import cell_color
from ..game.models import GameState, Player
from ..game.rules import turn_announcement

RULES_TEXT = (
    "Chess Royale — шахматная королевская битва без команд на доске 8×8. "
    "У каждого игрока одна фигура. Максимум 8 игроков, минимум 2. "
    "Все начинают пешками на случайных клетках: нельзя стоять рядом и под шахом. "
    "Эволюция: пешка → слон → конь → ладья → королева. "
    "Победа — когда остаётся один. Ничья — если все живые королевы или все согласились на ничью."
)

RULES_FULL = """Chess Royale — свободная королевская битва на шахматной доске.

Доска и игроки
• Доска всегда 8×8. Команд нет, каждый играет за себя.
• У каждого игрока ровно одна фигура. Максимум 8 участников, минимум 2 для старта.
• Все начинают пешками. Стартовые позиции случайны: нельзя занимать одну клетку, стоять рядом и начинать под боем.

Ходы
• Ходит только текущий игрок. Чужие нажатия кнопок «Ходы» ничего не делают.
• Слон, ладья и королева: сначала направление, затем число клеток. Нельзя прыгать через фигуры и вставать на занятую клетку.
• Конь ходит буквой «Г», как в шахматах. Все 8 кнопок — сразу 8 возможных прыжков, без выбора дистанции.
• Пешка ходит на 1 клетку вверх/вниз/влево/вправо. По диагонали (клетки 1, 3, 7, 9 вокруг пешки) можно только атаковать врага.

Бой и шах
• Атака не требует встать на клетку врага: достаточно, чтобы фигура оказалась в зоне удара.
• Шах смертелен. Ходить под шах можно, но после такого хода игрок погибает.
• Если двое бьют друг друга, погибает тот, кто последним вошёл в зону удара.

Эволюция
• Точки эволюции — это спавны игроков. Нужно встать на точку, чтобы эволюционировать.
• Свою точку нельзя использовать, пока её не активирует другой игрок. После этого доступ владельца сохраняется навсегда, даже если точка переехала.
• После эволюции пешка→слон, слон→конь, конь→ладья точка переезжает на новую клетку.
• Эволюция в королеву уничтожает точку: она исчезает с доски и больше не телепортируется.
• Всегда есть хотя бы одна точка того же цвета клетки, что и фигура игрока. Точки распределяются по доске без скученности и без крайних дистанций.

Смерть, выход, победа, ничья
• Погибший или вышедший сразу исчезает с доски и из информации, не ходит и не голосует.
• 🔈 @игрок покидает игру. — при выходе.
• Победа: остался один живой игрок — 🔈 @игрок побеждает, затем полное обновление лобби.
• Ничья только если все живые проголосовали «Ничья», либо все оставшиеся — королевы. Пешки или слоны сами по себе ничью не дают.
• После победы или ничьи сообщения игры удаляются и открывается новое лобби.

Интерфейс
• Информация, доска и кнопки «Ходы» — отдельные сообщения. В чат пишите текст: бот удалит его и покажет в строке 💬."""

RULES_ALERT = (
    "8x8, каждый за себя, 2-8 игроков. "
    "Пешка: 1 клетка +, диагональ только удар. "
    "Конь: 8 прыжков без дистанции. "
    "Шах убивает ходившего. "
    "В ферзи точка исчезает. "
    "Ничья: все королевы или все за ничью."
)


def html_quote_block(inner_html: str, expandable: bool = True) -> str:
    attr = " expandable" if expandable else ""
    return f"<blockquote{attr}>{inner_html}</blockquote>"


def rules_message_text() -> str:
    return f"\U0001f50e Правила игры:\n\n{html_quote_block(escape(RULES_FULL))}"


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


def player_info_line(player: Player) -> str:
    color = cell_color(player.position)
    piece_html = piece(player.piece_type.value, player.color.value, color).to_html()
    return f"{piece_html} {escape(player.mention)}: {player.position.to_algebraic()}"


def info_message_text(state: GameState, current: Player | None = None) -> str:
    alive = [p for p in state.active_players() if p.position is not None]
    if alive:
        quote_body = "\n".join(player_info_line(p) for p in alive)
    else:
        quote_body = "—"
    quote = html_quote_block(quote_body)

    status = state.status_line
    if not status:
        actor = current or state.current_player()
        status = turn_announcement(actor) if actor is not None else "\U0001f508"
    status = escape(status) if not status.startswith("\U0001f508") else status
    if status.startswith("\U0001f508"):
        # Keep the speaker emoji, escape the rest after it if needed.
        prefix = "\U0001f508"
        rest = status[len(prefix):]
        status = prefix + escape(rest) if "<" in rest else status

    chat = ""
    if state.chat_line:
        chat = f"\n\n\U0001f4ac {escape(state.chat_line)}"

    rules = ""
    if state.showing_rules:
        rules = f"\n\n{html_quote_block(escape(RULES_FULL))}"

    return f"\U0001f4ce Информация по игре:\n\n{quote}\n\n{status}{chat}{rules}"


def distance_prompt_text() -> str:
    return "Выберите количество клеток:"


def moves_prompt_text() -> str:
    return "Ходы:"


def announce_placeholder_text() -> str:
    return "\U0001f508"


def status_line_count(text: str) -> int:
    """Number of 🔈 lines in a status string (must stay 1)."""

    return sum(1 for line in text.splitlines() if "\U0001f508" in line)
