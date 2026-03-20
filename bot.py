import logging
import asyncio
from pyrogram import Client
from pyrogram.enums import ParseMode
from info import API_ID, API_HASH, BOT_TOKEN, ADMINS
from scheduler import start_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s — %(message)s",
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)


class Bot(Client):
    def __init__(self):
        super().__init__(
            name="OttReleaseBot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            plugins=dict(root="plugins"),
        )

    async def start(self):
        await super().start()
        me = await self.get_me()
        logging.info(f"✅ Bot started as @{me.username}")

        for admin in ADMINS:
            try:
                await self.send_message(
                    admin,
                    "✅ <b>OTT Release Bot started!</b>",
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass

        # Kick off the daily 00:01 IST channel-edit loop
        start_scheduler(self)

    async def stop(self, *args):
        await super().stop()
        logging.info("Bot stopped.")


if __name__ == "__main__":
    Bot().run()
