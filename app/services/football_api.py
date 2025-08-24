from __future__ import annotations
import asyncio
from typing import List, Dict, Optional
import httpx
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from ..core import config
import json

logger = logging.getLogger("football_bot")

league_translations: Dict = {}
team_translations: Dict = {}

async def load_translations():
    global league_translations, team_translations
    league_translations = _load_json_file('leagues.json')
    team_translations = _load_json_file('teams.json')

def _load_json_file(filename: str) -> Dict:
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading {filename}: {e}")
        return {}

class FootballAPI:
    def __init__(self):
        self.client: Optional[httpx.AsyncClient] = None
        self.tz = ZoneInfo(config.TIMEZONE)

    async def startup(self):
        self.client = httpx.AsyncClient(follow_redirects=True, timeout=15)
        await load_translations()

    async def shutdown(self):
        if self.client:
            await self.client.aclose()

    async def fetch_matches_for_team(self, team_id: int, start_date: str, end_date: str) -> List[Dict]:
        assert self.client is not None
        headers = {"X-Auth-Token": config.FOOTBALL_API_KEY}
        params = {"dateFrom": start_date, "dateTo": end_date}
        url = f"{config.FOOTBALL_API_URL}/teams/{team_id}/matches"
        try:
            resp = await self.client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
            return data.get("matches", [])
        except httpx.HTTPStatusError as e:
            logger.error(f"Status error team {team_id}: {e.response.status_code} {e.response.text[:150]}")
        except httpx.RequestError as e:
            logger.error(f"Request error team {team_id}: {e}")
        return []

    async def get_matches(self, start_date: str, end_date: str, team_ids: List[int]) -> List[Dict]:
        tasks = [self.fetch_matches_for_team(tid, start_date, end_date) for tid in team_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        matches: List[Dict] = []
        for r in results:
            if isinstance(r, list):
                matches.extend(r)
        # deduplicate
        seen = set()
        unique = []
        for m in matches:
            mid = m.get('id')
            if mid and mid not in seen:
                seen.add(mid)
                unique.append(m)
        return unique

    def utc_to_local(self, utc_iso: str) -> str:
        try:
            dt_utc = datetime.strptime(utc_iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=ZoneInfo('UTC'))
            local = dt_utc.astimezone(self.tz)
            return local.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return utc_iso

    def format_match(self, match: Dict, include_date: bool) -> str:
        comp = league_translations.get(match.get('competition', {}).get('name', ''), match.get('competition', {}).get('name', ''))
        home = team_translations.get(match.get('homeTeam', {}).get('name', ''), match.get('homeTeam', {}).get('name', ''))
        away = team_translations.get(match.get('awayTeam', {}).get('name', ''), match.get('awayTeam', {}).get('name', ''))
        start_local = self.utc_to_local(match.get('utcDate', ''))
        date_part, time_part = (start_local.split() + [''])[:2]
        lines = ["-" * 34, f"תחרות: {comp}", f"{home} vs {away}"]
        if include_date:
            lines.append(f"תאריך: {date_part}")
        lines.append(f"שעה: {time_part}")
        return "\n".join(lines) + "\n"

    async def build_message(self, start_date: str, end_date: str, team_ids: List[int], daily: bool) -> str | None:
        matches = await self.get_matches(start_date, end_date, team_ids)
        if not matches:
            return None
        matches.sort(key=lambda m: m.get('utcDate', ''))
        header = f"משחקים להיום ({start_date}):\n" if daily else f"משחקים לשבוע הקרוב ({start_date} - {end_date}):\n"
        body = ''.join(self.format_match(m, include_date=not daily) for m in matches)
        return header + body
