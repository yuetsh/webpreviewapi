from django.contrib.auth import authenticate, login, logout
from ninja import Router
from ninja.errors import HttpError
from .schemas import UserRegistrationSchema, UserLoginSchema
from .models import User

router = Router()


@router.post("/register")
def user_register(request, payload: UserRegistrationSchema):
    if User.objects.filter(username=payload.username).exists():
        raise HttpError(400, "Username already exists")
    User.objects.create_user(
        username=payload.username,
        email=payload.email,
        password=payload.password,
    )
    return {"message": "User created successfully"}


@router.post("/login")
def user_login(request, payload: UserLoginSchema):
    user = authenticate(username=payload.username, password=payload.password)
    if user is not None:
        login(request, user)
        return request.user.get_username()
    else:
        raise HttpError(401, "Invalid credentials")


@router.post("/logout")
def user_logout(request):
    logout(request)


@router.get("/profile")
def current_user_profile(request):
    # 暂时这样写
    return request.user.get_username()
