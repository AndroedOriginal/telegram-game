# Chess Royale

Chess Royale is a free-for-all, chess-themed multiplayer game played inside a
Telegram topic. There are no teams: every player controls exactly one piece
on a standard 8×8 board, and pieces get stronger over time by reaching
**evolution points** left behind by other players.

```
Pawn → Bishop → Knight → Rook → Queen
```

The last surviving player wins. If every remaining player has evolved to
the *same* piece type, the game ends in a draw.

This repository contains a complete, testable implementation: a pure-Python
game engine, a Telegram bot UI built with
[python-telegram-bot](https://python-telegram-bot.org/) (async, v22), custom
Telegram emoji rendering, SQLite persistence, and an automated test suite.

## How the game works

- **Board.** Always exactly 8×8, rendered with Telegram custom/premium emoji
  (never plain Unicode squares) — column letters (A–H) and row numbers
  (1–8) are shown as a header/side using the same custom emoji. The board
  message is the original custom-emoji screen with a single divider emoji
  after the last board row (no quote).
- **Spawns are evolution points.** Every player's starting square becomes a
  permanent *spawn* object owned by that player (identity is the owner, not
  the coordinate). A player cannot evolve on their **own** spawn at first.
  That spawn unlocks permanently if (A) the owner evolves on someone else's
  point, or (B) another player evolves on it. Relocation does not reset the
  unlock. Evolving into a Queen removes the used point instead of moving it.
- **Movement**
  - *Pawn* — one square up/down/left/right. Diagonals are attack-only: a
    pawn can move diagonally only to eliminate an enemy piece sitting
    there, and it does **not** relocate onto that square.
  - *Bishop / Rook / Queen* — classic chess sliding movement in their usual
    directions, any distance, blocked by other pieces.
  - *Knight* — jumps like a chess knight, but only 4 fixed jumps are
    exposed as buttons (one per diagonal quadrant) for a compact one-hand
    mobile control scheme. Knight *attacks* (for check detection) still
    use the full classic 8-square L-shape geometry.
  - A player can never land on an occupied square (the pawn diagonal
    attack is the only exception).
- **Check is lethal and immediate.** After a move, every other living
  player inside the mover's attack area is eliminated at once. There is
  no persistent check: the attacked player does not get a turn to escape.
  Status becomes `🔈 @attacker ставит шах @victim`. If the mover is still
  under attack after that resolution, the mover also dies.
- **Turns.** Turn order is shuffled once at game start and then proceeds
  cyclically, skipping eliminated/left players. Only the active player's
  button presses do anything; everyone else's taps are silently ignored.
- **Controls.** Direction first, then distance (for sliding pieces) — no
  chess notation required:

  ```
  [⬅️][➡️][⬆️][⬇️][↖️][↗️][↙️][↘️]
  ```

  Choosing a sliding-piece direction opens a second message with only the
  legal distances for that direction (e.g. `[1️⃣][2️⃣][3️⃣]`).

## Project structure

```
telegram-game/
├── bot/
│   ├── config.py            # env-based configuration (no secrets in code)
│   ├── emoji_assets.py      # the ONLY place custom emoji ids are listed
│   ├── callback_data.py     # compact callback_data encode/decode
│   ├── manager.py           # in-memory + SQLite-backed game registry
│   ├── game/                # pure Python game engine (no Telegram imports)
│   │   ├── models.py        # enums & dataclasses (Player, Spawn, GameState...)
│   │   ├── board.py         # 8x8 geometry, cell coloring
│   │   ├── movement.py      # legal destinations per piece type
│   │   ├── attacks.py       # attack-area geometry / check detection
│   │   ├── evolution.py     # evolution order + spawn-usage rules
│   │   ├── spawns.py        # random valid spawn placement/relocation
│   │   ├── rules.py         # draw/victory detection + RU announcements
│   │   └── engine.py        # orchestrates the full move/lobby lifecycle
│   ├── rendering/
│   │   ├── board_renderer.py  # board -> Telegram HTML with <tg-emoji>
│   │   └── messages.py        # all other RU UI strings
│   ├── database/
│   │   ├── db.py             # SQLite connection/schema
│   │   └── repository.py     # GameState <-> JSON (de)serialization
│   └── handlers/
│       ├── lobby.py          # /chessroyale, join/leave/start callbacks
│       ├── game.py           # move callbacks, board/info message updates
│       ├── callbacks.py      # single CallbackQueryHandler dispatcher
│       └── keyboards.py      # InlineKeyboardMarkup builders
├── tests/                    # pytest suite for the game engine & persistence
├── main.py                   # bot entry point
├── requirements.txt
├── requirements-dev.txt
├── .env.example
└── .gitignore
```

The game engine (`bot/game/`) never imports anything from `telegram`; it can
be tested and reasoned about in complete isolation. `bot/handlers/` is the
only layer that talks to the Telegram Bot API.

## Custom emoji assets

All Telegram custom/premium emoji IDs used by the board renderer live in
`bot/emoji_assets.py` and nowhere else. Each entry pairs a custom emoji id
with a plain-Unicode placeholder character, and rendering uses Telegram's
`<tg-emoji emoji-id="...">placeholder</tg-emoji>` HTML tag (sent with
`parse_mode=HTML`) so no manual UTF-16 offset math is needed.

## Installation

Requires **Python 3.11+**.

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

## Configuration

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

| Variable              | Description                                                                 |
|-----------------------|-------------------------------------------------------------------------------|
| `TELEGRAM_BOT_TOKEN`  | Bot token from [@BotFather](https://t.me/BotFather). **Required.**            |
| `TELEGRAM_CHAT_ID`    | Numeric id of the chat the bot should operate in. Leave empty to allow any chat. |
| `TELEGRAM_TOPIC_ID`   | `message_thread_id` of the "Chess Royale" forum topic. Optional.              |
| `DATABASE_PATH`       | Path to the SQLite file used for persistence (default `chess_royale.sqlite3`). |

Never commit your real `.env` file, bot token, or the SQLite database — they
are excluded via `.gitignore`.

## Running the bot

```bash
python main.py
```

Inside the configured chat/topic, use:

- `/chessroyale` (or `/newgame`) — open a new lobby with rules, a
  join/leave panel, and a start button.
- `/restart` — end the current lobby or match, delete game messages, and
  open a fresh lobby.
- `/leave` — leave an active game you are currently playing in.

During an active game the UI is three persistent messages: information
(with **Правила / Выйти / Ничья**), the board, and **Ходы** (direction
buttons). Player chat messages are deleted and mirrored into the 💬 line.

Every game is keyed by `(chat_id, topic_id)`, so multiple independent games
can run simultaneously in different topics/chats.

## Running tests

```bash
pip install -r requirements-dev.txt
pytest
```

The suite covers pawn/bishop/knight/rook/queen movement, blockers and
occupied-cell rules, attack detection, lethal immediate check (the
attacked player dies and is skipped), evolution and the full spawn-activation
lifecycle (owner restriction, activation by another player, permanent
unlock, relocation, Queen evolution removing the point), draw votes,
automatic Queen-draw, victory, leaving, chat mirroring, invalid moves,
turn restrictions, stale/replayed callback rejection, and SQLite
persistence round-trips.

## Design notes / deliberate interpretations

- **Automatic draw** happens only when every remaining alive player is a
  Queen, or when every alive player votes **Ничья**. Same-piece groups of
  bishops/knights/pawns do not draw by themselves.
- **Knight controls.** All eight direction buttons map to the eight
  classic knight L-jumps. There is no distance menu.
- **Pawn diagonal attacks don't relocate the attacker.** The attacking pawn
  eliminates the enemy in place; its own square is then re-checked for
  danger exactly like any other move.
- **Rules popup.** Telegram alerts are limited to 200 characters, so the
  Rules button shows a short alert and also expands the full rules inside
  the main information message.
- **Chat cleanup.** On start/restart the bot deletes every message ID it
  has tracked. It cannot delete arbitrary older history unless it is a
  group admin and knows those IDs.
