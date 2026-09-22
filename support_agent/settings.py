"""Project settings, read from the process environment and a git-ignored ``.env`` file.

Values already present in the process environment win over the file, so CI and
compose can set them without a stray ``.env`` overriding them. The file is read
without mutating ``os.environ``.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

# The project is installed editable by `uv sync`, so the package sits inside the repo.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str | None
    anthropic_base_url: str | None
    database_url: str | None


def load_settings(env_file: Path = DEFAULT_ENV_FILE) -> Settings:
    """Read ``env_file`` if it exists, letting the process environment override it."""
    values = {**dotenv_values(env_file), **os.environ}
    return Settings(
        anthropic_api_key=values.get("ANTHROPIC_API_KEY"),
        anthropic_base_url=values.get("ANTHROPIC_BASE_URL"),
        database_url=values.get("DATABASE_URL"),
    )
