from collections.abc import Callable
from typing import Any, cast

from django.urls import path
from django.urls.resolvers import URLPattern, URLResolver

from .consumers import PromptConsumer, GuidanceConsumer

AsgiApplication = Callable[..., Any]
RoutePattern = URLPattern | URLResolver

websocket_urlpatterns: list[RoutePattern] = [
    path("ws/prompt/<int:task_id>/", cast(AsgiApplication, PromptConsumer.as_asgi())),
    path("ws/guidance/<int:task_id>/", cast(AsgiApplication, GuidanceConsumer.as_asgi())),
]
