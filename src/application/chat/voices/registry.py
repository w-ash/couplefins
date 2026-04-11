"""Voice lookup and validation."""

from src.application.chat.voices._types import VoiceDict
from src.application.chat.voices.fiona import VOICE as _FIONA
from src.application.chat.voices.standard import VOICE as _STANDARD

VOICE_NAMES: frozenset[str] = frozenset({"fiona", "standard"})

_VOICES: dict[str, VoiceDict] = {
    "fiona": _FIONA,
    "standard": _STANDARD,
}


def get_voice(name: str) -> VoiceDict:
    """Return the voice dict for *name*, or raise ValueError."""
    try:
        return _VOICES[name]
    except KeyError as exc:
        raise ValueError(
            f"Unknown voice: {name!r}. Valid: {sorted(VOICE_NAMES)}"
        ) from exc
