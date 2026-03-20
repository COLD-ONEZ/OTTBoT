"""
ott.py  —  OTT Release Date Bot — Main Plugin

HOW IT WORKS
────────────
• Any message that looks like a date  → returns release list for that date
• /addrelease                         → step-by-step wizard (admin only)
• /removerelease <date> | <title>     → remove an entry (admin only)
• /sendupdate <channel_id>            → post Today+Tomorrow to a channel,
                                        auto-edited every day at 00:01 IST
                                        (admin only, must be sent in PM)
• /stopupdate <channel_id>            → stop daily edits (admin only, PM)
• /listchannels                       → list registered channels (admin only)
• /start / /help                      → usage info
"""

import re
import logging
from datetime import date, datetime, timedelta
from typing import Optional

from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

from info import ADMINS
from database.ott_db import (
    add_release,
    remove_release,
    get_releases_by_date,
    add_update_task,
    remove_update_task,
    get_all_update_tasks,
)
from helpers.ott_fetcher import fetch_ott_releases
from helpers.formatter import format_single_date, format_today_tomorrow

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# In-memory wizard state  {user_id: {step, action, ...data}}
# ─────────────────────────────────────────────────────────────────────────────
_state: dict = {}

# All command names (excluded from text handlers)
_ALL_CMDS = [
    "start", "help",
    "addrelease", "removerelease",
    "sendupdate", "stopupdate", "listchannels",
]


# ─────────────────────────────────────────────────────────────────────────────
# Date helpers
# ─────────────────────────────────────────────────────────────────────────────

_DATE_FORMATS = [
    "%B %d %Y",   # March 18 2026
    "%B %d, %Y",  # March 18, 2026
    "%d/%m/%Y",   # 18/03/2026
    "%d-%m-%Y",   # 18-03-2026
    "%Y-%m-%d",   # 2026-03-18
    "%d %B %Y",   # 18 March 2026
]


def parse_date(text: str) -> Optional[date]:
    text = re.sub(r"\s+", " ", text.strip().rstrip(".,"))
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def looks_like_date(text: str) -> bool:
    t = text.strip().lower()
    months = [
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december",
        "jan", "feb", "mar", "apr", "jun",
        "jul", "aug", "sep", "oct", "nov", "dec",
    ]
    has_month = any(m in t for m in months)
    has_digit = bool(re.search(r"\d", t))
    is_numeric = bool(re.match(r"^\d{1,4}[\/\-]\d{1,2}[\/\-]\d{2,4}$", t))
    return (has_month and has_digit) or is_numeric


# ─────────────────────────────────────────────────────────────────────────────
# DB helper — fetch from APIs if DB empty, then cache
# ─────────────────────────────────────────────────────────────────────────────

async def get_or_fetch(date_obj: date) -> dict:
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


