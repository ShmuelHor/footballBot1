from __future__ import annotations
from fastapi import APIRouter, Query, HTTPException
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from ..core import config
from ..services.football_api import FootballAPI
from ..services.telegram_service import send_message

router = APIRouter()

api_instance: FootballAPI | None = None

def set_api_instance(instance: FootballAPI):
    global api_instance
    api_instance = instance

@router.get("/")
async def root():
    return {"message": "Football Bot API is running", "teams": config.TEAM_IDS}

@router.get("/send_test_message")
async def send_test_message():
    ok = await send_message("הודעת בדיקה: הבוט פועל בהצלחה!")
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to send Telegram message")
    return {"status": "sent"}

@router.get("/today_matches")
async def today_matches():
    tz = ZoneInfo(config.TIMEZONE)
    today = datetime.now(tz).strftime('%Y-%m-%d')
    assert api_instance is not None
    matches = await api_instance.get_matches(today, today, config.TEAM_IDS)
    return {"count": len(matches), "date": today, "matches": matches}

@router.get("/upcoming_matches")
async def upcoming_matches(days: int = Query(7, ge=1, le=14)):
    tz = ZoneInfo(config.TIMEZONE)
    start_dt = datetime.now(tz)
    start = start_dt.strftime('%Y-%m-%d')
    end = (start_dt + timedelta(days=days)).strftime('%Y-%m-%d')
    assert api_instance is not None
    matches = await api_instance.get_matches(start, end, config.TEAM_IDS)
    return {"count": len(matches), "from": start, "to": end, "matches": matches}
