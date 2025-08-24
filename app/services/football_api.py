from __future__ import annotations
import asyncio
from typing import List, Dict, Optional
import httpx
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from ..core import config
import json
from collections import defaultdict

logger = logging.getLogger("football_bot")

class FootballAPI:
    def __init__(self):
        self.client: Optional[httpx.AsyncClient] = None
        self.tz = ZoneInfo(config.TIMEZONE)

    async def startup(self):
        self.client = httpx.AsyncClient(follow_redirects=True, timeout=15)

    async def shutdown(self):
        if self.client:
            await self.client.aclose()


    async def get_today_matches(self) -> List[Dict]:
        """קבלת כל המשחקים של היום מה-API החדש"""
        assert self.client is not None
        headers = {"X-Auth-Token": config.FOOTBALL_API_KEY}

        # קבלת התאריך של היום
        today = datetime.now(self.tz).strftime('%Y-%m-%d')
        logger.info(f"Looking for matches on date: {today}")

        url = f"{config.FOOTBALL_API_URL}/matches"

        try:
            # בקשה ל-API עם פילטר תאריך
            params = {
                "dateFrom": today,
                "dateTo": today
            }

            logger.info(f"Making API request to: {url} with params: {params}")
            resp = await self.client.get(url, headers=headers, params=params)
            resp.raise_for_status()

            # פענוח התגובה
            data = resp.json()
            logger.info(f"API response status: {resp.status_code}")
            logger.info(f"API response keys: {list(data.keys())}")

            # שליפת המשחקים מהמערך "matches"
            matches = data.get("matches", [])
            logger.info(f"Found {len(matches)} matches in response")

            if matches:
                # לוג מידע על המשחקים
                leagues = set()
                for i, match in enumerate(matches):
                    league_name = match.get('competition', {}).get('name', 'Unknown')
                    leagues.add(league_name)

                    home = match.get('homeTeam', {}).get('shortName', 'Unknown')
                    away = match.get('awayTeam', {}).get('shortName', 'Unknown')
                    status = match.get('status', 'Unknown')
                    utc_time = match.get('utcDate', 'Unknown')

                    logger.info(f"Match {i+1}: {home} vs {away} ({league_name}) - {status} at {utc_time}")

                logger.info(f"Leagues found: {', '.join(leagues)}")
            else:
                logger.warning("No matches found in API response")

            return matches

        except httpx.HTTPStatusError as e:
            error_text = ""
            try:
                error_text = e.response.text
                logger.error(f"HTTP Status error: {e.response.status_code}")
                logger.error(f"Error response: {error_text[:500]}")
            except:
                logger.error(f"HTTP Status error: {e.response.status_code} (couldn't read response)")
        except httpx.RequestError as e:
            logger.error(f"Request error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

        return []

    async def fetch_matches_for_team(self, team_id: int, start_date: str, end_date: str) -> List[Dict]:
        """שמירה לתאימות עם הקוד הקיים"""
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

    def format_match_english(self, match: Dict) -> str:
        """פורמט חדש למשחק באנגלית עם סמלים וסמלי קבוצות"""
        home_team = match.get('homeTeam', {}).get('shortName', 'Unknown')
        away_team = match.get('awayTeam', {}).get('shortName', 'Unknown')

        # קישורים לסמלי הקבוצות
        home_crest = match.get('homeTeam', {}).get('crest', '')
        away_crest = match.get('awayTeam', {}).get('crest', '')

        utc_date = match.get('utcDate', '')
        status = match.get('status', 'UNKNOWN')

        # המרת זמן לשעון מקומי
        local_time = self.utc_to_local(utc_date)
        time_part = local_time.split(' ')[1] if ' ' in local_time else utc_date

        # בניית שמות הקבוצות עם סמלים כקישורים
        home_display = f"[{home_team}]({home_crest})" if home_crest else home_team
        away_display = f"[{away_team}]({away_crest})" if away_crest else away_team

        # פורמט שונה לפי סטטוס המשחק
        if status == "FINISHED":
            score = match.get('score', {}).get('fullTime', {})
            home_score = score.get('home', 0)
            away_score = score.get('away', 0)
            return f"    ⚽ {home_display} `{home_score}-{away_score}` {away_display} ✅"
        elif status == "TIMED":
            return f"    🕐 `{time_part}` │ {home_display} **VS** {away_display}"
        elif status == "IN_PLAY":
            return f"    🔴 **LIVE** │ {home_display} **VS** {away_display}"
        elif status == "HALFTIME":
            return f"    ⏸️ **HALF TIME** │ {home_display} **VS** {away_display}"
        elif status == "PAUSED":
            return f"    ⏸️ **PAUSED** │ {home_display} **VS** {away_display}"
        else:
            return f"    📅 {home_display} **VS** {away_display} `({status})`"

    def group_matches_by_league(self, matches: List[Dict]) -> Dict[str, List[Dict]]:
        """קיבוץ משחקים לפי ליגות"""
        grouped = defaultdict(list)
        for match in matches:
            league_name = match.get('competition', {}).get('name', 'Unknown League')
            grouped[league_name].append(match)
        return dict(grouped)

    async def build_daily_matches_message_from_raw_data(self, raw_data: Dict) -> str | None:
        """בניית הודעה יומית מתוך נתוני API גולמיים"""
        matches = raw_data.get("matches", [])

        if not matches:
            return "⚽ No matches scheduled for today"

        # מיון לפי שעה
        matches.sort(key=lambda m: m.get('utcDate', ''))

        # קיבוץ לפי ליגות
        leagues = self.group_matches_by_league(matches)

        # בניית ההודעה
        today = datetime.now(self.tz).strftime('%d/%m/%Y')
        message_parts = [f"⚽ **Today's Football Matches - {today}**\n"]

        # מיון הליגות לפי עדיפות
        league_priority = {
            'Premier League': 1,
            'Primera Division': 2,
            'Serie A': 3,
            'Bundesliga': 4,
            'Ligue 1': 5,
            'Eredivisie': 6,
            'Primeira Liga': 7,
            'Campeonato Brasileiro Série A': 8
        }

        sorted_leagues = sorted(leagues.items(),
                              key=lambda x: league_priority.get(x[0], 99))

        for league_name, league_matches in sorted_leagues:
            # הוספת אייקון מותאם לליגה
            league_icon = self.get_league_icon(league_name)
            message_parts.append(f"\n{league_icon} **{league_name}**")

            for match in league_matches:
                message_parts.append(f"   {self.format_match_english(match)}")

        message_parts.append(f"\n📊 **Summary:**")
        message_parts.append(f"🏟️ Total matches: {len(matches)}")
        message_parts.append(f"🏆 Leagues: {len(leagues)}")

        return "\n".join(message_parts)

    async def build_daily_matches_message_from_matches(self, matches: List[Dict]) -> str | None:
        """בניית הודעה יומית מרשימת משחקים"""
        if not matches:
            return "⚽ No matches scheduled for today"

        # מיון לפי שעה
        matches.sort(key=lambda m: m.get('utcDate', ''))

        # קיבוץ לפי ליגות
        leagues = self.group_matches_by_league(matches)

        # בניית ההודעה
        today = datetime.now(self.tz).strftime('%A, %d/%m/%Y')
        message_parts = [
            "⚽🏆 **TODAY'S FOOTBALL MATCHES** 🏆⚽",
            f"📅 *{today}* │ 🇮🇱 Israel Time",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            ""
        ]

        # מיון הליגות לפי עדיפות
        league_priority = {
            'Premier League': 1,
            'Primera Division': 2,
            'Serie A': 3,
            'Bundesliga': 4,
            'Ligue 1': 5,
            'Eredivisie': 6,
            'Primeira Liga': 7,
            'Campeonato Brasileiro Série A': 8
        }

        sorted_leagues = sorted(leagues.items(),
                              key=lambda x: league_priority.get(x[0], 99))

        for i, (league_name, league_matches) in enumerate(sorted_leagues):
            # הוספת אייקון מותאם לליגה
            league_icon = self.get_league_icon(league_name)

            # קו מפריד בין ליגות (לא לליגה הראשונה)
            if i > 0:
                message_parts.append("┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈")

            message_parts.append(f"{league_icon} **{league_name}** `({len(league_matches)} matches)`")

            for match in league_matches:
                message_parts.append(self.format_match_english(match))

            # רווח אחרי כל ליגה
            message_parts.append("")

        # סיכום
        message_parts.extend([
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "📊 **SUMMARY:**",
            f"🏟️ Total matches: `{len(matches)}`",
            f"🏆 Leagues: `{len(leagues)}`",
            f"⏰ Updated: `{datetime.now(self.tz).strftime('%H:%M')}`",
            "",
            "🔔 *Next update tomorrow at 09:00*"
        ])

        return "\n".join(message_parts)

    async def build_daily_matches_message(self) -> str | None:
        """בניית הודעה יומית עם כל המשחקים מקובצים לפי ליגות"""
        # קבלת תשובה גולמית מה-API בלי פילטר תאריך
        assert self.client is not None
        headers = {"X-Auth-Token": config.FOOTBALL_API_KEY}

        # קבלת התאריך של היום
        today = datetime.now(self.tz).strftime('%Y-%m-%d')
        logger.info(f"Building daily message for date: {today}")

        url = f"{config.FOOTBALL_API_URL}/matches"

        try:
            # בקשה ל-API בלי פילטר תאריך כדי לקבל את כל המשחקים
            logger.info(f"Making API request to: {url} (no date filter)")
            resp = await self.client.get(url, headers=headers)
            resp.raise_for_status()

            # פענוח התגובה
            raw_data = resp.json()
            logger.info(f"API response status: {resp.status_code}")
            logger.info(f"Raw API data keys: {list(raw_data.keys())}")

            # שליפת כל המשחקים
            all_matches = raw_data.get("matches", [])
            logger.info(f"Found {len(all_matches)} total matches in response")

            # סינון משחקים של היום בלבד
            today_matches = []
            for match in all_matches:
                utc_date = match.get('utcDate', '')
                if utc_date:
                    try:
                        # המרת התאריך ל-UTC
                        match_date_utc = datetime.strptime(utc_date[:10], "%Y-%m-%d")

                        # המרה לשעון מקומי
                        match_date_utc_full = datetime.strptime(utc_date, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=ZoneInfo('UTC'))
                        match_date_local = match_date_utc_full.astimezone(self.tz)
                        local_date_str = match_date_local.strftime('%Y-%m-%d')

                        # אם המשחק בתאריך של היום (בשעון מקומי)
                        if local_date_str == today:
                            today_matches.append(match)

                    except Exception as e:
                        logger.warning(f"Error parsing date {utc_date}: {e}")

            logger.info(f"Found {len(today_matches)} matches for today after filtering")

            if today_matches:
                # בניית ההודעה מהמשחקים המסוננים
                return await self.build_daily_matches_message_from_matches(today_matches)
            else:
                logger.warning("No matches found for today after filtering")
                return "⚽ No matches scheduled for today"

        except httpx.HTTPStatusError as e:
            error_text = ""
            try:
                error_text = e.response.text
                logger.error(f"HTTP Status error: {e.response.status_code}")
                logger.error(f"Error response: {error_text[:500]}")
            except:
                logger.error(f"HTTP Status error: {e.response.status_code} (couldn't read response)")
            return "⚽ Error fetching today's matches"
        except httpx.RequestError as e:
            logger.error(f"Request error: {e}")
            return "⚽ Error connecting to football API"
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return "⚽ Unexpected error occurred"

    def get_league_icon(self, league_name: str) -> str:
        """מחזיר אייקון מתאים לכל ליגה"""
        league_icons = {
            'Premier League': '🏴',
            'Primera Division': '🇪🇸',
            'Serie A': '🇮🇹',
            'Bundesliga': '🇩🇪',
            'Ligue 1': '🇫🇷',
            'Eredivisie': '🇳🇱',
            'Primeira Liga': '🇵🇹',
            'Campeonato Brasileiro Série A': '🇧🇷'
        }
        return league_icons.get(league_name, '⚽')

    def format_match(self, match: Dict, include_date: bool) -> str:
        """שמירה לתאימות עם הקוד הקיים"""
        home = match.get('homeTeam', {}).get('name', '')
        away = match.get('awayTeam', {}).get('name', '')
        comp = match.get('competition', {}).get('name', '')
        start_local = self.utc_to_local(match.get('utcDate', ''))
        date_part, time_part = (start_local.split() + [''])[:2]
        lines = ["-" * 34, f"תחרות: {comp}", f"{home} vs {away}"]
        if include_date:
            lines.append(f"תאריך: {date_part}")
        lines.append(f"שעה: {time_part}")
        return "\n".join(lines) + "\n"

    async def build_message(self, start_date: str, end_date: str, team_ids: List[int], daily: bool) -> str | None:
        """שמירה לתאימות עם הקוד הקיים"""
        matches = await self.get_matches(start_date, end_date, team_ids)
        if not matches:
            return None
        matches.sort(key=lambda m: m.get('utcDate', ''))
        header = f"משחקים להיום ({start_date}):\n" if daily else f"משחקים לשבוע הקרוב ({start_date} - {end_date}):\n"
        body = ''.join(self.format_match(m, include_date=not daily) for m in matches)
        return header + body
