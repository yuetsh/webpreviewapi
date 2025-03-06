from django.db import models

from django.contrib.auth.models import AbstractUser


class RoleChoices(models.TextChoices):
    SUPER = "super", "超级管理员"
    ADMIN = "admin", "管理员"
    NORMAL = "normal", "普通"


class User(AbstractUser):
    role = models.CharField(
        max_length=20,
        choices=RoleChoices.choices,
        default=RoleChoices.NORMAL,
        verbose_name="权限",
    )
    raw_password = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name="明文密码",
    )

    def set_password(self, raw_password):
        super().set_password(raw_password)
        self.raw_password = raw_password
        self.save()
    
    class Meta:
        ordering = ("-id",)
