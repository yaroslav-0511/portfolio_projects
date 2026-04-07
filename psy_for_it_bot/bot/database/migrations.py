from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def run_migrations() -> None:
    """Apply all pending Alembic migrations."""
    project_root = Path(__file__).resolve().parents[2]

    logger.info("Running Alembic migrations...")
    subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=project_root,
        check=True,
    )
    logger.info("Alembic migrations finished")
