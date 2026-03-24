from fastapi import Request

from src.application.runner import execute_use_case
from src.config.settings import get_settings
from src.domain.entities.person import Person
from src.domain.exceptions import AuthenticationError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol
from src.infrastructure.auth.tokens import decode_access_token


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
