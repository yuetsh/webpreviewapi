from django.db import models
from django_extensions.db.models import TimeStampedModel


class Task(TimeStampedModel):
    TASK_TYPE_CHOICES = [
        ("challenge", "Challenge"),
        ("tutorial", "Tutorial"),
    ]

    display = models.IntegerField(unique=True, db_index=True, verbose_name="序号")
    title = models.CharField(max_length=100, verbose_name="标题")
    content = models.TextField(verbose_name="内容")
    task_type = models.CharField(
        max_length=20, choices=TASK_TYPE_CHOICES, editable=False, verbose_name="类型"
    )
    is_public = models.BooleanField(default=False, verbose_name="是否公开")

    def save(self, *args, **kwargs):
        if not self.task_type:
            self.task_type = self.__class__.__name__.lower()
        super().save(*args, **kwargs)


class Tutorial(Task):
    def __str__(self):
        return self.title

    class Meta:
        ordering = ("display",)
        verbose_name = "教程"
        verbose_name_plural = verbose_name


class Challenge(Task):
    score = models.IntegerField(default=0)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ("display",)
        verbose_name = "挑战"
        verbose_name_plural = verbose_name
