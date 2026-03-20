"""
scheduler.py
Runs a task at 00:01 IST every day:
  1. Fetches Today + Tomorrow OTT releases (DB first, APIs as fallback)
  2. Edits the stored message in every registered channel
"""

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Optional
import pytz

logger = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata")


def _seconds_until_next_midnight() -> float:
    now = datetime.now(IST)
    target = now.replace(hour=0, minute=1, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    return (target - now).total_seconds()


async def _get_or_fetch(date_obj: date) -> dict:
    """Import here to avoid circular imports at module load time."""
    from database.ott_db import get_releases_by_date, add_release
    from helpers.ott_fetcher import fetch_ott_releases

    date_str = date_obj.strftime("%Y-%m-%d")
    stored = await get_releases_by_date(date_str)
    if stored["movies"] or stored["series"]:
        return stored

    fetched = await fetch_ott_releases(date_obj)
    for m in fetched.get("movies", []):
        await add_release(date_str, "movie", m["title"], m.get("language", ""), "")
    for s in fetched.get("series", []):
        await add_release(date_str, "series", s["title"], s.get("language", ""), s.get("extra", ""))

    return await get_releases_by_date(date_str)


async def _run_daily_update(client):
    from database.ott_db import get_all_update_tasks, update_task_message_id
    from helpers.formatter import format_today_tomorrow
    from pyrogram.enums import ParseMode

    logger.info("⏰ Running daily OTT channel update…")
    today = date.today()
    tomorrow = today + timedelta(days=1)

    today_rel = await _get_or_fetch(today)
    tomorrow_rel = await _get_or_fetch(tomorrow)
    text_out = format_today_tomorrow(today, today_rel, tomorrow, tomorrow_rel)

    tasks = await get_all_update_tasks()
    for task in tasks:
        cid = task["channel_id"]
        mid = task.get("message_id")
        try:
            if mid:
                await client.edit_message_text(
                    chat_id=cid,
                    message_id=mid,
                    text=text_out,
                    parse_mode=ParseMode.HTML,
                )
                logger.info(f"✅ Edited message in channel {cid}")
            else:
                sent = await client.send_message(cid, text_out, parse_mode=ParseMode.HTML)
                await update_task_message_id(cid, sent.id)
                logger.info(f"✅ Sent fresh message to channel {cid}")
        except Exception as e:
            logger.error(f"❌ Failed to update channel {cid}: {e}")


async def _scheduler_loop(client):
    logger.info("🗓️ OTT Scheduler started.")
    while True:
        wait = _seconds_until_next_midnight()
        logger.info(f"⏳ Next OTT update in {wait / 3600:.2f} hours")
        await asyncio.sleep(wait)
        await _run_daily_update(client)
        await asyncio.sleep(70)   # small buffer so we don't double-fire


def start_scheduler(client):
    """Call once after bot.start() to kick off the daily update loop."""
    loop = asyncio.get_event_loop()
    loop.create_task(_scheduler_loop(client))
