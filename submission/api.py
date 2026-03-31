import threading
from typing import List, Optional
from uuid import UUID
from ninja import Router, Query
from ninja.errors import HttpError
from ninja.pagination import paginate
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, F, IntegerField, Max, OuterRef, Q, Subquery


from .schemas import (
    FlagIn,
    FlagStats,
    SubmissionCountBucket,
    SubmissionFilter,
    SubmissionIn,
    SubmissionOut,
    RatingScoreIn,
    TaskStatsOut,
    UserTag,
)


from .models import Rating, Submission
from task.models import Task
from account.models import RoleChoices, User

router = Router()


@router.post("/")
@login_required
def create_submission(request, payload: SubmissionIn):
    """
    创建一个新的提交
    """
    task = get_object_or_404(Task, id=payload.task_id)
    conversation = None
    if payload.conversation_id:
        from prompt.models import Conversation
        conversation = get_object_or_404(
            Conversation, id=payload.conversation_id, user=request.user
        )
        conversation.is_active = False
        conversation.save(update_fields=["is_active"])

    sub = Submission.objects.create(
        user=request.user,
        task=task,
        html=payload.html,
        css=payload.css,
        js=payload.js,
        conversation=conversation,
    )

    if conversation:
        from .classifier import classify_conversation_messages
        threading.Thread(target=classify_conversation_messages, args=(conversation.id,), daemon=True).start()


@router.get("/", response=List[SubmissionOut])
@paginate
@login_required
def list_submissions(request, filters: SubmissionFilter = Query(...)):
    """
    获取提交列表，支持按任务和用户过滤
    """
    submissions = (
        Submission.objects.select_related("task", "user")
        .defer("html", "css", "js")
        .exclude(conversation__isnull=False, html__isnull=True, css__isnull=True, js__isnull=True)
    )

    if filters.task_id:
        task = get_object_or_404(Task, id=filters.task_id)
        submissions = submissions.filter(task=task)
    elif filters.task_type:
        submissions = submissions.filter(task__task_type=filters.task_type)
    if filters.username:
        submissions = submissions.filter(user__username__icontains=filters.username)
    if filters.user_id:
        submissions = submissions.filter(user_id=filters.user_id)
    if filters.flag:
        if filters.flag == "any":
            submissions = submissions.filter(flag__isnull=False)
        else:
            submissions = submissions.filter(flag=filters.flag)
    if filters.zone:
        submissions = submissions.filter(zone=filters.zone)

    if filters.score_lt_threshold is not None:
        submissions = submissions.filter(score__lt=filters.score_lt_threshold)
    else:
        if filters.score_min is not None:
            submissions = submissions.filter(score__gte=filters.score_min)
        if filters.score_max_exclusive is not None:
            submissions = submissions.filter(score__lt=filters.score_max_exclusive)
    if filters.ordering in ("-score", "score", "-created"):
        submissions = submissions.order_by(filters.ordering)

    if filters.grouped:
        # 分组模式：每个 (user, task) 只保留最新一条
        latest_per_group = (
            Submission.objects.filter(user=OuterRef("user"), task=OuterRef("task"))
            .order_by("-created")
            .values("pk")[:1]
        )
        submissions = submissions.filter(pk=Subquery(latest_per_group))

    user_rating_subquery = Subquery(
        Rating.objects.filter(user=request.user, submission=OuterRef("pk")).values(
            "score"
        )[:1],
        output_field=IntegerField(),
    )
    submissions = submissions.annotate(my_score=user_rating_subquery)

    # 同一用户同一任务的提交次数
    submit_count_subquery = Subquery(
        Submission.objects.filter(
            user=OuterRef("user"), task=OuterRef("task")
        ).values("user", "task").annotate(c=Count("id")).values("c")[:1],
        output_field=IntegerField(),
    )
    submissions = submissions.annotate(submit_count=submit_count_subquery)

    return submissions



