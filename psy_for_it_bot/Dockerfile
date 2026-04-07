FROM python:3.11-slim

WORKDIR /app

# Optional dev dependencies
ARG INSTALL_DEV=false

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Dev/test dependencies (optional)
COPY requirements-dev.txt .
RUN if [ "$INSTALL_DEV" = "true" ]; then pip install --no-cache-dir -r requirements-dev.txt; fi

# Copy source code
COPY bot/ ./bot/
COPY migrations/ ./migrations/
COPY alembic.ini ./alembic.ini
COPY pytest.ini ./pytest.ini
COPY tests/ ./tests/

CMD ["python", "-m", "bot.main"]
