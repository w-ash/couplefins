import uuid

from src.infrastructure.auth.tokens import create_access_token, decode_access_token

_SECRET = "test-secret-key"


def test_create_and_decode_roundtrip() -> None:
    person_id = uuid.uuid4()
    token = create_access_token(person_id, _SECRET, expires_minutes=60)
    decoded = decode_access_token(token, _SECRET)
    assert decoded == person_id


def test_expired_token_returns_none() -> None:
    person_id = uuid.uuid4()
    token = create_access_token(person_id, _SECRET, expires_minutes=-1)
    assert decode_access_token(token, _SECRET) is None


def test_invalid_token_returns_none() -> None:
    assert decode_access_token("not-a-valid-token", _SECRET) is None


def test_wrong_secret_returns_none() -> None:
    person_id = uuid.uuid4()
    token = create_access_token(person_id, _SECRET, expires_minutes=60)
    assert decode_access_token(token, "wrong-secret") is None


def test_empty_token_returns_none() -> None:
    assert decode_access_token("", _SECRET) is None
