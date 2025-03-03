from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from ninja import Router
from ninja.errors import HttpError
from .schemas import UserRegistrationSchema, UserLoginSchema
from .models import RoleChoices, User

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
    # 暂时这样写
    if request.user.is_authenticated:
        return {"username": request.user.get_username(), "role": request.user.role}
    else:
        return {"username": "", "role": RoleChoices.NORMAL}
