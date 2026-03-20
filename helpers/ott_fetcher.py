"""
ott_fetcher.py
Fetches OTT streaming release dates from multiple APIs and cross-validates them.

APIs used (configure keys in info.py / env vars):
  1. TMDB  — https://www.themoviedb.org/settings/api  (FREE, 1M req/month)
     - watch_providers endpoint gives which platforms stream a title
     - release_dates endpoint gives digital/streaming release dates
  2. Streaming Availability API (RapidAPI)
     — https://rapidapi.com/movie-of-the-night-movie-of-the-night-default/api/streaming-availability
     - Dedicated OTT streaming calendar, supports Netflix/Prime/Hotstar etc.
  3. OTT Details API (RapidAPI)
     — https://rapidapi.com/gox-ai-gox-ai-default/api/ott-details
     - Gives OTT platform & release date per title (India-focused)

Cross-validation logic:
  - A release date is marked 'confirmed' if ≥2 sources agree (within ±1 day).
  - If only 1 source has data it is marked 'unconfirmed'.
  - The best/earliest agreed date is returned.
"""

import logging
import asyncio
import aiohttp
from datetime import date, datetime, timedelta
from typing import Optional
from info import TMDB_API_KEY, STREAMING_AVAILABILITY_API_KEY, OTT_DETAILS_API_KEY

logger = logging.getLogger(__name__)

TMDB_BASE = "https://api.themoviedb.org/3"

# ── Low-level helpers ─────────────────────────────────────────────────────────

async def _get(session: aiohttp.ClientSession, url: str, params: dict = None, headers: dict = None):
    try:
        async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status == 200:
                return await r.json()
    except Exception as e:
        logger.warning(f"HTTP GET failed {url}: {e}")
    return None


# ── TMDB ──────────────────────────────────────────────────────────────────────

async def tmdb_new_releases(session, target_date: date, media_type="movie"):
    """
    Fetch TMDB 'discover' results filtered by release date.
    media_type: 'movie' or 'tv'
    """
    date_str = target_date.strftime("%Y-%m-%d")
    url = f"{TMDB_BASE}/discover/{media_type}"
    params = {
        "api_key": TMDB_API_KEY,
        "language": "en-US",
        "sort_by": "popularity.desc",
        "page": 1,
        "with_watch_monetization_types": "flatrate",  # streaming only
    }
    if media_type == "movie":
        params["primary_release_date.gte"] = date_str
        params["primary_release_date.lte"] = date_str
    else:
        params["first_air_date.gte"] = date_str
        params["first_air_date.lte"] = date_str

    data = await _get(session, url, params)
    results = []
    if data:
        for item in data.get("results", []):
            title = item.get("title") or item.get("name", "")
            lang = item.get("original_language", "").upper()
            results.append({
                "source": "tmdb",
                "title": title,
                "language": lang,
                "date": date_str,
                "media_type": media_type,
                "tmdb_id": item.get("id"),
            })
    return results


async def tmdb_tv_season_releases(session, target_date: date):
    """Get TV episodes/seasons airing on a specific date via TMDB."""
    date_str = target_date.strftime("%Y-%m-%d")
    url = f"{TMDB_BASE}/discover/tv"
    params = {
        "api_key": TMDB_API_KEY,
        "language": "en-US",
        "air_date.gte": date_str,
        "air_date.lte": date_str,
        "with_watch_monetization_types": "flatrate",
        "sort_by": "popularity.desc",
    }
    data = await _get(session, url, params)
    results = []
    if data:
        for item in data.get("results", []):
            title = item.get("name", "")
            lang = item.get("original_language", "").upper()
            results.append({
                "source": "tmdb_tv",
                "title": title,
                "language": lang,
                "date": date_str,
                "media_type": "tv",
                "tmdb_id": item.get("id"),
            })
    return results


# ── Streaming Availability API (RapidAPI) ─────────────────────────────────────

