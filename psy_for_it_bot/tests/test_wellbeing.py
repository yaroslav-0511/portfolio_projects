import pytest

from bot.services.wellbeing import who5_raw_and_percent, who5_recommendation_key


def test_who5_all_zero() -> None:
    raw, pct = who5_raw_and_percent([0, 0, 0, 0, 0])
    assert raw == 0
    assert pct == 0


def test_who5_all_five() -> None:
    raw, pct = who5_raw_and_percent([5, 5, 5, 5, 5])
    assert raw == 25
    assert pct == 100


def test_who5_recommendation_keys() -> None:
    assert who5_recommendation_key(40) == "who5_rec_low"
    assert who5_recommendation_key(60) == "who5_rec_mid"
    assert who5_recommendation_key(80) == "who5_rec_high"


def test_who5_invalid_length() -> None:
    with pytest.raises(ValueError):
        who5_raw_and_percent([1, 2, 3])
