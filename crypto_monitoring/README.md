# Crypto price monitor (Telegram + Bybit)

**Public work sample** — a small production-style utility: polls the [Bybit V5](https://bybit-exchange.github.io/docs/v5/intro) public spot ticker API and sends formatted price updates to a Telegram chat via [aiogram](https://docs.aiogram.dev/) v3. Documented like a typical freelance handoff (env template, no secrets in the repo).

**Stack:** Python 3.10+, `asyncio`, `aiohttp`, `aiogram`, `python-dotenv`.

## What this sample shows

- Async HTTP client with timeouts and structured logging
- JSON parsing from a REST API
- Long-running polling loop with configurable interval
- Configuration via environment variables (same pattern as client projects under NDA)

## Setup

1. Create a bot with [@BotFather](https://t.me/BotFather), copy the token.
2. Get your numeric Telegram user ID (e.g. message [@userinfobot](https://t.me/userinfobot)).
3. From this folder, create a virtual environment:

```bash
cd portfolio_projects/crypto_monitoring
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

4. Copy environment template and edit:

```bash
cp .env.example .env
# Edit .env: set BOT_TOKEN and USER_ID
```

5. Run:

```bash
python main.py
```

Stop with `Ctrl+C`.

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `BOT_TOKEN` | yes | Telegram bot token |
| `USER_ID` | yes | Recipient chat/user ID for messages |
| `SYMBOL` | no | Spot symbol on Bybit (default `BTCUSDT`) |
| `POLL_INTERVAL_SEC` | no | Seconds between API polls (default `30`) |

## Publishing to GitHub

- Do **not** commit `.env` or real tokens (`.gitignore` already excludes `.env`).
- Optional: add a short screen recording or GIF of a Telegram notification for your Fiverr/Upwork profile.

## Freelance profile templates

Copy-paste texts for marketplaces live in [`../../freelance_portfolio_docs/`](../../freelance_portfolio_docs/) (Fiverr gigs, Upwork proposals, scope checklist).

## License

Public code sample — use and adapt freely; no warranty.
