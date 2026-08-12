from pydantic import BaseModel, EmailStr, Field, model_validator


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


class GoogleAuthRequest(BaseModel):
    idToken: str | None = Field(default=None, min_length=1)
    accessToken: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_token(self) -> "GoogleAuthRequest":
        if not self.idToken and not self.accessToken:
            raise ValueError("Either idToken or accessToken is required")
        if self.idToken and self.accessToken:
            raise ValueError("Provide only one of idToken or accessToken")
        return self


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UpdateTeamRoleRequest(BaseModel):
    teamRole: str = Field(min_length=1, max_length=100)
