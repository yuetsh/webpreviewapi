import uuid
from django.db import models
from django_extensions.db.models import TimeStampedModel

from account.models import Profile, User
from task.models import Task


class Submission(TimeStampedModel):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="my_submissions",
    )
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    score = models.IntegerField(default=0, verbose_name="分数")
    referee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="referee_submissions",
        verbose_name="打分人",
    )
    html = models.TextField(null=True, blank=True, verbose_name="HTML代码")
    css = models.TextField(null=True, blank=True, verbose_name="CSS代码")
    js = models.TextField(null=True, blank=True, verbose_name="JS代码")

    class Meta:
        ordering = ("-created",)

    def __str__(self):
        return f"{self.user.username} - {self.task.title}"

    def get_task_type(self):
        """
        返回任务的具体类型（Challenge 或 Tutorial）
        """
        return self.task.task_type

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.score > 0:
            self.user.profile.update_total_score(self.score)
