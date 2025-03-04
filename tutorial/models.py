from django.db import models
from django_extensions.db.models import TimeStampedModel


class Tutorial(TimeStampedModel):
    display = models.IntegerField(unique=True)
    title = models.CharField(max_length=100)
    content = models.TextField()
    is_public = models.BooleanField(default=False)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ("display",)
        verbose_name = "教程"
        verbose_name_plural = verbose_name
