# telegram-game

One Telegram bot, two independent games. Each running match is keyed by
`(chat_id, topic_id)`, so Chess Royale and Buckshot Roulette can live in
different forum topics of the same chat without sharing state.

| Game | Topic (example) | Command |
|------|-----------------|--------|
| **Chess Royale** | its own forum topic | `/chessroyale` or `/newgame` |
| **Buckshot Roulette** | topic `Buckshot Roulette` | `/buckshot` or `/buckshotroulette` |

`/restart` and `/leave` apply to whichever game is in the **current** topic.

This repository contains testable pure-Python engines, a Telegram bot UI built
with [python-telegram-bot](https://python-telegram-bot.org/) (async, v22),
custom Telegram emoji rendering, SQLite persistence, and an automated test suite.

## Chess Royale

Chess Royale is a free-for-all, chess-themed multiplayer game. There are no
teams: every player controls exactly one piece on a standard 8×8 board, and
pieces get stronger over time by reaching **evolution points** left behind by
other players.

```
Pawn → Bishop → Knight → Rook → Queen
```

The last surviving player wins. If every remaining player has evolved to
the *same* piece type, the game ends in a draw.

## How the game works

- **Board.** Always exactly 8×8, rendered with Telegram custom/premium emoji
  (never plain Unicode squares) — column letters (A–H) and row numbers
  (1–8) are shown as a header/side using the same custom emoji. The board
  message is a rich Heading 6 (`<h6>`) wrapping the original custom-emoji
  screen (no divider, no quote). **Ходы:** stays a separate message below.
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
- **Check is lethal and immediate.** After a completed move, the destination
  is tested against the attack areas of **all other alive players** (from
  that resulting position). A Pawn attacks only its four adjacent diagonal
  cells; Bishop / Rook / Queen slide until blocked; a Knight attacks all
  eight L-shaped squares. If any alive opponent attacks that cell, the
  mover dies at once — piece type does not matter, there is no warning,
  and the victim is removed from the board, the info list, and the turn
  order. Status becomes `🔈 @attacker ставит шах @victim`. Dead pieces
  no longer attack.
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

## Buckshot Roulette

A 2–4 player shotgun duel in its own topic. Players take turns using
single-use items and must shoot themselves or another living player.
Cartridges are blank or live; the real order is hidden. Last player with HP
wins. Dead players leave the turn rotation and cannot be shot, but their
inventory remains stealable with Adrenaline.

Lobby: `/buckshot` → rules (collapsed quote), join/leave, start. In-game UI is
four persistent messages that are edited in place: information
(**Правила / Выйти**), dealer commentary, **Действия**, and one 🔈 status
line. Temporary target/item pickers may appear and are deleted afterwards.

## Project structure

```
telegram-game/
├── bot/
│   ├── config.py            # env-based configuration (no secrets in code)
│   ├── emoji_assets.py      # Chess Royale custom emoji ids
│   ├── callback_data.py     # Chess Royale callback_data encode/decode
│   ├── manager.py           # in-memory + SQLite registry for BOTH games
│   ├── game/                # Chess Royale engine (no Telegram imports)
│   ├── buckshot/            # Buckshot Roulette (independent of Chess Royale)
│   │   ├── emoji_assets.py  # Buckshot custom emoji ids only
│   │   ├── models.py
│   │   ├── engine.py
│   │   ├── texts.py
│   │   ├── sequencer.py     # async delays between event messages
│   │   ├── persistence.py
│   │   ├── callbacks.py
│   │   ├── ui.py
│   │   └── handlers.py
│   ├── rendering/           # Chess Royale board + messages
│   ├── database/            # shared SQLite; chess JSON load skips buckshot rows
│   └── handlers/            # Chess Royale UI + callback dispatcher
├── tests/
├── main.py
├── requirements.txt
├── requirements-dev.txt
├── .env.example
└── .gitignore
```

Chess Royale (`bot/game/`) never imports Buckshot or Telegram. Buckshot
(`bot/buckshot/engine.py`) never imports Chess Royale or Telegram. Callbacks
are routed by prefix so the two games cannot operate on each other's state.

## Custom emoji assets

All Telegram custom/premium emoji IDs for **Chess Royale** live in
`bot/emoji_assets.py`. Buckshot Roulette IDs live only in
`bot/buckshot/emoji_assets.py`. Do not mix the two packs.

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
| `TELEGRAM_TOPIC_ID`   | Optional Chess Royale forum `message_thread_id` (documentation / pinning).    |
| `BUCKSHOT_TOPIC_ID`   | Optional Buckshot Roulette forum `message_thread_id`. If set, `/buckshot` only works in that topic. |
| `DATABASE_PATH`       | Path to the SQLite file used for persistence (default `chess_royale.sqlite3`). |

Never commit your real `.env` file, bot token, or the SQLite database — they
are excluded via `.gitignore`.

## Running the bot

```bash
python main.py
```

Inside the configured chat, open the matching forum topic and use:

- `/chessroyale` (or `/newgame`) — Chess Royale lobby (rules, join/leave, start).
- `/buckshot` (or `/buckshotroulette`) — Buckshot Roulette lobby in the current topic.
- `/restart` — end the current topic's lobby or match, delete its messages, open a fresh lobby for that same game.
- `/leave` — leave an active match in this topic.

Chess Royale UI is three persistent messages: information
(with **Правила / Выйти / Ничья**), the board, and **Ходы**.
Buckshot Roulette keeps persistent information (**Правила / Выйти**), dealer
commentary, **Действия**, and one 🔈 status line. Those messages are edited
when the state changes; only temporary pickers are extra messages.

Every game is keyed by `(chat_id, topic_id)`, so Chess Royale and Buckshot
Roulette (and multiple Chess Royale topics) run independently.

## Running tests

```bash
pip install -r requirements-dev.txt
pytest
```

The suite covers Chess Royale (movement, lethal check, evolution, draws,
persistence) and Buckshot Roulette (lobby limits, shotgun, items, blocks,
adrenaline, death/leave, topic isolation). Chess Royale tests must keep
passing when Buckshot Roulette changes.

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
