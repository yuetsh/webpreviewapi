from typing import List
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from ninja import Router
from ninja.errors import HttpError
from .schemas import UserListSchema, UserRegistrationSchema, UserLoginSchema
from .models import RoleChoices, User
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
def list(request, username: str):
    # 之后加上分页
    users = User.objects.filter(username__icontains=username)
    return [UserListSchema.from_orm(user) for user in users]


@router.post("/batch")
@super_required
def batch_create(request):
    # 批量创建账号
    pass
