from typing import List
from uuid import UUID
from ninja import Router, Query
from ninja.errors import HttpError
from ninja.pagination import paginate
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required

from account.decorators import admin_required
from .schemas import (
    SubmissionFilter,
    SubmissionIn,
    SubmissionOut,
    SubmissionScoreIn,
    SubmissionScoreOut,
)


from .models import Submission
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

    Submission.objects.create(
        user=request.user,
        task=task,
        html=payload.html,
        css=payload.css,
        js=payload.js,
    )


@router.get("/", response=List[SubmissionOut])
@paginate
def list_submissions(request, filters: SubmissionFilter = Query(...)):
    """
    获取提交列表，支持按任务和用户过滤
    """
    queryset = Submission.objects.all()

    if filters.task_id:
        queryset = queryset.filter(task_id=filters.task_id)
    if filters.task_id:
        queryset = queryset.filter(task_task_type=filters.task_type)
    if filters.username:
        queryset = queryset.filter(user_username=filters.username)

    return [SubmissionOut.list(submission) for submission in queryset]


@router.get("/{submission_id}", response=SubmissionOut)
@login_required
def get_submission(request, submission_id: UUID):
    """
    获取单个提交的详细信息
    """
    # 如果是普通用户，只能查看自己的提交
    if request.user.role == RoleChoices.NORMAL:
        submission = get_object_or_404(Submission, id=submission_id, user=request.user)
    else:
        submission = get_object_or_404(Submission, id=submission_id)

    return SubmissionOut.get(submission)


@router.put("/{submission_id}/score", response=SubmissionScoreOut)
@admin_required
def update_score(request, submission_id: UUID, payload: SubmissionScoreIn):
    """
    给提交打分
    """
    if payload.score <= 0:
        raise HttpError(400, "分数不能为零")

    submission = get_object_or_404(Submission, id=submission_id)

    if submission.score > 0:
        raise HttpError(400, "该提交已经有分数了")
    if (
        request.user.role == RoleChoices.NORMAL
        and submission.user.id == request.user.id
    ):
        raise HttpError(400, "不能自己给自己打分")

    submission.score = payload.score
    submission.referee = request.user
    submission.save()

    return {
        "id": submission.id,
        "score": submission.score,
    }
