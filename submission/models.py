import uuid
from django.db import models
from django_extensions.db.models import TimeStampedModel
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver  # 导入receiver

from account.models import Profile, RoleChoices, User
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
    score = models.FloatField(default=0.0, verbose_name="分数")
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

    def update_score(self):
        """
        更新当前Submission的分数
        """
        ratings = self.ratings.all()

        super_score = 0.0
        admin_score = 0.0
        normal_score = 0.0

        for rating in ratings:
            if rating.user.role == RoleChoices.SUPER:
                super_score += rating.score
            elif rating.user.role == RoleChoices.ADMIN:
                admin_score += rating.score
            else:
                normal_score += rating.score

        if ratings.exists():
            total_score = super_score * 0.5 + admin_score * 0.3 + normal_score * 0.2
            self.score = total_score / ratings.count()
        else:
            self.score = 0.0

        self.save()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # if self.score > 0:
        #     self.user.profile.update_total_score(self.score)


class Rating(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="ratings",
    )
    submission = models.ForeignKey(
        Submission,
        on_delete=models.CASCADE,
        related_name="ratings",
    )
    score = models.IntegerField(default=0, verbose_name="分数")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "submission")

    def __str__(self):
        return f"{self.user.username} 评分了 {self.submission.id}，分数是 {self.score}"

    def clean(self):
        """
        在保存之前检查用户当天的评分次数
        """
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timezone.timedelta(days=1)
        count = Rating.objects.filter(
            user=self.user, created__range=(today_start, today_end)
        ).count()

        if self.user.role == RoleChoices.NORMAL and count >= 30:
            raise ValidationError("普通用户每天最多只能评分30次。")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


@receiver(post_save, sender=Rating)
def update_submission_score_on_save(sender, instance, **kwargs):
    """
    当Rating保存时，更新对应的Submission的平均分
    """
    instance.submission.update_score()
