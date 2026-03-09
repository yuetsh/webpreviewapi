from typing import List
from uuid import UUID
from ninja import Router, Query
from ninja.errors import HttpError
from ninja.pagination import paginate
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import OuterRef, Subquery, IntegerField


from .schemas import (
    FlagIn,
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
    Submission.objects.create(
        user=request.user,
        task=task,
        html=payload.html,
        css=payload.css,
        js=payload.js,
        conversation=conversation,
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
    if filters.flag:
        submissions = submissions.filter(flag=filters.flag)

    user_rating_subquery = Subquery(
        Rating.objects.filter(user=request.user, submission=OuterRef("pk")).values(
            "score"
        )[:1],
        output_field=IntegerField(),
    )
    submissions = submissions.annotate(my_score=user_rating_subquery)

    return submissions


@router.get("/{submission_id}", response=SubmissionOut)
@login_required
def get_submission(request, submission_id: UUID):
    """
    获取单个提交的详细信息
    """
    submission = get_object_or_404(
        Submission.objects.select_related("task", "user"), id=submission_id
    )
    rating = (
        Rating.objects.filter(user=request.user, submission=submission)
        .first()
    )
    return SubmissionOut.get(submission, rating)


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
