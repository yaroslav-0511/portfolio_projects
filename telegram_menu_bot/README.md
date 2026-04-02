# Telegram menu bot (inline keyboard + APIs)

**Public work sample** — [aiogram](https://docs.aiogram.dev/) v3 bot with **inline buttons**: weather for two preset cities via [Open-Meteo](https://open-meteo.com/), random quote via [ZenQuotes](https://zenquotes.io/), short “About”. Good **second Telegram screenshot** vs. the price-polling bot in `crypto_monitoring/`.

**Stack:** Python 3.10+, aiogram, aiohttp, python-dotenv.

## What this sample shows

- `Command("start")` and `CallbackQuery` handlers
- `InlineKeyboardMarkup` / `InlineKeyboardButton`
- Async HTTP to public JSON APIs

## Setup

1. Create a bot with [@BotFather](https://t.me/BotFather), copy the token.
2. From this folder:

```bash
cd portfolio_projects/telegram_menu_bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# set BOT_TOKEN in .env
python main.py
```

Stop with `Ctrl+C`.

## Notes

- ZenQuotes and Open-Meteo may rate-limit heavy use; fine for demos.
- For portfolio photos, open the chat, tap `/start`, then capture the **menu and a reply** after a button press.

## License

Public code sample — use and adapt freely; no warranty.
