"""Small Telegram bot: inline menu, weather snippet (Open-Meteo), random quote (ZenQuotes)."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

dp = Dispatcher()


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🌤 Weather (Berlin)",
                    callback_data="wx:52.52:13.41",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🌤 Weather (NYC)",
                    callback_data="wx:40.7128:-74.006",
                )
            ],
            [InlineKeyboardButton(text="💬 Random quote", callback_data="quote")],
            [InlineKeyboardButton(text="ℹ️ About", callback_data="about")],
        ]
    )


async def fetch_weather(session: aiohttp.ClientSession, lat: float, lon: float) -> str:
    url = (
        "https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        "&current=temperature_2m,relative_humidity_2m"
        "&timezone=auto"
    )
    async with session.get(url, timeout=15) as resp:
        resp.raise_for_status()
        data = await resp.json()
    cur = data.get("current") or {}
    t = cur.get("temperature_2m")
    h = cur.get("relative_humidity_2m")
    if t is None:
        return "Could not read temperature from API."
    line2 = f"Humidity: {h}%" if h is not None else ""
    return f"📍 {lat}, {lon}\n🌡 <b>{t} °C</b>\n{line2}".strip()


async def fetch_quote(session: aiohttp.ClientSession) -> str:
    url = "https://zenquotes.io/api/random"
    async with session.get(url, timeout=15) as resp:
        resp.raise_for_status()
        raw = await resp.text()
    data = json.loads(raw)
    if not data:
        return "No quote returned."
    item = data[0]
    q = item.get("q", "").strip()
    a = item.get("a", "").strip()
    return f"“{q}”\n— <i>{a}</i>" if a else f"“{q}”"


@dp.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Choose an action:",
        reply_markup=main_menu(),
    )


@dp.callback_query(F.data == "about")
async def cb_about(query: CallbackQuery) -> None:
    await query.answer()
    await query.message.answer(
        "Public work sample: inline keyboard + Open-Meteo + ZenQuotes API.",
    )


@dp.callback_query(F.data == "quote")
async def cb_quote(query: CallbackQuery) -> None:
    await query.answer("Fetching…")
    try:
        async with aiohttp.ClientSession() as session:
            text = await fetch_quote(session)
        await query.message.answer(text, parse_mode="HTML")
    except Exception:
        logger.exception("quote failed")
        await query.message.answer("Quote service unavailable. Try again later.")


@dp.callback_query(F.data.startswith("wx:"))
async def cb_weather(query: CallbackQuery) -> None:
    await query.answer("Loading…")
    try:
        _, lat_s, lon_s = query.data.split(":", 2)
        lat, lon = float(lat_s), float(lon_s)
    except ValueError:
        await query.message.answer("Invalid location payload.")
        return
    try:
        async with aiohttp.ClientSession() as session:
            text = await fetch_weather(session, lat, lon)
        await query.message.answer(text, parse_mode="HTML")
    except Exception:
        logger.exception("weather failed")
        await query.message.answer("Weather API error. Try again later.")


async def main() -> None:
    if not BOT_TOKEN:
        print("Set BOT_TOKEN in .env (see .env.example).", file=sys.stderr)
        sys.exit(1)
    bot = Bot(BOT_TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
