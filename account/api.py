import random
from typing import List
from django.db.models.signals import post_save
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
from .models import Profile, RoleChoices, User, create_user_profile
from .decorators import super_required

router = Router()


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
    return [UserListSchema.from_orm(user) for user in users]


@router.post("/batch")
@super_required
def batch_create(request, payload: BatchUsersIn):
    # 批量创建账号
    prefix = "web"
    user_list = []
    profile_list = []
    usernames = []

    for name in payload.names:
        username = prefix + payload.classname + name
        usernames.append(username)
        digits = [str(random.randint(2, 9)) for _ in range(6)]
        password = "".join(digits)
        user = User(username=username)
        user.set_password(password)
        user_list.append(user)

    for user in user_list:
        profile_list.append(Profile(user=user))

    post_save.disconnect(create_user_profile, sender=User)
    User.objects.bulk_create(user_list)
    post_save.connect(create_user_profile, sender=User)

    Profile.objects.bulk_create(profile_list)
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
