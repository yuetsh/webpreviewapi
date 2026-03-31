from typing import List
from ninja import Router
from django.shortcuts import get_object_or_404
from account.decorators import super_required
from .schemas import ChallengeAll, ChallengeIn, ChallengeSlim
from .models import Challenge

router = Router()


@router.get("/list", response=List[ChallengeSlim])
@super_required
def challenge(request):
    """
    后台显示所有的列表
    """
    return Challenge.objects.all()


@router.get("/display", response=List[ChallengeSlim])
def get_all_public_display(request):
    """
    前台显示所有公开的挑战
    """
    return Challenge.objects.filter(is_public=True).order_by("-display")


@router.get("/{display}", response=ChallengeAll)
def get(request, display: int):
    return get_object_or_404(Challenge, display=display)


@router.post("/")
@super_required
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
@super_required
def remove(request, display: int):
    Challenge.objects.filter(display=display).delete()
    return {"message": "删除成功"}
