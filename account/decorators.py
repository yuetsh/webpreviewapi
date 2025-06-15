from ninja import NinjaAPI
from functools import wraps
from typing import Callable, List, Any
from django.http import HttpRequest
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import User, RoleChoices

api = NinjaAPI()


def _require(roles: List[RoleChoices]) -> Callable:
    def check_role(user: User) -> bool:
        return user.is_authenticated and hasattr(user, "role") and user.role in roles

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        @login_required
        @user_passes_test(check_role, login_url=None)
        def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> Any:
            return func(request, *args, **kwargs)

        return wrapper

    return decorator


admin_required = _require([RoleChoices.ADMIN, RoleChoices.SUPER])
super_required = _require([RoleChoices.SUPER])
