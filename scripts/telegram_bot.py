"""Telegram bot that replies 'ok' to any incoming message."""

import sys
from pathlib import Path

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings


async def reply_ok(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    await message.reply_text("ok")


def run_bot() -> None:
    settings = get_settings()
    token = settings.telegram_bot_token.strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required in backend2/.env")

    app = Application.builder().token(token).build()
    app.add_handler(MessageHandler(filters.ALL, reply_ok))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    run_bot()
