from django.db import models
from django.contrib.auth.models import AbstractUser

from django.db.models.signals import post_save
from django.dispatch import receiver


class RoleChoices(models.TextChoices):
    SUPER = "super", "超级管理员"
    ADMIN = "admin", "管理员"
    NORMAL = "normal", "普通"


class User(AbstractUser):
    first_name = None
    last_name = None

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

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = RoleChoices.SUPER
        super().save(*args, **kwargs)

    def set_password(self, raw_password):
        super().set_password(raw_password)
        self.raw_password = raw_password
        self.save()

    class Meta:
        ordering = ("-id",)
        verbose_name = "用户"
        verbose_name_plural = verbose_name


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    total_score = models.IntegerField(default=0)

    def __str__(self):
        return self.user.username


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()
