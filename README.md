# 🎬 OTT Release Date Bot

A Telegram bot that shows OTT (Netflix, Prime, Hotstar, Zee5, SonyLIV…) release dates for movies and series.

---

## Features

| Feature | Description |
|---|---|
| Date query | Send any date → get the release list for that day |
| Manual add | Admin wizard to add releases that APIs may miss |
| Manual remove | Remove a wrong or duplicate entry |
| Channel update | Post Today + Tomorrow list to any channel |
| Auto-edit | That channel message is silently edited every day at 00:01 IST — no new message spam |
| Cross-validation | Release dates are compared across 3 APIs; confirmed when ≥2 agree |

---

## Setup

```bash
git clone <this-repo>
cd OTT-Release-Bot
pip install -r requirements.txt
cp .env.sample .env    # fill in your values
python bot.py
```

Or with Docker:
```bash
docker build -t ott-bot .
docker run --env-file .env ott-bot
```

---

## Environment Variables  (`.env.sample`)

| Variable | Required | Where to get |
|---|---|---|
| `API_ID` | ✅ | https://my.telegram.org |
| `API_HASH` | ✅ | https://my.telegram.org |
| `BOT_TOKEN` | ✅ | @BotFather |
| `ADMINS` | ✅ | Your Telegram user ID(s), space-separated |
| `DATABASE_URI` | ✅ | MongoDB Atlas connection string |
| `DATABASE_NAME` | optional | Default: `OttReleaseBot` |
| `TMDB_API_KEY` | ✅ | https://www.themoviedb.org/settings/api — **FREE** |
| `STREAMING_AVAILABILITY_API_KEY` | recommended | RapidAPI — see below |
| `OTT_DETAILS_API_KEY` | recommended | RapidAPI — see below |

---

## API Keys — Where to Get Them

### 1. TMDB  (FREE — start here)
- Sign up at https://www.themoviedb.org
- Go to Settings → API → Request an API Key
- Free tier: **1,000,000 requests/month**
- What it provides: movie & TV discover by date, streaming watch providers

### 2. Streaming Availability API  (Best for exact OTT dates)
- URL: https://rapidapi.com/movie-of-the-night-movie-of-the-night-default/api/streaming-availability
- Free plan: 100 requests/day &nbsp;|&nbsp; Basic plan: ~$10/month
- Covers India (`country=in`): Netflix IN, Prime Video IN, Disney+ Hotstar, Zee5, SonyLIV, MX Player
- This is the most reliable source for exact OTT streaming calendar dates

### 3. OTT Details API  (India focused — good for regional content)
- URL: https://rapidapi.com/gox-ai-gox-ai-default/api/ott-details
- Has a free tier
- Good for Malayalam / Tamil / Telugu OTT titles that may not appear on global APIs

### Cross-validation logic
The bot fetches from all three APIs and groups results by title.
- If **≥ 2 sources** list the same title on the same date → **confirmed**
- If only **1 source** has it → still shown, but treated as unconfirmed
- This significantly reduces phantom/incorrect dates

> **Tip:** Even with just the TMDB key the bot works. Add the other two for better Indian OTT coverage.

---

## Commands

| Command | Who | Where |
|---|---|---|
| `March 18 2026` (any date) | Everyone | Anywhere |
| `18/03/2026` or `2026-03-18` | Everyone | Anywhere |
| `/start` or `/help` | Everyone | Anywhere |
| `/addrelease` | Admin | Anywhere |
| `/removerelease March 21 2026 \| Title` | Admin | Anywhere |
| `/sendupdate -100xxxxxxxxxx` | Admin | **PM only** |
| `/stopupdate -100xxxxxxxxxx` | Admin | **PM only** |
| `/listchannels` | Admin | Anywhere |

---

## How the daily auto-edit works

1. Admin sends `/sendupdate -100xxxxxxxxxx` to the bot in **private chat**
2. Bot sends the Today + Tomorrow release list to that channel
3. Stores `channel_id` + `message_id` in MongoDB
4. Every night at **00:01 IST** the scheduler wakes up, fetches fresh data, and **edits that same message**
5. The message stays in place — no flood of new posts

To stop: `/stopupdate -100xxxxxxxxxx`

---

## File Structure

```
OTT-Release-Bot/
├── bot.py                  # Entry point
├── info.py                 # Config & env vars
├── scheduler.py            # Daily 00:01 IST auto-edit loop
├── requirements.txt
├── Dockerfile
├── .env.sample
├── plugins/
│   └── ott.py              # All commands, date handler, wizard
├── database/
│   └── ott_db.py           # MongoDB CRUD (releases + update tasks)
└── helpers/
    ├── ott_fetcher.py       # Fetches from 3 APIs, cross-validates
    └── formatter.py         # Builds the exact message format
```
