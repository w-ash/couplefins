from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt


def create_access_token(person_id: UUID, secret: str, expires_minutes: int) -> str:
    payload = {
        "sub": str(person_id),
        "exp": datetime.now(UTC) + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, secret, algorithm="HS256")  # pyright: ignore[reportUnknownMemberType]


_DECODE_ERRORS = (jwt.InvalidTokenError, KeyError, ValueError)


def decode_access_token(token: str, secret: str) -> UUID | None:
    try:
        payload: dict[str, str] = jwt.decode(token, secret, algorithms=["HS256"])  # pyright: ignore[reportUnknownMemberType]
        return UUID(payload["sub"])
    except _DECODE_ERRORS:
        return None
