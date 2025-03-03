from django.db import models

from django.contrib.auth.models import AbstractUser


class RoleChoices(models.TextChoices):
    SUPER = "sup    er", "超级管理员"
    ADMIN = "admin", "管理员"
    NORMAL = "normal", "普通"


class User(AbstractUser):
    role = models.CharField(
        max_length=20,
        choices=RoleChoices.choices,
        default=RoleChoices.NORMAL,
    )
