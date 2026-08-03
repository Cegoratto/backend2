from pydantic import BaseModel, EmailStr, Field


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    teamRole: str | None = None

    model_config = {"from_attributes": True}


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    teamRole: str = Field(min_length=1, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UpdateTeamRoleRequest(BaseModel):
    teamRole: str = Field(min_length=1, max_length=100)
