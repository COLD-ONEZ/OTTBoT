from os import environ

# ── Telegram ──────────────────────────────────────────────────────────────────
API_ID   = int(environ.get("API_ID", "20400973"))
API_HASH = environ.get("API_HASH", "047838cb76d54bc445e155a7cab44664")
BOT_TOKEN = environ.get("BOT_TOKEN", "8725923727:AAFJdfFQONozrmrNYmeVc8_qYUt5kIx2lDA")

# Space-separated Telegram user IDs that have admin access
ADMINS = [
    int(x) for x in environ.get("ADMINS", "5677517133 5329179170").split()
    if x.strip().isdigit()
]

# ── MongoDB ────────────────────────────────────────────────────────────────────
DATABASE_URI  = environ.get("DATABASE_URI", "mongodb+srv://amalabraham989:seriesfactory@sfactory.a7gq1.mongodb.net/?retryWrites=true&w=majority&appName=sfactory")
DATABASE_NAME = environ.get("DATABASE_NAME", "sfactory")

# ── OTT / Streaming API Keys ──────────────────────────────────────────────────

# 1. TMDB (FREE)  →  https://www.themoviedb.org/settings/api
TMDB_API_KEY = environ.get("TMDB_API_KEY", "7d034fbeb71688b7be38ef92a020a79f")

# 2. Streaming Availability API (RapidAPI)
#    https://rapidapi.com/movie-of-the-night-movie-of-the-night-default/api/streaming-availability
STREAMING_AVAILABILITY_API_KEY = environ.get("STREAMING_AVAILABILITY_API_KEY", "1bca4f2baamsh845ce3c7d565b24p133fa3jsnc6518baacd36")

# 3. OTT Details API (RapidAPI) — India focused
#    https://rapidapi.com/gox-ai-gox-ai-default/api/ott-details
OTT_DETAILS_API_KEY = environ.get("OTT_DETAILS_API_KEY", "b573a7d01fmsh1eedbb86e0752efp15d71bjsn3b35a9c55a70")
