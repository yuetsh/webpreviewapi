from typing import List
from uuid import UUID
from ninja import Router, Query
from ninja.errors import HttpError
from ninja.pagination import paginate
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Count, OuterRef, Q, Subquery, IntegerField


from .schemas import (
    FlagIn,
    MyScoreOut,
    SubmissionFilter,
    SubmissionIn,
    SubmissionOut,
    RatingScoreIn,
)


from .models import Rating, Submission
from task.models import Task
from account.models import RoleChoices

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
    # 如果用户之前已参与排名，自动转移提名到新提交
    had_nomination = Submission.objects.filter(
        user=request.user, task=task, nominated=True
    ).update(nominated=False) > 0

    Submission.objects.create(
        user=request.user,
        task=task,
        html=payload.html,
        css=payload.css,
        js=payload.js,
        conversation=conversation,
        nominated=had_nomination,
    )


@router.get("/", response=List[SubmissionOut])
@paginate
@login_required
def list_submissions(request, filters: SubmissionFilter = Query(...)):
    """
    获取提交列表，支持按任务和用户过滤
    """
    submissions = Submission.objects.select_related("task", "user").defer(
        "html", "css", "js"
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

    if filters.nominated is not None:
        submissions = submissions.filter(nominated=filters.nominated)
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


@router.get("/my-scores", response=List[MyScoreOut])
@login_required
def my_scores(request):
    seen = {}
    for s in Submission.objects.filter(
        user=request.user, task__task_type="challenge"
    ).order_by("-score").select_related("task"):
        if s.task_id not in seen:
            seen[s.task_id] = s
    return [
        MyScoreOut(
            task_id=s.task_id,
            task_display=s.task.display,
            task_title=s.task.title,
            score=s.score,
            created=s.created.isoformat(),
        )
        for s in seen.values()
    ]



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


@router.put("/{submission_id}/nominate")
@login_required
def nominate_submission(request, submission_id: UUID):
    """
    学生将某条提交标记为"参与排名"。
    同一用户同一题目只能有一条参与排名，旧的自动取消。
    """
    submission = get_object_or_404(Submission, id=submission_id)

    if submission.user != request.user:
        raise HttpError(403, "只能提名自己的提交")

    Submission.objects.filter(
        user=request.user,
        task=submission.task,
        nominated=True,
    ).exclude(pk=submission.pk).update(nominated=False)

    submission.nominated = True
    submission.save(update_fields=["nominated"])

    return {"nominated": True}