@router.get("/by-user-task", response=List[SubmissionOut])
@login_required
def list_by_user_task(request, user_id: int, task_id: int):
    """
    获取某用户某任务的所有提交（不分页）
    """
    user_rating_subquery = Subquery(
        Rating.objects.filter(user=request.user, submission=OuterRef("pk")).values(
            "score"
        )[:1],
        output_field=IntegerField(),
    )
    return (
        Submission.objects.filter(user_id=user_id, task_id=task_id)
        .exclude(conversation__isnull=False, html__isnull=True, css__isnull=True, js__isnull=True)
        .select_related("task", "user")
        .defer("html", "css", "js")
        .annotate(my_score=user_rating_subquery)
        .order_by("-created")
    )


@router.delete("/flags")
@login_required
def clear_all_flags(request):
    """
    清除所有提交的标记（仅管理员和超级管理员可操作）
    """
    if request.user.role not in (RoleChoices.SUPER, RoleChoices.ADMIN):
        raise HttpError(403, "没有权限")

    count = Submission.objects.filter(flag__isnull=False).update(flag=None)
    return {"cleared": count}


@router.delete("/{submission_id}")
@login_required
def delete_submission(request, submission_id: UUID):
    submission = get_object_or_404(Submission, id=submission_id)
    if submission.user != request.user:
        raise HttpError(403, "只能删除自己的提交")
    submission.delete()
    return {"message": "删除成功"}


@router.get("/stats/{task_id}", response=TaskStatsOut)
@login_required
def get_task_stats(request, task_id: int, classname: Optional[str] = None):
    """
    获取某个挑战任务的班级提交统计数据（仅管理员）
    """
    if request.user.role not in (RoleChoices.SUPER, RoleChoices.ADMIN):
        raise HttpError(403, "没有权限")

    task = get_object_or_404(Task, id=task_id)

    # All distinct classnames (unfiltered, for filter buttons in UI)
    all_classes = list(
        User.objects.filter(role=RoleChoices.NORMAL)
        .exclude(classname="")
        .values_list("classname", flat=True)
        .distinct()
        .order_by("classname")
    )

    # Student universe: Normal users, optionally filtered by classname
    students = User.objects.filter(role=RoleChoices.NORMAL)
    if classname:
        students = students.filter(classname=classname)

    student_ids = list(students.values_list("id", flat=True))
    total_students = len(student_ids)

    # Submitted student IDs
    submitted_ids = set(
        Submission.objects.filter(task=task, user_id__in=student_ids)
        .values_list("user_id", flat=True)
        .distinct()
    )
    submitted_count = len(submitted_ids)
    unsubmitted_count = total_students - submitted_count

    # Unsubmitted users
    unsubmitted_users = [
        UserTag(username=u.username, classname=u.classname)
        for u in students.exclude(id__in=submitted_ids).order_by("classname", "username")
    ]

    # Latest submission per submitted user (SQLite-compatible).
    # Find each user's max created timestamp, then resolve all matching IDs
    # in a single query using OR'd Q objects instead of one query per user.
    latest_per_user = list(
        Submission.objects.filter(task=task, user_id__in=submitted_ids)
        .values("user_id")
        .annotate(max_created=Max("created"))
    )
    latest_sub_ids = []
    if latest_per_user:
        user_time_filter = Q()
        for row in latest_per_user:
            user_time_filter |= Q(user_id=row["user_id"], created=row["max_created"])
        # Fetch all matching submissions in one query; deduplicate by user_id
        seen_users: set = set()
        for sub_id, uid in (
            Submission.objects.filter(user_time_filter, task=task)
            .values_list("id", "user_id")
        ):
            if uid not in seen_users:
                seen_users.add(uid)
                latest_sub_ids.append(sub_id)
    latest_subs = list(Submission.objects.filter(id__in=latest_sub_ids))

    # Average score from latest submissions (None if no submissions have score > 0)
    avg_result = (
        Submission.objects.filter(id__in=latest_sub_ids, score__gt=0)
        .aggregate(avg=Avg("score"))["avg"]
    )
    average_score = round(avg_result, 2) if avg_result is not None else None

    # Unrated: submitted but no Rating on any of their submissions for this task
    rated_ids = set(
        Rating.objects.filter(
            submission__task=task, submission__user_id__in=submitted_ids
        )
        .values_list("submission__user_id", flat=True)
        .distinct()
    )
    unrated_ids = submitted_ids - rated_ids
    unrated_count = len(unrated_ids)
    unrated_users = [
        UserTag(username=u.username, classname=u.classname)
        for u in students.filter(id__in=unrated_ids).order_by("classname", "username")
    ]

    # Submission count distribution
    sub_counts = dict(
        Submission.objects.filter(task=task, user_id__in=submitted_ids)
        .values("user_id")
        .annotate(c=Count("id"))
        .values_list("user_id", "c")
    )
    dist = {"count_1": 0, "count_2": 0, "count_3": 0, "count_4_plus": 0}
    for c in sub_counts.values():
        if c == 1:
            dist["count_1"] += 1
        elif c == 2:
            dist["count_2"] += 1
        elif c == 3:
            dist["count_3"] += 1
        else:
            dist["count_4_plus"] += 1

    # Flag stats (all submissions for this task, not grouped by user)
    flag_counts = dict(
        Submission.objects.filter(task=task, flag__isnull=False)
        .values("flag")
        .annotate(c=Count("id"))
        .values_list("flag", "c")
    )
    flag_stats = FlagStats(
        red=flag_counts.get("red", 0),
        blue=flag_counts.get("blue", 0),
        green=flag_counts.get("green", 0),
        yellow=flag_counts.get("yellow", 0),
    )

    return TaskStatsOut(
        submitted_count=submitted_count,
        unsubmitted_count=unsubmitted_count,
        average_score=average_score,
        unrated_count=unrated_count,
        unsubmitted_users=unsubmitted_users,
        unrated_users=unrated_users,
        submission_count_distribution=SubmissionCountBucket(**dist),
        flag_stats=flag_stats,
        classes=all_classes,
    )


