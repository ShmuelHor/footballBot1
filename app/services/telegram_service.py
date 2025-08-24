from __future__ import annotations
from telegram import Bot
import logging
from ..core import config

logger = logging.getLogger("football_bot")

bot = Bot(token=config.TELEGRAM_API_TOKEN)

async def send_message(text: str) -> bool:
    try:
        await bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=text)
        logger.info("Telegram message sent")
        return True
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False
