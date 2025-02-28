from ninja import Schema
from pydantic import EmailStr, Field


class UserRegistrationSchema(Schema):
    username: str
    email: EmailStr
    password: str = Field(min_length=6)


class UserLoginSchema(Schema):
    username: str
    password: str
