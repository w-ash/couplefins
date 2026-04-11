from fastapi import Request

from src.application.chat.protocols import LLMClientProtocol
from src.application.runner import execute_use_case
from src.config.settings import get_settings
from src.domain.entities.person import Person
from src.domain.exceptions import AuthenticationError, ChatUnavailableError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol
from src.infrastructure.auth.tokens import decode_access_token

_llm_client: LLMClientProtocol | None = None


def set_llm_client(client: LLMClientProtocol | None) -> None:
    global _llm_client  # noqa: PLW0603
    _llm_client = client


def is_chat_available() -> bool:
    return _llm_client is not None


async def get_current_user(request: Request) -> Person:
    settings = get_settings()
    token = request.cookies.get(settings.auth.cookie_name)
    if not token:
        raise AuthenticationError("Not authenticated")

    person_id = decode_access_token(token, settings.auth.jwt_secret)
    if person_id is None:
        raise AuthenticationError("Invalid or expired token")

    async def _lookup(uow: UnitOfWorkProtocol) -> Person:
        person = await uow.persons.get_by_id(person_id)
        if person is None:
            raise AuthenticationError("User not found")
        return person

    return await execute_use_case(_lookup)


def get_llm_client() -> LLMClientProtocol:
    if _llm_client is None:
        raise ChatUnavailableError(
            "Chat is not available — no ANTHROPIC_API_KEY configured"
        )
    return _llm_client
