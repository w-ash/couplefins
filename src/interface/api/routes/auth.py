from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from src.application.runner import execute_use_case
from src.application.use_cases.auth.change_password import (
    ChangePasswordCommand,
    ChangePasswordUseCase,
)
from src.application.use_cases.auth.login import LoginCommand, LoginUseCase
from src.application.use_cases.auth.reset_partner_password import (
    ResetPartnerPasswordCommand,
    ResetPartnerPasswordUseCase,
)
from src.application.use_cases.list_persons import list_persons
from src.config.settings import get_settings
from src.domain.entities.person import Person
from src.infrastructure.auth.password import hash_password, verify_password
from src.infrastructure.auth.tokens import create_access_token
from src.interface.api.dependencies import get_current_user
from src.interface.api.schemas.auth import (
    AuthPersonResponse,
    ChangePasswordRequest,
    LoginRequest,
    ResetPartnerPasswordRequest,
)
from src.interface.api.schemas.persons import PersonResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/persons")
async def list_auth_persons() -> list[AuthPersonResponse]:
    result = await execute_use_case(list_persons)
    return [AuthPersonResponse(name=p.name) for p in result.persons]


@router.post("/login")
async def login(body: LoginRequest) -> JSONResponse:
    settings = get_settings()

    def _create_token(person_id: UUID) -> str:
        return create_access_token(
            person_id, settings.auth.jwt_secret, settings.auth.token_expiry_minutes
        )

    command = LoginCommand(name=body.name, password=body.password)
    result = await execute_use_case(
        lambda uow: LoginUseCase(
            verify_password=verify_password,
            create_token=_create_token,
        ).execute(command, uow)
    )
    data = PersonResponse.from_domain(result.person)
    response = JSONResponse(content=data.model_dump(mode="json"))
    response.set_cookie(
        key=settings.auth.cookie_name,
        value=result.token,
        httponly=True,
        secure=settings.auth.cookie_secure,
        samesite=settings.auth.cookie_samesite,
        max_age=settings.auth.token_expiry_minutes * 60,
        path="/",
    )
    return response


@router.post("/logout")
async def logout() -> JSONResponse:
    settings = get_settings()
    response = JSONResponse(content={"ok": True})
    response.delete_cookie(key=settings.auth.cookie_name, path="/")
    return response


@router.get("/me")
async def get_me(
    current_user: Person = Depends(get_current_user),
) -> PersonResponse:
    return PersonResponse.from_domain(current_user)


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    current_user: Person = Depends(get_current_user),
) -> JSONResponse:
    command = ChangePasswordCommand(
        person_id=current_user.id,
        current_password=body.current_password,
        new_password=body.new_password,
    )
    await execute_use_case(
        lambda uow: ChangePasswordUseCase(
            verify_password=verify_password,
            hash_password=hash_password,
        ).execute(command, uow)
    )
    return JSONResponse(content={"ok": True})


@router.post("/reset-partner-password")
async def reset_partner_password(
    body: ResetPartnerPasswordRequest,
    current_user: Person = Depends(get_current_user),
) -> JSONResponse:
    command = ResetPartnerPasswordCommand(
        requester_person_id=current_user.id,
        new_password=body.new_password,
    )
    await execute_use_case(
        lambda uow: ResetPartnerPasswordUseCase(
            hash_password=hash_password,
        ).execute(command, uow)
    )
    return JSONResponse(content={"ok": True})
