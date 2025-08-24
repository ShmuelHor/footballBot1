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

@router.get("/daily_matches_message")
async def daily_matches_message():
    """קבלת הודעה יומית עם כל המשחקים מקובצים לפי ליגות"""
    assert api_instance is not None
    message = await api_instance.build_daily_matches_message()
    if not message:
        raise HTTPException(status_code=404, detail="No matches found for today")
    return {"message": message}

@router.get("/send_daily_matches")
async def send_daily_matches():
    """שליחת הודעה יומית לטלגרם עם כל המשחקים"""
    assert api_instance is not None
    message = await api_instance.build_daily_matches_message()
    if not message:
        return {"status": "no_matches", "message": "No matches found for today"}

    ok = await send_message(message)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to send Telegram message")
    return {"status": "sent", "message": "Daily matches sent successfully"}

@router.get("/test_today_matches")
async def test_today_matches():
    """בדיקת המשחקים של היום - רק לבדיקה"""
    assert api_instance is not None
    matches = await api_instance.get_today_matches()
    return {"count": len(matches), "matches": matches[:5] if matches else []}

@router.get("/raw_api_response")
async def raw_api_response():
    """בדיקת התגובה הגולמית מה-API"""
    assert api_instance is not None

    # קריאה ישירה ל-API
    import httpx
    from ..core import config
    from datetime import datetime
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(config.TIMEZONE)
    today = datetime.now(tz).strftime('%Y-%m-%d')

    headers = {"X-Auth-Token": config.FOOTBALL_API_KEY}
    url = f"{config.FOOTBALL_API_URL}/matches"

    async with httpx.AsyncClient() as client:
        try:
            # בלי פילטרים
            resp1 = await client.get(url, headers=headers)
            data1 = resp1.json()

            # עם פילטר תאריך
            resp2 = await client.get(url, headers=headers, params={"dateFrom": today, "dateTo": today})
            data2 = resp2.json()

            return {
                "today": today,
                "without_filter": {
                    "status": resp1.status_code,
                    "total_matches": len(data1.get("matches", [])),
                    "first_5_matches": data1.get("matches", [])[:5]
                },
                "with_date_filter": {
                    "status": resp2.status_code,
                    "total_matches": len(data2.get("matches", [])),
                    "matches": data2.get("matches", []),
                    "full_response": data2
                }
            }
        except Exception as e:
            return {"error": str(e)}

@router.get("/test_mock_matches")
async def test_mock_matches():
    """בדיקת הפונקציה עם נתוני דמה"""
    assert api_instance is not None
    mock_matches = await api_instance.get_mock_today_matches()
    message = await api_instance.build_daily_matches_message_from_matches(mock_matches)
    return {"mock_matches_count": len(mock_matches), "message": message}

@router.get("/test_all_matches")
async def test_all_matches():
    """בדיקת כל המשחקים של היום עם ההודעה המלאה"""
    assert api_instance is not None
    message = await api_instance.build_daily_matches_message()
    if not message:
        return {"status": "no_matches", "message": "No matches found for today"}
    return {"status": "success", "message": message}

@router.get("/scheduler_status")
async def scheduler_status():
    """בדיקת סטטוס המתזמן והעבודות הבאות"""
    from datetime import timedelta
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(config.TIMEZONE)
    now = datetime.now(tz)

    # חישוב מתי התזמון הבא לשעה 9:00
    next_9am = now.replace(hour=9, minute=0, second=0, microsecond=0)
    if now.hour >= 9:
        # אם עברנו את 9:00, התזמון הבא יהיה מחר
        next_9am = next_9am + timedelta(days=1)

    time_until_next = next_9am - now
    hours_until = int(time_until_next.total_seconds() // 3600)
    minutes_until = int((time_until_next.total_seconds() % 3600) // 60)

    return {
        "current_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "timezone": str(tz),
        "next_daily_job": next_9am.strftime("%Y-%m-%d %H:%M:%S"),
        "time_until_next": f"{hours_until} hours and {minutes_until} minutes",
        "schedule": {
            "daily_matches": "Every day at 09:00",
            "weekly_summary": "Every Sunday at 09:05"
        }
    }
