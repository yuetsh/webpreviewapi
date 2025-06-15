import random
from typing import List
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from ninja import Router
from ninja.pagination import paginate
from ninja.errors import HttpError
from .schemas import (
    BatchUsersIn,
    UserListSchema,
    UserRegistrationSchema,
    UserLoginSchema,
)
from .models import RoleChoices, User
from .decorators import super_required
from django.db import transaction
import secrets
import string

router = Router()


def generate_password(length=6):
    """生成更安全的随机密码"""
    alphabet = string.digits[2:]  # 只使用2-9的数字
    return "".join(secrets.choice(alphabet) for _ in range(length))


@router.post("/register")
def user_register(request, payload: UserRegistrationSchema):
    if User.objects.filter(username=payload.username).exists():
        raise HttpError(400, "用户已存在")
    User.objects.create_user(
        username=payload.username,
        email=payload.email,
        password=payload.password,
    )
    return {"message": "创建成功"}


@router.post("/login")
def user_login(request, payload: UserLoginSchema):
    user = authenticate(username=payload.username, password=payload.password)
    if user:
        login(request, user)
        return {"username": user.username, "role": user.role}
    else:
        raise HttpError(401, "账号密码错误")


@router.post("/logout")
@login_required
def user_logout(request):
    logout(request)
    return {"message": "退出成功"}


@router.get("/profile")
def my_profile(request):
    # 首页获取用户状态
    if request.user.is_authenticated:
        return {"username": request.user.get_username(), "role": request.user.role}
    else:
        return {"username": "", "role": RoleChoices.NORMAL}


@router.get("/list", response=List[UserListSchema])
@super_required
@paginate
def list(request, username: str, role: str = None):
    # 用户列表
    users = User.objects.filter(username__icontains=username)
    if role:
        users = users.filter(role=role)
    return [UserListSchema.get(user) for user in users]


@router.post("/batch")
@super_required
@transaction.atomic
def batch_create(request, payload: BatchUsersIn):
    prefix = "web"
    usernames = []
    users_to_create = []

    # 生成用户名列表
    for name in payload.names:
        username = prefix + payload.classname + name
        usernames.append(username)

    # 检查是否存在重复用户名
    existing_users = User.objects.filter(username__in=usernames)
    if existing_users.exists():
        raise HttpError(400, "有些用户已经存在，创建失败")

    # 批量创建用户
    for username in usernames:
        password = generate_password()
        user = User(username=username)
        user.set_password(password)
        users_to_create.append(user)

    # 使用 bulk_create 批量保存
    User.objects.bulk_create(users_to_create, ignore_conflicts=True)

    # 返回创建的用户信息
    return {"message": "批量创建成功"}


@router.put("/active/{id}")
@super_required
def toggle_user_is_active(request, id: int):
    # 封号和解封
    try:
        user = User.objects.get(id=id)
        user.is_active = not user.is_active
        user.save()
        return {
            "message": f"{user.username} {'解封' if user.is_active else '封号'}成功"
        }
    except User.DoesNotExist:
        raise HttpError(404, "查无此人")
