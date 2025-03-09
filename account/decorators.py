from ninja.errors import HttpError
from ninja import NinjaAPI
from functools import wraps
from .models import User, RoleChoices

api = NinjaAPI()


def _require(roles):
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return HttpError(401, "用户未登录")
            try:
                if request.user.role not in roles:
                    return HttpError(403, "你没有权限")
            except User.DoesNotExist:
                return HttpError(404, "用户不存在")
            return func(request, *args, **kwargs)

        return wrapper

    return decorator

admin_required =  _require([RoleChoices.ADMIN, RoleChoices.SUPER])

super_required = _require([RoleChoices.SUPER])
