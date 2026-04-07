# Psy for IT BOT (mental-support Telegram bot)

**Public work sample** — production-style [aiogram](https://docs.aiogram.dev/) v3 bot with **PostgreSQL**, **Redis**, **Alembic** migrations, **Docker Compose**, and **RU / EN / UA** strings. Roles: **user**, **consultant**, **owner** (invites, sessions, wellbeing flows — see code under `bot/`).

**Stack:** Python 3.11, aiogram, SQLAlchemy/asyncpg, Redis (FSM + scheduler), pytest.

## What this sample shows

- Long-lived bot with DB-backed state and migrations
- Async handlers, middlewares, i18n JSON
- Dockerized app + Postgres + Redis for local or VPS runs

## Quick start (Docker)

From this folder:

```bash
cd portfolio_projects/psy_for_it_bot
cp .env.example .env
# Edit .env: set BOT_TOKEN (from @BotFather) and OWNER_TELEGRAM_IDS (comma-separated numeric IDs).
docker compose up --build
```

Stop with `Ctrl+C` in the terminal, or `docker compose down` (add `-v` to drop DB volumes if you want a clean reset).

## Full instructions

Step-by-step setup (Windows/Linux, troubleshooting, VPS): **`ЧИТАТЬ_СНАЧАЛА.md`** and **`ИНСТРУКЦИЯ.md`** (Russian). English recipient copy: **`docs/START_HERE_RECIPIENT.md`**.

## Tests

With dev dependencies installed:

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

## Security

Never commit **`.env`** — only **`.env.example`**. No real tokens in the repo.

## License

Public code sample — use and adapt freely; no warranty.
