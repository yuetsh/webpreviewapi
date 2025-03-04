from typing import List
from ninja import Router
from ninja.errors import HttpError
from account.decorators import super_required
from .schemas import TutorialAll, TutorialIn, TutorialReturn
from .models import Tutorial

router = Router()


@router.get("/", response=TutorialReturn)
@super_required
def tutorial(request):
    return {
        "list": Tutorial.objects.all(),
        "first": Tutorial.objects.first(),
    }


@router.get("/display", response=List[int])
def get_all_public_display(request):
    return Tutorial.objects.filter(is_public=True).values_list("display", flat=True)


@router.get("/{display}", response=TutorialAll)
def get(request, display: int):
    try:
        return Tutorial.objects.get(display=display)
    except Tutorial.DoesNotExist:
        raise HttpError(404, "此序号无教程")


@router.post("/")
@super_required
def create_or_update(request, payload: TutorialIn):
    try:
        item = Tutorial.objects.get(display=payload.display)
        item.title = payload.title
        item.content = payload.content
        item.is_public = payload.is_public
        item.save()
        return {"message": "更新成功"}
    except Tutorial.DoesNotExist:
        Tutorial.objects.create(**payload.dict())
        return {"message": "创建成功"}


@router.put("/public/{display}")
@super_required
def toggle_public(request, display: int):
    try:
        item = Tutorial.objects.get(display=display)
        item.is_public = not item.is_public
        item.save()
        label = "公开" if item.is_public else "隐藏"
        return {"message": f"【{item.display}】{item.title} 已{label}"}
    except Tutorial.DoesNotExist:
        raise HttpError(404, "此序号无教程")


@router.delete("/{display}")
@super_required
def remove(request, display: int):
    Tutorial.objects.filter(display=display).delete()
    return {"message": "删除成功"}
