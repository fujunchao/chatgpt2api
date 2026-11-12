"""按图片原始字节识别格式，统一保存后缀、响应 MIME 和静态能力判断。"""

from dataclasses import dataclass
from io import BytesIO

from PIL import Image


IMAGE_FORMATS = {
    "PNG": (".png", "image/png"),
    "JPEG": (".jpg", "image/jpeg"),
    "WEBP": (".webp", "image/webp"),
    "GIF": (".gif", "image/gif"),
}
STATIC_IMAGE_FORMATS = frozenset({"PNG", "JPEG", "WEBP"})


@dataclass(frozen=True)
class ImageInfo:
    format: str
    extension: str
    mime_type: str
    width: int
    height: int
    animated: bool

    @property
    def supported_static(self) -> bool:
        return self.format in STATIC_IMAGE_FORMATS and not self.animated


def inspect_image(payload: bytes, *, verify: bool = False) -> ImageInfo | None:
    """识别真实格式；兼容旧存储调用方的不完整数据，不推断未知内容类型。"""
    try:
        with Image.open(BytesIO(payload)) as image:
            image_format = str(image.format or "").upper()
            if image_format not in IMAGE_FORMATS:
                return None
            extension, mime = IMAGE_FORMATS[image_format]
            info = ImageInfo(
                image_format, extension, mime, image.width, image.height,
                bool(getattr(image, "is_animated", False)),
            )
            if verify:
                image.verify()
            return info
    except Exception:
        return None


def image_mime_type(payload: bytes) -> str:
    """对实际图片使用其 MIME；旧的不完整存储数据保留 PNG 后备值。"""
    info = inspect_image(payload)
    return info.mime_type if info is not None else "image/png"
