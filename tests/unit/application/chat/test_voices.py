import pytest

from src.application.chat.voices import VOICE_NAMES, get_voice


def test_get_voice_fiona() -> None:
    voice = get_voice("fiona")
    assert isinstance(voice["identity"], str)
    assert len(voice["identity"]) > 0
    assert len(voice["voice_examples"]) > 0
    assert len(voice["rules"]) > 0


def test_get_voice_standard() -> None:
    voice = get_voice("standard")
    assert isinstance(voice["identity"], str)
    assert len(voice["identity"]) > 0
    assert voice["voice_examples"] == []
    assert voice["rules"] == []


def test_get_voice_unknown_raises() -> None:
    with pytest.raises(ValueError, match="Unknown voice"):
        get_voice("nonexistent")


def test_get_voice_empty_raises() -> None:
    with pytest.raises(ValueError, match="Unknown voice"):
        get_voice("")


def test_all_voice_names_resolve() -> None:
    for name in VOICE_NAMES:
        voice = get_voice(name)
        assert "identity" in voice
        assert "voice_examples" in voice
        assert "rules" in voice


def test_voice_names_are_lowercase() -> None:
    for name in VOICE_NAMES:
        assert name == name.lower()
        assert len(name) > 0


def test_fiona_identity_under_budget() -> None:
    """Fiona identity should be concise — roughly 200 tokens (~300 words max)."""
    voice = get_voice("fiona")
    word_count = len(str(voice["identity"]).split())
    assert word_count < 300
