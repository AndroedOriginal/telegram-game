"""Entry point for the Chess Royale Telegram bot."""
from __future__ import annotations

import logging

from telegram.ext import Application, CallbackQueryHandler, CommandHandler

from bot.config import config
from bot.handlers.callbacks import on_callback_query
from bot.handlers.game import cmd_leave_game
from bot.handlers.lobby import cmd_new_game
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
    application.add_handler(CommandHandler("leave", cmd_leave_game))
    application.add_handler(CallbackQueryHandler(on_callback_query))

    return application


def main() -> None:
    application = build_application()
    logger.info("Chess Royale bot starting...")
    application.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
