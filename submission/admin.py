from django.contrib import admin

from .models import Award, SubmissionAward


@admin.register(Award)
class AwardAdmin(admin.ModelAdmin):
    list_display = ("name", "sort_order", "is_active", "item_ordering", "created")
    list_filter = ("is_active", "item_ordering")
    search_fields = ("name",)
    ordering = ("sort_order",)


@admin.register(SubmissionAward)
class SubmissionAwardAdmin(admin.ModelAdmin):
    list_display = (
        "award_name",
        "submission_username",
        "submission_task_title",
        "submission_score",
        "submission_view_count",
        "sort_order",
        "awarded_at",
    )
    list_filter = ("award", "submission__task", "submission__user__classname")
    search_fields = (
        "award__name",
        "submission__user__username",
        "submission__task__title",
    )
    raw_id_fields = ("submission",)

    @admin.display(description="奖项")
    def award_name(self, obj):
        return obj.award.name

    @admin.display(description="提交作者")
    def submission_username(self, obj):
        return obj.submission.user.username

    @admin.display(description="挑战标题")
    def submission_task_title(self, obj):
        return obj.submission.task.title

    @admin.display(description="评分")
    def submission_score(self, obj):
        return obj.submission.score

    @admin.display(description="浏览量")
    def submission_view_count(self, obj):
        return obj.submission.view_count
