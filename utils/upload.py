from ninja import Router, File
from ninja.files import UploadedFile
from pathlib import Path
from django.conf import settings
import uuid
from account.decorators import super_required

router = Router()


@router.post("")
@super_required
def upload_to_media(request, image: File[UploadedFile]):
    # 生成唯一的文件名
    ext = Path(image.name).suffix
    filename = f"{uuid.uuid4()}{ext}"

    # 确保 media 目录存在
    media_root = Path(settings.MEDIA_ROOT)
    media_root.mkdir(exist_ok=True)

    # 保存文件
    file_path = media_root / filename
    with open(file_path, "wb+") as f:
        for chunk in image.chunks():
            f.write(chunk)

    # 返回文件URL
    return {"url": f"{settings.MEDIA_URL}{filename}"}
