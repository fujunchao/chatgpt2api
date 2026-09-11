"""图片模型名称、路由和参数约束；不依赖运行时服务或账号数据。"""

from __future__ import annotations

import re


IMAGE_MODEL_PLAN_TYPES = ("plus", "team", "pro")
CODEX_IMAGE_MODEL = "codex-gpt-image-2"
# 这是本项目的 Web 兼容入口，不是已验证的官方图片引擎标识。
WEB_AUTO_IMAGE_MODEL = "gpt-image-2.5"
WEB_IMAGE_MODELS = frozenset({"gpt-image-2", WEB_AUTO_IMAGE_MODEL})
GPT_IMAGE_25_MODELS = frozenset({
    "gpt-image-2.5-flare",
    "gpt-image-2.5-sunburst",
})

# 裸变体名与带 codex- 的名称都走 Codex；不猜测网页端的 2.5 model slug。
# 通用 Codex 2.5 别名明确选择 Flare，不能悄悄降级成 2.0。
CODEX_TOOL_MODELS = {
    CODEX_IMAGE_MODEL: "gpt-image-2",
    **{model: model for model in GPT_IMAGE_25_MODELS},
    "codex-gpt-image-2.5": "gpt-image-2.5-flare",
    "codex-gpt-image-2.5-flare": "gpt-image-2.5-flare",
    "codex-gpt-image-2.5-sunburst": "gpt-image-2.5-sunburst",
}
CODEX_IMAGE_MODELS = frozenset(CODEX_TOOL_MODELS)
CODEX_PREFIXABLE_MODELS = frozenset(model for model in CODEX_IMAGE_MODELS if model.startswith("codex-"))
BASE_IMAGE_MODELS = WEB_IMAGE_MODELS | CODEX_IMAGE_MODELS
PREFIXED_CODEX_IMAGE_MODELS = frozenset(
    f"{plan}-{model}"
    for plan in IMAGE_MODEL_PLAN_TYPES
    for model in CODEX_PREFIXABLE_MODELS
)
IMAGE_MODELS = BASE_IMAGE_MODELS | PREFIXED_CODEX_IMAGE_MODELS
PUBLIC_IMAGE_MODELS = IMAGE_MODELS
IMAGE_QUALITIES = ("auto", "low", "medium", "high")
IMAGE_25_QUALITIES = (*IMAGE_QUALITIES, "xhigh", "max")


class ImageModelParameterError(ValueError):
    def __init__(self, message: str, param: str):
        super().__init__(message)
        self.param = param


def split_image_model(model: object) -> tuple[str | None, str | None]:
    normalized = str(model or "").strip().lower()
    if normalized in BASE_IMAGE_MODELS:
        return None, normalized
    for plan in IMAGE_MODEL_PLAN_TYPES:
        prefix = f"{plan}-"
        if normalized.startswith(prefix) and normalized[len(prefix):] in CODEX_PREFIXABLE_MODELS:
            return plan, normalized[len(prefix):]
    return None, None


def is_supported_image_model(model: object) -> bool:
    return split_image_model(model)[1] is not None


def is_codex_image_model(model: object) -> bool:
    return split_image_model(model)[1] in CODEX_IMAGE_MODELS


def is_web_auto_image_model(model: object) -> bool:
    """识别显式的 Web 自动入口，不把它视为已确认的 2.5 引擎。"""
    return split_image_model(model)[1] == WEB_AUTO_IMAGE_MODEL


def codex_tool_model(model: object) -> str:
    base_model = split_image_model(model)[1]
    if base_model not in CODEX_TOOL_MODELS:
        raise ImageModelParameterError("unsupported Codex image model", "model")
    return CODEX_TOOL_MODELS[base_model]


def is_gpt_image_25_model(model: object) -> bool:
    return CODEX_TOOL_MODELS.get(split_image_model(model)[1] or "") in GPT_IMAGE_25_MODELS


def image_model_qualities(model: object) -> tuple[str, ...]:
    return IMAGE_25_QUALITIES if is_gpt_image_25_model(model) else IMAGE_QUALITIES


def validate_image_options(model: object, size: object, quality: object) -> tuple[object, str]:
    """只约束新增 2.5 模型，不改变旧 2.0 请求的宽松参数行为。"""
    if not is_gpt_image_25_model(model):
        return size, str(quality or "auto")
    normalized_quality = str(quality or "auto").strip().lower()
    if normalized_quality not in IMAGE_25_QUALITIES:
        raise ImageModelParameterError(
            "quality must be one of auto, low, medium, high, xhigh, max", "quality",
        )
    normalized_size = str(size or "").strip().lower()
    if normalized_size in {"", "auto"}:
        return normalized_size or None, normalized_quality
    match = re.fullmatch(r"(\d{1,5})x(\d{1,5})", normalized_size)
    if not match:
        raise ImageModelParameterError("size must be auto or WIDTHxHEIGHT", "size")
    width, height = map(int, match.groups())
    if (
        width <= 0 or height <= 0
        or width % 16 or height % 16
        or max(width, height) > 3840
        or max(width, height) > 3 * min(width, height)
        or not 655_360 <= width * height <= 8_294_400
    ):
        raise ImageModelParameterError(
            "size requires multiples of 16, edges <= 3840, aspect ratio <= 3:1, "
            "and 655360-8294400 pixels", "size",
        )
    return normalized_size, normalized_quality
