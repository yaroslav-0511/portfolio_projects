import asyncio
import logging
import os
import sys

import aiohttp
from aiogram import Bot
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# --- Configuration (secrets only from environment) ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
USER_ID = os.getenv("USER_ID", "").strip()
SYMBOL = os.getenv("SYMBOL", "BTCUSDT").strip().upper()
POLL_INTERVAL_SEC = int(os.getenv("POLL_INTERVAL_SEC", "30"))

# Modern User-Agent to reduce chance of blocks from the exchange API
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class CryptoMonitor:
    """Track a spot symbol via Bybit V5 public API and notify Telegram."""

    def __init__(self, token: str, user_id: str, symbol: str):
        self.bot = Bot(token=token)
        self.user_id = user_id
        self.symbol = symbol
        self.last_price = 0.0
        self.api_url = (
            f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={symbol}"
        )

    def get_dynamic_emoji(self, current_price: float) -> str:
        if self.last_price == current_price:
            return "➡️"
        return "📈" if current_price > self.last_price else "📉"

    async def run_monitoring(self) -> None:
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            while True:
                try:
                    async with session.get(self.api_url, timeout=10) as response:
                        if response.status == 200:
                            data = await response.json()
                            items = data.get("result", {}).get("list") or []
                            if not items:
                                logger.warning("Empty ticker list in API response")
                            else:
                                raw = items[0]
                                current_price = float(raw["lastPrice"])
                                emoji = self.get_dynamic_emoji(current_price)
                                time_now = datetime.now().strftime("%H:%M:%S")
                                message = (
                                    f"<b>📊 {self.symbol} Monitor</b>\n"
                                    f"────────────────────\n"
                                    f"💰 Price: <code>${current_price:,.2f}</code> {emoji}\n"
                                    f"⏰ Updated: {time_now}\n"
                                    f"────────────────────"
                                )
                                await self.bot.send_message(
                                    self.user_id,
                                    message,
                                    parse_mode="HTML",
                                )
                                self.last_price = current_price
                                logger.info(
                                    "Update sent: %s %s", current_price, self.symbol
                                )
                        else:
                            logger.warning("API error: status %s", response.status)
                except Exception:
                    logger.exception("Connection or send issue")

                await asyncio.sleep(POLL_INTERVAL_SEC)


def _validate_config() -> bool:
    if not BOT_TOKEN:
        print("Error: set BOT_TOKEN in .env (see .env.example).", file=sys.stderr)
        return False
    if not USER_ID:
        print("Error: set USER_ID in .env (see .env.example).", file=sys.stderr)
        return False
    if POLL_INTERVAL_SEC < 5:
        print("Error: POLL_INTERVAL_SEC must be at least 5.", file=sys.stderr)
        return False
    return True


if __name__ == "__main__":
    if not _validate_config():
        sys.exit(1)
    monitor = CryptoMonitor(BOT_TOKEN, USER_ID, SYMBOL)
    print(f"Monitoring {SYMBOL} (every {POLL_INTERVAL_SEC}s). Ctrl+C to stop.")
    try:
        asyncio.run(monitor.run_monitoring())
    except (KeyboardInterrupt, SystemExit):
        print("\nStopped.")
