from pydantic import BaseModel, EmailStr, field_validator

from database.validators.users import validate_password_strength


class UserRegistrationRequestSchema(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, value):
        return validate_password_strength(value)


class UserRegistrationResponseSchema(BaseModel):
    id: int
    email: str


class UserActivation(BaseModel):
    message: str


class UserResendActivationEmail(BaseModel):
    email: EmailStr

