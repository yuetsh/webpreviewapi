from django.db import models
from django.db.models import Sum
from django.db.models.signals import post_save
from django.dispatch import receiver
from django_extensions.db.models import TimeStampedModel

from account.models import Profile, User
from task.models import Task


class Submission(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    score = models.IntegerField(default=0)
    html = models.TextField(null=True, blank=True)
    css = models.TextField(null=True, blank=True)
    js = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.task.title}"

    def get_task_type(self):
        """
        返回任务的具体类型（Challenge 或 Tutorial）
        """
        return self.task.task_type

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.user.profile.update_total_score()


# 信号处理函数
@receiver(post_save, sender=Submission)
def update_user_score(sender, instance, **kwargs):
    """
    当 Submission 保存后，自动更新用户的总分
    """
    total_score = (
        Submission.objects.filter(user=instance.user).aggregate(
            total_score=Sum("score")
        )["total_score"]
        or 0
    )
    profile, created = Profile.objects.get_or_create(user=instance.user)
    profile.total_score = total_score
    profile.save()
