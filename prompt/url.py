from django.urls import path
from .consumers import PromptConsumer

websocket_urlpatterns = [
    path("ws/prompt/<int:task_id>/", PromptConsumer.as_asgi()),
]
