from importlib import reload

import bot.config as config


def test_owner_ids_ignore_invalid_values(monkeypatch):
    monkeypatch.setenv("OWNER_TELEGRAM_IDS", "123,abc, 456 , !, 789x")
    reload(config)

    assert config.OWNER_TELEGRAM_IDS == [123, 456]


def test_invite_rate_limit_default_for_dev(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.delenv("INVITE_RATE_LIMIT_ENABLED", raising=False)
    reload(config)

    assert config.INVITE_RATE_LIMIT_ENABLED is False


def test_invite_rate_limit_default_for_prod(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.delenv("INVITE_RATE_LIMIT_ENABLED", raising=False)
    reload(config)

    assert config.INVITE_RATE_LIMIT_ENABLED is True


def test_invite_rate_limit_explicit_override(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("INVITE_RATE_LIMIT_ENABLED", "false")
    reload(config)

    assert config.INVITE_RATE_LIMIT_ENABLED is False
