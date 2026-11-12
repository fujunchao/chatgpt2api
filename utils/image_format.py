"""按图片原始字节识别格式，统一后缀、媒体类型及动画完整性判断。"""

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
    frame_count: int = 1
    frame_durations_ms: tuple[int, ...] = ()
    loop: int | None = None

    @property
    def supported_static(self) -> bool:
        return self.format in STATIC_IMAGE_FORMATS and not self.animated

    @property
    def supported_animation(self) -> bool:
        return self.format == "GIF" and self.animated and self.frame_count >= 2

    @property
    def animation_metadata(self) -> dict[str, object]:
        if not self.supported_animation:
            return {}
        return {
            "format": "gif", "mime_type": self.mime_type, "animated": True,
            "frame_count": self.frame_count, "frame_durations_ms": list(self.frame_durations_ms),
            "duration_ms": sum(self.frame_durations_ms), "loop": self.loop,
        }


def inspect_image(payload: bytes, *, verify: bool = False) -> ImageInfo | None:
    """识别真实格式；兼容旧存储调用方的不完整数据，不推断未知内容类型。"""
    try:
        with Image.open(BytesIO(payload)) as image:
            image_format = str(image.format or "").upper()
            if image_format not in IMAGE_FORMATS:
                return None
            extension, mime = IMAGE_FORMATS[image_format]
            frame_count = int(getattr(image, "n_frames", 1))
            loop = image.info.get("loop")
            durations = []
            if image_format == "GIF" or frame_count > 1:
                # verify() 不能代替动画逐帧解码，后面的损坏帧也必须被拒绝。
                for index in range(frame_count):
                    image.seek(index)
                    durations.append(int(image.info.get("duration", 0)))
                    if verify:
                        image.load()
            info = ImageInfo(
                image_format, extension, mime, image.width, image.height,
                frame_count > 1, frame_count, tuple(durations),
                int(loop) if loop is not None else None,
            )
            if verify and image_format != "GIF" and frame_count == 1:
                image.verify()
            return info
    except Exception:
        return None


def image_mime_type(payload: bytes) -> str:
    """对实际图片使用其 MIME；旧的不完整存储数据保留 PNG 后备值。"""
    info = inspect_image(payload)
    return info.mime_type if info is not None else "image/png"
