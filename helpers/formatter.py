"""
formatter.py
Produces the exact message format shown in the screenshots.

Single-date (Image 1):
    March 18 2026

    Movies

    1. Sarvam maya (Malayalam)
    2. Thani oruvan (Tamil)

    Series

    1. Loki S01 (English)
    2. Stranger Things S01E02 (English)

Today+Tomorrow (Image 2):
    Today - March 20 2026

    Movies
    ...
    Series
    ...

    Tomorrow - March 21 2026

    Movies
    ...
    Series
    ...
"""

from datetime import date
from typing import Optional


# ISO 639-1 → full name
_LANG_MAP = {
    "ml": "Malayalam",
    "ta": "Tamil",
    "te": "Telugu",
    "hi": "Hindi",
    "kn": "Kannada",
    "en": "English",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "fr": "French",
    "es": "Spanish",
    "de": "German",
    "pt": "Portuguese",
    "it": "Italian",
    "ru": "Russian",
    "ar": "Arabic",
    "th": "Thai",
    "id": "Indonesian",
}


def resolve_language(lang: str) -> str:
    """Convert ISO 639-1 code OR already-full language name to a display name."""
    if not lang:
        return "Unknown"
    code = lang.lower().strip()
    return _LANG_MAP.get(code, lang.title())


def _fmt_date(d: date) -> str:
    """'March 18 2026' — no leading zero, cross-platform."""
    return d.strftime("%B ") + str(d.day) + d.strftime(" %Y")


def _build_section(releases: dict) -> str:
    """
    Build the Movies + Series block.
    releases = {'movies': [doc, ...], 'series': [doc, ...]}
    """
    parts = []

    movies = releases.get("movies", [])
    if movies:
        parts.append("\n<b>Movies</b>\n")
        for i, m in enumerate(movies, 1):
            lang = resolve_language(m.get("language", ""))
            parts.append(f"{i}. {m['title']} ({lang})")

    series_list = releases.get("series", [])
    if series_list:
        parts.append("\n<b>Series</b>\n")
        for i, s in enumerate(series_list, 1):
            lang = resolve_language(s.get("language", ""))
            extra = (s.get("extra") or "").strip()
            title_part = f"{s['title']} {extra}".strip() if extra else s["title"]
            parts.append(f"{i}. {title_part} ({lang})")

    if not movies and not series_list:
        parts.append("\n<i>No releases found.</i>")

    return "\n".join(parts)


def format_single_date(d: date, releases: dict) -> str:
    """Image 1 style — one date."""
    header = f"<b>{_fmt_date(d)}</b>"
    return header + "\n" + _build_section(releases)


def format_today_tomorrow(
    today: date,
    today_releases: dict,
    tomorrow: date,
    tomorrow_releases: dict,
) -> str:
    """Image 2 style — Today + Tomorrow."""
    today_block = (
        f"<pre><b>Today - {_fmt_date(today)}</b></pre>\n"
        + _build_section(today_releases)
    )
    tomorrow_block = (
        f"\n<pre><b>Tomorrow - {_fmt_date(tomorrow)}</b></pre>\n"
        + _build_section(tomorrow_releases)
    )
    return today_block + "\n" + tomorrow_block