@router.get("/{submission_id}", response=SubmissionOut)
@login_required
def get_submission(request, submission_id: UUID):
    """
    获取单个提交的详细信息
    """
    user_rating_subquery = Subquery(
        Rating.objects.filter(user=request.user, submission=OuterRef("pk")).values(
            "score"
        )[:1],
        output_field=IntegerField(),
    )
    submission = get_object_or_404(
        Submission.objects.select_related("task", "user").annotate(
            my_score=user_rating_subquery
        ),
        id=submission_id,
    )
    return submission


@router.post("/{submission_id}/view")
@login_required
def increment_view(request, submission_id: UUID):
    """
    增加提交的浏览次数（仅在全屏预览时调用）
    """
    updated = Submission.objects.filter(pk=submission_id).update(
        view_count=F("view_count") + 1
    )
    if not updated:
        raise HttpError(404, "提交不存在")
    return {"ok": True}


@router.put("/{submission_id}/score")
@login_required
def update_score(request, submission_id: UUID, payload: RatingScoreIn):
    """
    给提交打分
    """
    if payload.score <= 0:
        raise HttpError(400, "分数不能为零")

    submission = get_object_or_404(Submission, id=submission_id)

    _, created = Rating.objects.get_or_create(
        user=request.user,
        submission=submission,
        defaults={"score": payload.score},
    )

    if created:
        return {"message": "打分成功"}
    else:
        return {"message": "你已经给这个提交打过分了"}


@router.put("/{submission_id}/flag")
@login_required
def update_flag(request, submission_id: UUID, payload: FlagIn):
    """
    设置或清除提交的标记（仅管理员和超级管理员可操作）
    """
    if request.user.role not in (RoleChoices.SUPER, RoleChoices.ADMIN):
        raise HttpError(403, "没有权限")

    submission = get_object_or_404(Submission, id=submission_id)
    submission.flag = payload.flag
    submission.save(update_fields=["flag"])
    return {"flag": submission.flag}




