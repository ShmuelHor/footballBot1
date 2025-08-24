from __future__ import annotations
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import logging
from .core import config
from .services.football_api import FootballAPI
from .services.telegram_service import send_message

logger = logging.getLogger("football_bot")

class FootballScheduler:
    def __init__(self, api: FootballAPI):
        self.api = api
        self.scheduler = AsyncIOScheduler()
        self.tz = ZoneInfo(config.TIMEZONE)

    def start(self):
        # Daily matches 09:00 בבוקר כל יום
        self.scheduler.add_job(self.job_today, CronTrigger(day_of_week='mon-sun', hour=12, minute=42, timezone=self.tz))
        # Weekly summary Sunday 09:00
        self.scheduler.add_job(self.job_week, CronTrigger(day_of_week='sun', hour=9, minute=5, timezone=self.tz))
        self.scheduler.start()
        logger.info("Scheduler started")

    async def job_today(self):
        # שליחת כל המשחקים של היום מקובצים לפי ליגות
        logger.info("Starting daily matches job at 9:00 AM")
        msg = await self.api.build_daily_matches_message()
        if msg:
            await send_message(msg)
            logger.info("Daily matches message sent successfully")
        else:
            logger.info("No matches today - no message sent")

    async def job_week(self):
        now = datetime.now(self.tz)
        start = now.strftime('%Y-%m-%d')
        end = (now + timedelta(days=7)).strftime('%Y-%m-%d')
        msg = await self.api.build_message(start, end, config.TEAM_IDS, daily=False)
        if msg:
            await send_message(msg)
        else:
            logger.info("No matches this week")
