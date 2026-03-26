from pydantic import BaseModel


class LoginRequest(BaseModel):
    name: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ResetPartnerPasswordRequest(BaseModel):
    new_password: str


class SetInitialPasswordRequest(BaseModel):
    name: str
    new_password: str


class AuthPersonResponse(BaseModel):
    name: str
    has_password: bool
