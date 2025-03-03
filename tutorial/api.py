from ninja import Router
from ninja.errors import HttpError

from account.decorators import super_required

# from account.decorators import super_required
from .schemas import TutorialAll, TutorialIn, TutorialReturn
from .models import Tutorial

router = Router()


@router.get("/", response=TutorialReturn)
@super_required
def tutorial(request):
    return {
        "total": Tutorial.objects.count(),
        "list": Tutorial.objects.all(),
        "first": Tutorial.objects.first(),
    }


@router.get("/{display}", response=TutorialAll)
def get(request, display: str):
    return Tutorial.objects.get(display=display)


@router.post("/")
@super_required
def create(request, payload: TutorialIn):
    if Tutorial.objects.filter(display=payload.display):
        raise HttpError(400, "有序号相同的教程存在")
    Tutorial.objects.create(**payload.dict())
    return {"message": "创建成功"}


@router.delete("/{display}")
@super_required
def remove(request, display: str):
    Tutorial.objects.filter(display=display).delete()
    return {"message": "删除成功"}