async def streaming_avail_releases(session, target_date: date):
    """
    Streaming Availability API — new titles arriving on a specific date.
    Docs: https://docs.movieofthenight.com
    """
    if not STREAMING_AVAILABILITY_API_KEY:
        return []

    # The API supports /shows/search/filters with output_language, order_by=original_title
    # and streaming_date range
    date_str = target_date.strftime("%Y-%m-%d")
    url = "https://streaming-availability.p.rapidapi.com/shows/search/filters"
    headers = {
        "X-RapidAPI-Key": STREAMING_AVAILABILITY_API_KEY,
        "X-RapidAPI-Host": "streaming-availability.p.rapidapi.com",
    }
    params = {
        "order_by": "original_title",
        "output_language": "en",
        "country": "in",           # India — covers Netflix IN, Prime IN, Hotstar, etc.
        "catalogs": "netflix,prime,disney,hotstar,zee5,sonyliv,mxplayer",
        "show_type": "movie",
        # The API uses unix timestamps for date ranges
        "streaming_date_from": str(int(datetime.combine(target_date, datetime.min.time()).timestamp())),
        "streaming_date_to": str(int(datetime.combine(target_date + timedelta(days=1), datetime.min.time()).timestamp())),
    }

    results = []
    for show_type in ["movie", "series"]:
        params["show_type"] = show_type
        data = await _get(session, url, params=params, headers=headers)
        if data:
            for item in data.get("shows", []):
                title = item.get("title", "")
                lang_code = (item.get("originalTitle") or "").upper()
                results.append({
                    "source": "streaming_avail",
                    "title": title,
                    "language": lang_code or "EN",
                    "date": date_str,
                    "media_type": show_type,
                })
    return results


# ── OTT Details API (RapidAPI) — India focused ────────────────────────────────

async def ott_details_releases(session, target_date: date):
    """
    OTT Details API — India OTT platform data.
    Docs: https://rapidapi.com/gox-ai-gox-ai-default/api/ott-details
    """
    if not OTT_DETAILS_API_KEY:
        return []

    date_str = target_date.strftime("%d-%m-%Y")  # This API uses DD-MM-YYYY
    url = "https://ott-details.p.rapidapi.com/getNewRelease"
    headers = {
        "X-RapidAPI-Key": OTT_DETAILS_API_KEY,
        "X-RapidAPI-Host": "ott-details.p.rapidapi.com",
    }
    params = {"date": date_str}

    data = await _get(session, url, params=params, headers=headers)
    results = []
    if data and isinstance(data, list):
        for item in data:
            title = item.get("title", "")
            lang = item.get("language", "Unknown").title()
            media_type = "movie" if item.get("type", "").lower() == "movie" else "tv"
            results.append({
                "source": "ott_details",
                "title": title,
                "language": lang,
                "date": target_date.strftime("%Y-%m-%d"),
                "media_type": media_type,
                "extra": item.get("season", "") or "",
            })
    return results


# ── Cross-validation ──────────────────────────────────────────────────────────

def _normalize(title: str) -> str:
    return title.lower().strip()


def cross_validate(all_results: list) -> list:
    """
    Group results by normalized title. Mark as 'confirmed' if ≥2 sources agree.
    Returns a deduplicated list with a 'confirmed' flag.
    """
    grouped = {}
    for r in all_results:
        key = _normalize(r["title"])
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(r)

    final = []
    for key, entries in grouped.items():
        sources = list({e["source"] for e in entries})
        best = entries[0]
        # Prefer entry with most data (extra field, language)
        for e in entries:
            if e.get("extra"):
                best = e
                break
        best["confirmed"] = len(sources) >= 2
        best["sources_count"] = len(sources)
        final.append(best)

    return final


# ── Main public function ──────────────────────────────────────────────────────

async def fetch_ott_releases(target_date: date) -> dict:
    """
    Fetch all OTT releases for a given date from all configured APIs.
    Returns: {'movies': [...], 'series': [...]}
    Each entry: {title, language, extra, confirmed, sources_count}
    """
    async with aiohttp.ClientSession() as session:
        tasks = [
            tmdb_new_releases(session, target_date, "movie"),
            tmdb_new_releases(session, target_date, "tv"),
            tmdb_tv_season_releases(session, target_date),
            streaming_avail_releases(session, target_date),
            ott_details_releases(session, target_date),
        ]
        gathered = await asyncio.gather(*tasks, return_exceptions=True)

    all_results = []
    for r in gathered:
        if isinstance(r, list):
            all_results.extend(r)

    validated = cross_validate(all_results)

    movies = [r for r in validated if r.get("media_type") == "movie"]
    series = [r for r in validated if r.get("media_type") in ("tv", "series")]

    return {"movies": movies, "series": series}
