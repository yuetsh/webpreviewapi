import uuid
from django.db import models
from django.db.models import Avg
from django_extensions.db.models import TimeStampedModel
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver  # 导入receiver

from account.models import RoleChoices, User
from task.models import Task


class FlagChoices(models.TextChoices):
    RED = "red", "值得展示"
    BLUE = "blue", "需要讲解"
    GREEN = "green", "优秀作品"
    YELLOW = "yellow", "需要改进"


class ZoneChoices(models.TextChoices):
    FEATURED = "featured", "精选"
    LOW = "low", "待改进"
    PENDING = "pending", "待评"


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
    flag = models.CharField(
        max_length=10,
        choices=FlagChoices.choices,
        null=True,
        blank=True,
        default=None,
        db_index=True,
        verbose_name="标记",
    )
    raw_score = models.FloatField(default=0.0, verbose_name="原始加权分")
    zone = models.CharField(
        max_length=10,
        choices=ZoneChoices.choices,
        null=True,
        blank=True,
        default=None,
        db_index=True,
        verbose_name="分区",
    )
    view_count = models.PositiveIntegerField(default=0, verbose_name="查看次数")

    class Meta:
        ordering = ("-created",)

    def __str__(self):
        return f"{self.user.username} - {self.task.title}"

    def get_task_type(self):
        """
        返回任务的具体类型（Challenge 或 Tutorial）
        """
        return self.task.task_type

    def _update_zone(self, n: int):
        if n < 5:
            new_zone = ZoneChoices.PENDING
        elif self.score >= 4.0:
            new_zone = ZoneChoices.FEATURED
        elif self.score < 3.0:
            new_zone = ZoneChoices.LOW
        else:
            new_zone = None
        if self.zone != new_zone:
            self.zone = new_zone
            self.save(update_fields=["zone"])

    def update_score(self):
        ratings = list(self.ratings.select_related("user").all())
        n = len(ratings)

        if n == 0:
            self.raw_score = 0.0
            self.score = 0.0
            self.save(update_fields=["raw_score", "score"])
            self._update_zone(n)
            return

        role_weights = [
            0.5 if r.user.role == RoleChoices.SUPER
            else 0.3 if r.user.role == RoleChoices.ADMIN
            else 0.2
            for r in ratings
        ]
        weighted_sum = sum(r.score * w for r, w in zip(ratings, role_weights))
        weight_total = sum(role_weights)
        self.raw_score = weighted_sum / weight_total

        C = 3
        global_mean = (
            Submission.objects.filter(raw_score__gt=0)
            .exclude(pk=self.pk)
            .aggregate(Avg("raw_score"))["raw_score__avg"]
        ) or self.raw_score

        self.score = (C * global_mean + n * self.raw_score) / (C + n)
        self.save(update_fields=["raw_score", "score"])
        self._update_zone(n)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)


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


class ItemOrdering(models.TextChoices):
    MANUAL = "manual", "手动排序"
    AWARDED_AT = "awarded_at", "授奖时间倒序"
    SCORE = "score", "评分倒序"
    VIEW_COUNT = "view_count", "浏览量倒序"


class Award(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True, verbose_name="奖项名称")
    description = models.TextField(blank=True, default="", verbose_name="奖项简介")
    sort_order = models.IntegerField(default=0, db_index=True, verbose_name="排序值")
    is_active = models.BooleanField(default=True, verbose_name="是否启用")
    item_ordering = models.CharField(
        max_length=20,
        choices=ItemOrdering.choices,
        default=ItemOrdering.MANUAL,
        verbose_name="作品排序方式",
    )

    class Meta:
        ordering = ("sort_order",)

    def __str__(self):
        return self.name


class SubmissionAward(TimeStampedModel):
    submission = models.ForeignKey(
        Submission, on_delete=models.CASCADE, related_name="awards"
    )
    award = models.ForeignKey(
        Award, on_delete=models.CASCADE, related_name="submission_awards"
    )
    sort_order = models.IntegerField(default=0, db_index=True, verbose_name="手动排序值")
    awarded_at = models.DateTimeField(
        auto_now_add=True, db_index=True, verbose_name="授奖时间"
    )

    class Meta:
        unique_together = ("submission", "award")
        ordering = ("sort_order",)

    def __str__(self):
        return f"{self.award.name} - {self.submission}"
