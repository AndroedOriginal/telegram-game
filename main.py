"""Entry point for the Telegram games bot (Chess Royale + Buckshot Roulette)."""
from __future__ import annotations

import logging

from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from bot.config import config
from bot.handlers.callbacks import on_callback_query
from bot.handlers.game import cmd_leave_game, on_player_chat
from bot.handlers.lobby import cmd_new_game, cmd_restart
from bot.buckshot.handlers import cmd_new_game as cmd_buckshot
from bot.manager import GameManager

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def build_application() -> Application:
    if not config.bot_token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is not set. Copy .env.example to .env and fill it in."
        )

    application = Application.builder().token(config.bot_token).build()
    application.bot_data["manager"] = GameManager(config.database_path)

    application.add_handler(CommandHandler(["chessroyale", "newgame"], cmd_new_game))
    application.add_handler(CommandHandler(["buckshot", "buckshotroulette"], cmd_buckshot))
    application.add_handler(CommandHandler("restart", cmd_restart))
    application.add_handler(CommandHandler("leave", cmd_leave_game))
    application.add_handler(CallbackQueryHandler(on_callback_query))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_player_chat))

    return application


def main() -> None:
    application = build_application()
    logger.info("Telegram games bot starting (Chess Royale + Buckshot Roulette)...")
    application.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
