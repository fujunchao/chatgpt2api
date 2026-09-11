from __future__ import annotations

from typing import Any

from services.account_service import account_service
from services.openai_backend_api import OpenAIBackendAPI
from utils.image_models import CODEX_IMAGE_MODELS, CODEX_PREFIXABLE_MODELS, WEB_AUTO_IMAGE_MODEL
from utils.log import logger


def list_models() -> dict[str, Any]:
    dynamic_models: set[str] = set()
    accounts = account_service.list_accounts()
    web_image_accounts = [
        account
        for account in accounts
        if isinstance(account, dict) and account.get("status") not in {"禁用", "异常"}
    ]
    codex_types = {
        normalized
        for account in accounts
        if isinstance(account, dict)
           and account.get("status") not in {"禁用", "异常"}
           and account_service._normalize_source_type(account.get("source_type")) == "codex"
           and (normalized := account_service._normalize_account_type(account.get("type")))
    }

    if web_image_accounts:
        dynamic_models.add("gpt-image-2")
    if any(
        account_service._account_matches_source_type(account, "web")
        for account in web_image_accounts
    ):
        dynamic_models.add(WEB_AUTO_IMAGE_MODEL)
    if codex_types & {"Plus", "Team", "Pro"}:
        dynamic_models.update(CODEX_IMAGE_MODELS)
    for plan in ("Plus", "Team", "Pro"):
        if plan in codex_types:
            dynamic_models.update(f"{plan.lower()}-{model}" for model in CODEX_PREFIXABLE_MODELS)

    backend = OpenAIBackendAPI()
    try:
        result = backend.list_models()
    except Exception as exc:
        # 匿名模型目录故障不应隐藏本地账号已经配置的图片调用入口。
        if not dynamic_models:
            raise
        logger.warning({"event": "model_catalog_image_fallback", "error": str(exc)[:300]})
        result = {"object": "list", "data": []}
    finally:
        backend.close()
    data = result.get("data")
    if not isinstance(data, list):
        return result
    # 新入口由本地路由与账号来源决定，不能继承匿名目录的同名能力声明。
    data = [item for item in data if not isinstance(item, dict) or item.get("id") != WEB_AUTO_IMAGE_MODEL]
    result["data"] = data
    seen = {str(item.get("id") or "").strip() for item in data if isinstance(item, dict)}

    for model in sorted(dynamic_models):
        if model not in seen:
            item = {
                "id": model,
                "object": "model",
                "created": 0,
                "owned_by": "chatgpt2api",
                "permission": [],
                "root": model,
                "parent": None,
            }
            if model == WEB_AUTO_IMAGE_MODEL:
                item.update({
                    "description": "ChatGPT Web 图片兼容入口，支持有配额的 Free 网页账号；图片引擎由官网自动选择，具体版本未知，不能指定 Flare / Sunburst。",
                    "metadata": {"route": "web", "model_selection": "upstream_auto", "variant_selection": False},
                })
            data.append(item)
    return result
