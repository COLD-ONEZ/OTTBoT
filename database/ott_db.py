import motor.motor_asyncio
from info import DATABASE_URI, DATABASE_NAME
import logging

logger = logging.getLogger(__name__)

client = motor.motor_asyncio.AsyncIOMotorClient(DATABASE_URI)
db = client[DATABASE_NAME]

# Collections
releases_col = db["ott_releases"]       # Stores release entries per date
update_tasks_col = db["update_tasks"]   # Stores /sendupdate channel tasks


# ── Release CRUD ──────────────────────────────────────────────────────────────

async def add_release(date_str: str, category: str, title: str, language: str, extra: str = ""):
    """
    Add a release entry.
    category: 'movie' or 'series'
    date_str: 'YYYY-MM-DD'
    extra: episode info like 'S01E02' for series, empty for movies
    """
    doc = {
        "date": date_str,
        "category": category,   # 'movie' or 'series'
        "title": title,
        "language": language,
        "extra": extra,         # e.g. 'S01' or 'S01E02' for series
    }
    # Avoid duplicates
    existing = await releases_col.find_one({
        "date": date_str,
        "title": {"$regex": f"^{title}$", "$options": "i"},
    })
    if existing:
        await releases_col.replace_one({"_id": existing["_id"]}, doc)
    else:
        await releases_col.insert_one(doc)


async def remove_release(date_str: str, title: str):
    result = await releases_col.delete_one({
        "date": date_str,
        "title": {"$regex": f"^{title}$", "$options": "i"},
    })
    return result.deleted_count > 0


async def get_releases_by_date(date_str: str) -> dict:
    """Returns {'movies': [...], 'series': [...]}"""
    cursor = releases_col.find({"date": date_str})
    movies = []
    series = []
    async for doc in cursor:
        if doc["category"] == "movie":
            movies.append(doc)
        else:
            series.append(doc)
    return {"movies": movies, "series": series}


async def clear_releases_by_date(date_str: str):
    await releases_col.delete_many({"date": date_str})


# ── Update Task CRUD ──────────────────────────────────────────────────────────

async def add_update_task(channel_id: int, message_id: int = None):
    """Register a channel to receive daily OTT updates."""
    existing = await update_tasks_col.find_one({"channel_id": channel_id})
    if existing:
        await update_tasks_col.update_one(
            {"channel_id": channel_id},
            {"$set": {"message_id": message_id}}
        )
    else:
        await update_tasks_col.insert_one({
            "channel_id": channel_id,
            "message_id": message_id,
        })


async def get_all_update_tasks():
    tasks = []
    async for doc in update_tasks_col.find({}):
        tasks.append(doc)
    return tasks


async def remove_update_task(channel_id: int):
    await update_tasks_col.delete_one({"channel_id": channel_id})


async def update_task_message_id(channel_id: int, message_id: int):
    await update_tasks_col.update_one(
        {"channel_id": channel_id},
        {"$set": {"message_id": message_id}}
    )
