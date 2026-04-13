from ninja import Router, File, Form, Schema
from ninja.files import UploadedFile
from django.shortcuts import get_object_or_404
from django.conf import settings
from account.decorators import admin_required, super_required
from .models import Challenge, Tutorial, TaskAsset

router = Router()


class AssetOut(Schema):
    name: str
    url: str


def _asset_url(asset: TaskAsset) -> str:
    return f"{settings.MEDIA_URL}{asset.file.name}"


# ── Challenge assets ──────────────────────────────────────────────────────────

@router.get("/challenge/{display}", response=list[AssetOut])
def list_challenge_assets(request, display: int):
    challenge = get_object_or_404(Challenge, display=display)
    return [AssetOut(name=a.name, url=_asset_url(a)) for a in challenge.assets.all()]


@router.post("/challenge/{display}", response=AssetOut)
@admin_required
def upload_challenge_asset(request, display: int, name: Form[str], file: File[UploadedFile]):
    challenge = get_object_or_404(Challenge, display=display)
    asset, _ = TaskAsset.objects.get_or_create(task=challenge.task_ptr, name=name)
    if asset.file:
        asset.file.delete(save=False)
    asset.file.save(name, file, save=True)
    return AssetOut(name=asset.name, url=_asset_url(asset))


@router.delete("/challenge/{display}/{name}")
@admin_required
def delete_challenge_asset(request, display: int, name: str):
    challenge = get_object_or_404(Challenge, display=display)
    asset = get_object_or_404(TaskAsset, task=challenge.task_ptr, name=name)
    asset.file.delete(save=False)
    asset.delete()
    return {"message": "删除成功"}


# ── Tutorial assets ───────────────────────────────────────────────────────────

@router.get("/tutorial/{display}", response=list[AssetOut])
def list_tutorial_assets(request, display: int):
    tutorial = get_object_or_404(Tutorial, display=display)
    return [AssetOut(name=a.name, url=_asset_url(a)) for a in tutorial.assets.all()]


@router.post("/tutorial/{display}", response=AssetOut)
@super_required
def upload_tutorial_asset(request, display: int, name: Form[str], file: File[UploadedFile]):
    tutorial = get_object_or_404(Tutorial, display=display)
    asset, _ = TaskAsset.objects.get_or_create(task=tutorial.task_ptr, name=name)
    if asset.file:
        asset.file.delete(save=False)
    asset.file.save(name, file, save=True)
    return AssetOut(name=asset.name, url=_asset_url(asset))


@router.delete("/tutorial/{display}/{name}")
@super_required
def delete_tutorial_asset(request, display: int, name: str):
    tutorial = get_object_or_404(Tutorial, display=display)
    asset = get_object_or_404(TaskAsset, task=tutorial.task_ptr, name=name)
    asset.file.delete(save=False)
    asset.delete()
    return {"message": "删除成功"}
