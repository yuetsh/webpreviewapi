import uuid
from django.db import models
from django_extensions.db.models import TimeStampedModel
from account.models import User
from task.models import Task


class Conversation(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="conversations")
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="conversations")
    is_active = models.BooleanField(default=True, verbose_name="是否活跃")

    class Meta:
        ordering = ("-created",)

    def __str__(self):
        return f"{self.user.username} - {self.task.title}"


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=10)  # "user" or "assistant"
    source = models.CharField(max_length=12, default="conversation")  # "conversation" or "manual"
    content = models.TextField()
    code_html = models.TextField(null=True, blank=True)
    code_css = models.TextField(null=True, blank=True)
    code_js = models.TextField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    prompt_level = models.IntegerField(
        null=True, blank=True, default=None, db_index=True, verbose_name="提示词层级"
    )

    class Meta:
        ordering = ("created",)

    def __str__(self):
        return f"[{self.role}] {self.content[:50]}"
