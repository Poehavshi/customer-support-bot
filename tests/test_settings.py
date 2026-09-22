from pathlib import Path

import pytest

from support_agent.settings import load_settings


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)


def test_env_file_values_are_loaded(tmp_path: Path, clean_env: None) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ANTHROPIC_API_KEY=sk-ant-from-file\n"
        "ANTHROPIC_BASE_URL=https://gateway.example/anthropic\n"
        "DATABASE_URL=postgresql://file/support_agent\n"
    )

    settings = load_settings(env_file)

    assert settings.anthropic_api_key == "sk-ant-from-file"
    assert settings.anthropic_base_url == "https://gateway.example/anthropic"
    assert settings.database_url == "postgresql://file/support_agent"


def test_process_environment_wins_over_env_file(
    tmp_path: Path, clean_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://ci/support_agent")
    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_URL=postgresql://file/support_agent\n")

    settings = load_settings(env_file)

    assert settings.database_url == "postgresql://ci/support_agent"


def test_missing_env_file_leaves_unset_values_as_none(tmp_path: Path, clean_env: None) -> None:
    settings = load_settings(tmp_path / ".env")

    assert settings.anthropic_api_key is None
    assert settings.anthropic_base_url is None
    assert settings.database_url is None
