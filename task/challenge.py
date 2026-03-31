from typing import List
from ninja import Router
from django.shortcuts import get_object_or_404
from account.decorators import admin_required, super_required
from submission.models import Submission
from .schemas import ChallengeAll, ChallengeDisplay, ChallengeIn, ChallengeSlim
from .models import Challenge

router = Router()


@router.get("/list", response=List[ChallengeSlim])
@admin_required
def challenge(request):
    """
    后台显示所有的列表
    """
    return Challenge.objects.all()


@router.get("/display", response=List[ChallengeDisplay])
def get_all_public_display(request):
    """
    前台显示所有公开的挑战
    """
    challenges = list(Challenge.objects.filter(is_public=True).order_by("-display"))
    if request.user.is_authenticated:
        task_ids = [c.task_ptr_id for c in challenges]
        submitted_ids = set(
            Submission.objects.filter(
                user=request.user,
                task_id__in=task_ids,
            ).values_list("task_id", flat=True)
        )
    else:
        submitted_ids = set()
    return [
        ChallengeDisplay(
            display=c.display,
            title=c.title,
            score=c.score,
            pass_score=c.pass_score,
            is_public=c.is_public,
            submitted=c.task_ptr_id in submitted_ids,
        )
        for c in challenges
    ]


@router.get("/{display}", response=ChallengeAll)
def get(request, display: int):
    return get_object_or_404(Challenge, display=display)


@router.post("/")
@admin_required
def create_or_update(request, payload: ChallengeIn):
    try:
        item = Challenge.objects.get(display=payload.display)
        item.title = payload.title
        item.content = payload.content
        item.score = payload.score
        item.is_public = payload.is_public
        item.save()
        return {"message": "更新成功"}
    except Challenge.DoesNotExist:
        Challenge.objects.create(**payload.dict())
        return {"message": "创建成功"}


@router.put("/public/{display}")
@super_required
def toggle_public(request, display: int):
    item = get_object_or_404(Challenge, display=display)
    item.is_public = not item.is_public
    item.save()
    label = "公开" if item.is_public else "隐藏"
    return {"message": f"【{item.display}】{item.title} 已{label}"}


@router.delete("/{display}")
@admin_required
def remove(request, display: int):
    Challenge.objects.filter(display=display).delete()
    return {"message": "删除成功"}
