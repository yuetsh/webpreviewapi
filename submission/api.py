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
    RatingScoreIn,
)


from .models import Rating, Submission
from task.models import Task
from account.models import User

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
@login_required
def list_submissions(request, filters: SubmissionFilter = Query(...)):
    """
    获取提交列表，支持按任务和用户过滤
    """
    submissions = Submission.objects.all()

    if filters.task_id:
        task = get_object_or_404(Task, id=filters.task_id)
        submissions = submissions.select_related("task").filter(task=task)
    if filters.task_type:
        tasks = Task.objects.filter(task_type=filters.task_type)
        submissions = submissions.select_related("task").filter(task__in=tasks)
    if filters.username:
        users = User.objects.filter(username__icontains=filters.username)
        submissions = submissions.select_related("user").filter(user__in=users)

    ratings = Rating.objects.select_related("user", "submission").filter(
        user=request.user, submission__in=submissions
    )
    rating_dict = {rating.submission_id: rating.score for rating in ratings}
    return [SubmissionOut.list(submission, rating_dict) for submission in submissions]


@router.get("/{submission_id}", response=SubmissionOut)
@login_required
def get_submission(request, submission_id: UUID):
    """
    获取单个提交的详细信息
    """
    submission = get_object_or_404(Submission, id=submission_id)
    rating = (
        Rating.objects.select_related("user", "submission")
        .filter(user=request.user, submission=submission)
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
