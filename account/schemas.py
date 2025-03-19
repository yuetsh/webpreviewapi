from typing import List
from ninja import Schema, ModelSchema
from pydantic import EmailStr, Field

from .models import User, RoleChoices


class UserListSchema(ModelSchema):
    @classmethod
    def get(cls, obj):
        raw_password = obj.raw_password if obj.role != RoleChoices.SUPER else ""
        return cls(
            id=obj.id,
            username=obj.username,
            raw_password=raw_password,
            role=obj.role,
            date_joined=obj.date_joined,
            last_login=obj.last_login,
            is_active=obj.is_active,
        )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "raw_password",
            "role",
            "date_joined",
            "last_login",
            "is_active",
        ]


class UserRegistrationSchema(Schema):
    username: str
    email: EmailStr
    password: str = Field(min_length=6, max_length=20)


class UserLoginSchema(Schema):
    username: str
    password: str


class BatchUsersIn(Schema):
    names: List[str]
    classname: str
