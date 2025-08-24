from __future__ import annotations
import os
from dotenv import load_dotenv
from typing import List

load_dotenv()

TELEGRAM_API_TOKEN = os.getenv('TELEGRAM_API_TOKEN')
FOOTBALL_API_KEY = os.getenv('FOOTBALL_DATA_TOKEN')  # שינוי לטוקן החדש
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TEAM_IDS_RAW = os.getenv('TEAM_IDS', '86')

if not all([TELEGRAM_API_TOKEN, FOOTBALL_API_KEY, TELEGRAM_CHAT_ID]):
    raise RuntimeError("Missing required environment variables (TELEGRAM_API_TOKEN / FOOTBALL_API_KEY / TELEGRAM_CHAT_ID)")

try:
    TEAM_IDS: List[int] = [int(x.strip()) for x in TEAM_IDS_RAW.split(',') if x.strip()]
except ValueError as e:
    raise RuntimeError("TEAM_IDS must be a comma separated list of integers") from e

FOOTBALL_API_URL = "https://api.football-data.org/v4"
TIMEZONE = "Asia/Jerusalem"
LOG_FILE = "football_bot.log"
APP_TITLE = "Football Bot API"
APP_VERSION = "1.2.0"