# ─────────────────────────────────────────────────────────────────────────────
# /start  /help
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command(["start", "help"]))
async def cmd_help(_, message: Message):
    await message.reply(
        "<b>🎬 OTT Info Bot</b>\n\n"
        "Send any date to see what releases that day:\n"
        "<code>March 21 2026</code>  or  <code>21/03/2026</code>",
        parse_mode=ParseMode.HTML,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Unified text handler — single handler for date queries AND wizard replies
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.text & ~filters.command(_ALL_CMDS))
async def text_router(client: Client, message: Message):
    uid = message.from_user.id if message.from_user else None
    if uid is None:
        return

    # ── If user is mid-wizard, handle that first ─────────────────────────────
    if uid in _state:
        await _wizard_step(client, message)
        return

    # ── Otherwise check if it's a date query ────────────────────────────────
    if not looks_like_date(message.text):
        return

    d = parse_date(message.text)
    if not d:
        await message.reply(
            "❌ Couldn't parse that date.\nTry: <code>March 21 2026</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    loading = await message.reply("⏳ Fetching releases…")
    releases = await get_or_fetch(d)
    await loading.edit_text(
        format_single_date(d, releases),
        parse_mode=ParseMode.HTML,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Wizard logic
# ─────────────────────────────────────────────────────────────────────────────

async def _wizard_step(client: Client, message: Message):
    uid = message.from_user.id
    state = _state[uid]
    text = message.text.strip()
    step = state["step"]

    if step == "date":
        d = parse_date(text)
        if not d:
            await message.reply(
                "❌ Invalid date. Try: <code>March 21 2026</code>",
                parse_mode=ParseMode.HTML,
            )
            return
        state["date"] = d.strftime("%Y-%m-%d")
        state["step"] = "category"
        await message.reply(
            "🎬 Is this a <b>Movie</b> or <b>Series</b>?\n"
            "Reply: <code>movie</code> or <code>series</code>",
            parse_mode=ParseMode.HTML,
        )

    elif step == "category":
        if text.lower() not in ("movie", "series"):
            await message.reply(
                "Please reply <code>movie</code> or <code>series</code>",
                parse_mode=ParseMode.HTML,
            )
            return
        state["category"] = text.lower()
        state["step"] = "title"
        await message.reply("✏️ Send the <b>Title</b>:", parse_mode=ParseMode.HTML)

    elif step == "title":
        state["title"] = text
        state["step"] = "language"
        await message.reply(
            "🌐 Send the <b>Language</b>\n"
            "e.g. <code>Malayalam</code>, <code>Tamil</code>, <code>English</code>",
            parse_mode=ParseMode.HTML,
        )

    elif step == "language":
        state["language"] = text.title()
        if state["category"] == "series":
            state["step"] = "extra"
            await message.reply(
                "📺 Send Season / Episode info\n"
                "e.g. <code>S01</code> or <code>S01E02</code>\n"
                "Or type <code>skip</code> to leave blank",
                parse_mode=ParseMode.HTML,
            )
        else:
            await _wizard_save(message, uid)

    elif step == "extra":
        state["extra"] = "" if text.lower() == "skip" else text.upper()
        await _wizard_save(message, uid)


async def _wizard_save(message: Message, uid: int):
    state = _state.pop(uid)
    await add_release(
        state["date"],
        state["category"],
        state["title"],
        state["language"],
        state.get("extra", ""),
    )
    display = datetime.strptime(state["date"], "%Y-%m-%d").strftime("%B %-d %Y")
    extra_text = f" <code>{state['extra']}</code>" if state.get("extra") else ""
    await message.reply(
        f"✅ Added: <b>{state['title']}</b>{extra_text} ({state['language']})\n"
        f"Date: <code>{display}</code>",
        parse_mode=ParseMode.HTML,
    )


# ─────────────────────────────────────────────────────────────────────────────
# /addrelease
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("addrelease") & filters.user(ADMINS))
async def cmd_add_release(_, message: Message):
    uid = message.from_user.id
    _state[uid] = {"step": "date", "action": "add_release"}
    await message.reply(
        "📅 <b>Add Release Wizard</b>\n\n"
        "Step 1 — Send the <b>release date</b>:\n"
        "<code>March 21 2026</code>",
        parse_mode=ParseMode.HTML,
    )


# ─────────────────────────────────────────────────────────────────────────────
# /removerelease  March 21 2026 | Loki
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("removerelease") & filters.user(ADMINS))
async def cmd_remove_release(_, message: Message):
    args = message.text.split(None, 1)
    if len(args) < 2 or "|" not in args[1]:
        await message.reply(
            "Usage: <code>/removerelease March 21 2026 | Title</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    date_raw, title_raw = args[1].split("|", 1)
    d = parse_date(date_raw.strip())
    if not d:
        await message.reply("❌ Invalid date.", parse_mode=ParseMode.HTML)
        return

    removed = await remove_release(d.strftime("%Y-%m-%d"), title_raw.strip())
    if removed:
        await message.reply(
            f"🗑️ Removed <b>{title_raw.strip()}</b> from <code>{d.strftime('%B %-d %Y')}</code>.",
            parse_mode=ParseMode.HTML,
        )
    else:
        await message.reply("⚠️ Entry not found.", parse_mode=ParseMode.HTML)


# ─────────────────────────────────────────────────────────────────────────────
# /sendupdate  <channel_id>   (PM only)
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_message(
    filters.command("sendupdate") & filters.private & filters.user(ADMINS)
)
async def cmd_send_update(client: Client, message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply(
            "Usage: <code>/sendupdate -100xxxxxxxxxx</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    raw = parts[1].strip()
    try:
        channel_id = int(raw)
    except ValueError:
        channel_id = raw  # username like @mychannel

    today = date.today()
    tomorrow = today + timedelta(days=1)

    loading = await message.reply("⏳ Preparing update…")
    today_rel = await get_or_fetch(today)
    tomorrow_rel = await get_or_fetch(tomorrow)
    text_out = format_today_tomorrow(today, today_rel, tomorrow, tomorrow_rel)

    try:
        sent = await client.send_message(
            chat_id=channel_id,
            text=text_out,
            parse_mode=ParseMode.HTML,
        )
        real_id = sent.chat.id
        await add_update_task(real_id, sent.id)
        await loading.edit_text(
            f"✅ Update sent!\n"
            f"Channel: <code>{real_id}</code>\n"
            f"Message ID: <code>{sent.id}</code>\n\n"
            f"This message will be auto-edited every day at <b>00:01 IST</b>.",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await loading.edit_text(
            f"❌ Failed to send:\n<code>{e}</code>",
            parse_mode=ParseMode.HTML,
        )


# ─────────────────────────────────────────────────────────────────────────────
# /stopupdate  <channel_id>   (PM only)
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_message(
    filters.command("stopupdate") & filters.private & filters.user(ADMINS)
)
async def cmd_stop_update(_, message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply(
            "Usage: <code>/stopupdate -100xxxxxxxxxx</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    try:
        channel_id = int(parts[1].strip())
    except ValueError:
        await message.reply("❌ Channel ID must be a number.", parse_mode=ParseMode.HTML)
        return

    await remove_update_task(channel_id)
    await message.reply(
        f"🛑 Daily updates stopped for <code>{channel_id}</code>.",
        parse_mode=ParseMode.HTML,
    )


# ─────────────────────────────────────────────────────────────────────────────
# /listchannels
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("listchannels") & filters.user(ADMINS))
async def cmd_list_channels(_, message: Message):
    tasks = await get_all_update_tasks()
    if not tasks:
        await message.reply("No channels registered for daily updates.")
        return
    lines = ["<b>📢 Registered Update Channels:</b>\n"]
    for i, t in enumerate(tasks, 1):
        lines.append(
            f"{i}. <code>{t['channel_id']}</code>  "
            f"— msg <code>{t.get('message_id', '—')}</code>"
        )
    await message.reply("\n".join(lines), parse_mode=ParseMode.HTML)
