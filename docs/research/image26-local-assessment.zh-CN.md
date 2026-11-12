# Image 2.6 官方协议与本地适配核查（2026-11-12）

> 本文是实施前的协议与源码对照，Codex 示例仅为候选研究。v0.16.4 采用已确认的网页账号路线，当前行为见 [网页接入说明](../image26-web-integration.zh-CN.md)。

用户已明确采用网页账号路线，当前实施步骤以 [网页账号适配计划](../image26-web-account-adaptation-plan.zh-CN.md) 为准。本文保留官方协议核查、现有代码基线和最初 Codex 候选差异，作为不同通道的技术对照。

Image 2.6 已有官方文档，指定版本的模型 ID 是 `gpt-image-2.6-sunburst` 和 `gpt-image-2.6-flare`。本地 `HEAD=5927143`（v0.16.3）尚未注册这些模型。最小适配可以在现有 Codex `image_generation` 工具链中加入两个变体，先继续输出 PNG；同时补齐参数校验、模型目录、前端说明、用量和错误处理。GIF、SVG、markup 和网页端指定变体应分别按实际通道能力扩展。

本次只核查源码、官方文档和已有离线基线，并提供可审查的代码示例；以下示例尚未应用到业务文件，也没有发送真实 Image 2.6 请求。

## 1. 实际读取的官方资料

以下文档及其 `.md` 版本均实际读取成功（HTTP 200），不是仅依据搜索摘要。项目 `POST http://127.0.0.1:8000/v1/search` 当前连接被拒绝，官方核查改用限定官方域的检索和直接文档读取。

| 核查项 | 当前官方证据 | 对项目的含义 |
| --- | --- | --- |
| 精确模型 ID | [Sunburst 模型页](https://developers.openai.com/api/docs/models/gpt-image-2.6-sunburst)、[Flare 模型页](https://developers.openai.com/api/docs/models/gpt-image-2.6-flare) 分别写明两个 ID；裸 `gpt-image-2.6` 未列入官方枚举 | 注册两个具体变体；裸名只能是项目另行定义的兼容别名 |
| 直接调用端点 | 两个模型页均列 `v1/images/generations`、`v1/images/edits` 为 Supported；顶层 `v1/responses`、`v1/chat/completions` 为 Not supported | 不能把图像模型填入官方 Responses 顶层 `model` |
| Responses 工具模型 | [Responses create 参考](https://developers.openai.com/api/reference/resources/responses/methods/create) 的 `image_generation.model` 枚举含两个 2.6 变体，默认值为 `gpt-image-2.6-sunburst` | **Responses 工具可以选择 2.6**。模型页的顶层端点表不能用来否定工具用法；官方 API 的声明仍不能替代本地 `/backend-api/codex/responses` 的账号实测 |
| `quality` 与 `complexity` | [图像指南的 2.6 小节](https://developers.openai.com/api/docs/guides/image-generation#gpt-image-26) 明确二者独立：`quality` 控制渲染质量，`complexity` 控制渲染前规划，取 `low/medium/high`；Images API 省略 complexity 时默认为 high | 现有 `quality=auto` 请求合法。加入 2.6 不要求把 quality 改为 complexity；最低 PNG 方案可以暂不传 complexity |
| Responses complexity 默认值 | [Responses create](https://developers.openai.com/api/reference/resources/responses/methods/create) 写明省略时继承可支持的外层 reasoning effort，或使用图像模型配置的默认值 | 不应笼统声称所有通道省略 complexity 都无条件等于 high |
| 2.6 质量档 | [指南成本计算部分](https://developers.openai.com/api/docs/guides/image-generation#calculating-costs) 明确 2.5、2.6 的两个变体均支持 `low/medium/high/xhigh/max`；请求 schema 另有 `auto` | 可以复用当前六档质量集合；`complexity` 不是新增质量档 |
| 静态尺寸 | [生成参考](https://developers.openai.com/api/reference/resources/images/methods/generate) 和 [指南尺寸部分](https://developers.openai.com/api/docs/guides/image-generation#size-and-quality-options) 列标准 `1024x1024/1536x1024/1024x1536` 和 `auto`；自定义尺寸叙述仍主要指 2.5 等旧型号，没有单列 2.6 上限表 | 初次验收先使用标准尺寸。若沿用 2.5 的自定义尺寸规则，明确这是本地暂定约束，不能宣称已经验证 2.6 原生 4K |
| GIF | [GIF 指南](https://developers.openai.com/api/docs/guides/image-generation#generate-animated-gif-output)、[生成 schema](https://developers.openai.com/api/reference/resources/images/methods/generate)、[编辑 schema](https://developers.openai.com/api/reference/resources/images/methods/edit) 都支持生成和编辑 GIF，帧数 **2–16**，默认 9；Images schema 另要求账号有 GIF preview 权限 | “最多 64 帧”“编辑一律禁止 GIF”不能作为当前官方 API 规则；某个 fork 的编辑限制应标成该实现的限制 |
| GIF 帧间隔与流式 | 指南及 Responses 工具 schema 为 `20–2000 ms`、默认 200、按 10 ms 取整；Images schema 仅明确下限 20、编码延迟上限 655350 ms。Responses 工具允许 GIF 的生命周期事件流，不支持 partial image 流、mask 和自定义压缩 | 本地 Codex 扩展先使用工具 schema 的 `20–2000`；不能把“不支持 partial image”误写成“一律不能 stream=True” |
| SVG | [SVG 指南](https://developers.openai.com/api/docs/guides/image-generation#generate-svg-output) 说明 `n=1`、仅生成端点、不能把 SVG 当栅格编辑输入；[生成 schema](https://developers.openai.com/api/reference/resources/images/methods/generate) 的 `svg.model` 仅在开启 SVG model selection 时必填，否则应省略 svg 对象 | SVG 需要独立输出处理和作者模型用量；不应无条件要求所有请求都携带 svg.model |
| markup | [markup 指南](https://developers.openai.com/api/docs/guides/image-generation#guide-an-edit-with-markup) 明确支持 2.5、2.6，并给出 2.6 Flare 示例；第一张原图和透明 PNG 标注层需在旋转处理后同尺寸，不能与 mask 同用 | 官方 Images 编辑通道已经有证据。本地现有 mask 的本地透明度合成不能直接当成原生 markup；工具端也不能凭 Images schema 猜字段 |
| 用量与价格 | [两个模型页](https://developers.openai.com/api/docs/models/gpt-image-2.6-sunburst) 的 image token 费率为输入 $8、缓存 $2、输出 $30 / 百万 tokens；[指南](https://developers.openai.com/api/docs/guides/image-generation#cost-and-latency) 提醒相同费率不代表每张图相同成本 | 不能继续套 2.0 输出 token 公式来冒充 2.6 实际用量；SVG 作者用量与图像渲染用量还应分开 |

文档存在局部更新不同步：例如 markup 的编辑字段短描述仍只写 2.5，但指南明确写 2.5/2.6；部分质量和自定义尺寸描述同样仍列旧型号。这里保留实际证据的范围，避免用遗漏的短描述推出“新型号一定不支持”。

## 2. 本地链路与实际缺口

真实上游为 `basketikun/chatgpt2api`，当前上游 main 的 `92dd80e91543157d36a4ddad60e765c5293760e9` 尚只注册 2.0 图片入口，其 Codex 工具仍填写旧 `gpt-image-2`。来源：[上游 helper](https://github.com/basketikun/chatgpt2api/blob/92dd80e91543157d36a4ddad60e765c5293760e9/utils/helper.py#L17)、[上游工具请求](https://github.com/basketikun/chatgpt2api/blob/92dd80e91543157d36a4ddad60e765c5293760e9/services/openai_backend_api.py#L792-L793)。本地已有集中注册表、2.5、Free 网页入口、OAuth 来源区分和生产恢复逻辑，因此应在本地结构上增补模型，而不是整文件覆盖为某个 fork 的实现。

| 本地位置 | 当前实际行为 | 最小 2.6 变更 |
| --- | --- | --- |
| [utils/image_models.py](https://github.com/fujunchao/chatgpt2api/blob/5927143ec4421886b5e1f563718b564c0bdf52d9/utils/image_models.py#L11)（11–38、78–113 行） | 裸 `gpt-image-2.5` 是 Web 自动入口；带 flare/sunburst 的名字和 codex 别名走 Codex；唯一集中模型真源尚无 2.6 | 新增两个精确 ID 和两个明确 codex 变体别名；自动派生 Plus/Team/Pro 前缀 |
| [services/openai_backend_api.py](https://github.com/fujunchao/chatgpt2api/blob/5927143ec4421886b5e1f563718b564c0bdf52d9/services/openai_backend_api.py#L768)（768–797 行） | `tools[0].model=codex_tool_model(model)`，顶层 `model=gpt-5.5`，`output_format=png`，`action` 根据输入图选择 edit/generate | PNG 最小阶段复用现有 payload，只改变注册表返回的精确工具模型；不需要升级顶层控制模型或更换 URL |
| [services/protocol/conversation.py](https://github.com/fujunchao/chatgpt2api/blob/5927143ec4421886b5e1f563718b564c0bdf52d9/services/protocol/conversation.py#L1364)（1364–1372 行） | Codex 模型只选 `source_type=codex` 的 Plus/Team/Pro；Web 自动入口显式只选网页来源 | 2.6 精确变体继续归 Codex；Free、password、oauth_login 网页账号不能因名字相似被选中 |
| [services/account_service.py](https://github.com/fujunchao/chatgpt2api/blob/5927143ec4421886b5e1f563718b564c0bdf52d9/services/account_service.py#L150)（150–170 行） | 网页来源包含 web/password/oauth_login；账号类型、来源和配额决定能否进入账号池 | 可以复用来源筛选；模型出现在 `/v1/models` 只说明本地有匹配账号，不能当成 2.6 权限已验证 |
| [services/protocol/openai_v1_models.py](https://github.com/fujunchao/chatgpt2api/blob/5927143ec4421886b5e1f563718b564c0bdf52d9/services/protocol/openai_v1_models.py#L35)（35–39 行） | 动态目录使用 `CODEX_IMAGE_MODELS`、`CODEX_PREFIXABLE_MODELS` | 注册表扩充后自动派生目录；不要另造第二套静态白名单 |
| [services/protocol/conversation.py](https://github.com/fujunchao/chatgpt2api/blob/5927143ec4421886b5e1f563718b564c0bdf52d9/services/protocol/conversation.py#L1262)（1262–1324 行） | 读取 `image_generation_call.result`、从完成事件收集图片并去重；缺少 usage 只对 2.5 标 unavailable | PNG 的结果形态可以复用；对 2.6 同样保留 unknown usage，不重复记账 |
| [utils/image_tokens.py](https://github.com/fujunchao/chatgpt2api/blob/5927143ec4421886b5e1f563718b564c0bdf52d9/utils/image_tokens.py#L348)（348–367 行） | 只有 2.5/Web 自动入口避开旧图片 token 估算 | 2.6 加入 unavailable 分支；否则新增 model 后会返回旧公式的 estimated 数字 |
| [services/protocol/conversation.py](https://github.com/fujunchao/chatgpt2api/blob/5927143ec4421886b5e1f563718b564c0bdf52d9/services/protocol/conversation.py#L1543)（1543–1552 行） | 只有 2.5 保留上游 HTTP status/type/code/param；其他错误可能落入通用错误处理 | 把同样的结构化错误保留应用于 2.6；没有权限或模型不可用时明确报错，不能自动降到 2.0/2.5 |
| [web/src/lib/image-models.ts](https://github.com/fujunchao/chatgpt2api/blob/5927143ec4421886b5e1f563718b564c0bdf52d9/web/src/lib/image-models.ts#L6)（6–14、40–44 行） | 2.5 的 Codex 识别和 xhigh/max 控件依赖正则 | 增补 2.6 具体变体正则；质量选项和路由说明与后端一致；不新增“Free 可指定 2.6 变体”的暗示 |
| [services/image_storage_service.py](https://github.com/fujunchao/chatgpt2api/blob/5927143ec4421886b5e1f563718b564c0bdf52d9/services/image_storage_service.py#L199)、[services/image_service.py](https://github.com/fujunchao/chatgpt2api/blob/5927143ec4421886b5e1f563718b564c0bdf52d9/services/image_service.py#L51) | 保存名固定 `.png`，WebDAV put 默认 image/png，远端响应固定 image/png；缩略图、批量压缩、清理按静态 PNG 处理 | PNG 最小阶段可保留；请求 JPEG/WebP/GIF/SVG 时必须按真实格式调整扩展名、MIME 和处理路径 |

本地纯注册表实测：`gpt-image-2.6`、两个 2.6 精确变体、`codex-gpt-image-2.6-flare`、`plus-codex-gpt-image-2.6-sunburst` 的 `is_supported_image_model` 目前全部为 false。生成入口在 [conversation.py:1589](https://github.com/fujunchao/chatgpt2api/blob/5927143ec4421886b5e1f563718b564c0bdf52d9/services/protocol/conversation.py#L1589) 对不支持的模型返回 400 / `model_not_found` / `param=model`。

文本 token 统计在 [conversation.py:232](https://github.com/fujunchao/chatgpt2api/blob/5927143ec4421886b5e1f563718b564c0bdf52d9/services/protocol/conversation.py#L232) 已有 tiktoken 型号未知时的 `o200k_base` 后备（再后备 cl100k_base）。这只用于本地文本统计，不证明 2.6 图像引擎采用同一 tokenizer。PNG 接入不需要猜一个图像 tokenizer；响应应优先保留上游提供的 usage，缺失就返回 `usage_source=unavailable`。Responses 顶层控制模型用量与图像工具用量也应在实测时核对口径。

## 3. 第一阶段：明确变体的 PNG 最小方案

以下为尚未应用的示例差异。第一次实现只新增两个具体 ID 和两个具体 codex 变体别名；不新增含糊的裸 `gpt-image-2.6` 或 `codex-gpt-image-2.6`。若之后要短别名，可以独立配置默认目标并明确写入文档。

```diff
--- a/utils/image_models.py
+++ b/utils/image_models.py
@@
 GPT_IMAGE_25_MODELS = frozenset({
     "gpt-image-2.5-flare",
     "gpt-image-2.5-sunburst",
 })
+GPT_IMAGE_26_MODELS = frozenset({
+    "gpt-image-2.6-flare",
+    "gpt-image-2.6-sunburst",
+})
+GPT_IMAGE_VARIANT_MODELS = GPT_IMAGE_25_MODELS | GPT_IMAGE_26_MODELS
@@
 CODEX_TOOL_MODELS = {
     CODEX_IMAGE_MODEL: "gpt-image-2",
     **{model: model for model in GPT_IMAGE_25_MODELS},
+    **{model: model for model in GPT_IMAGE_26_MODELS},
     "codex-gpt-image-2.5": "gpt-image-2.5-flare",
     "codex-gpt-image-2.5-flare": "gpt-image-2.5-flare",
     "codex-gpt-image-2.5-sunburst": "gpt-image-2.5-sunburst",
+    "codex-gpt-image-2.6-flare": "gpt-image-2.6-flare",
+    "codex-gpt-image-2.6-sunburst": "gpt-image-2.6-sunburst",
 }
@@
 def is_gpt_image_25_model(model: object) -> bool:
     return CODEX_TOOL_MODELS.get(split_image_model(model)[1] or "") in GPT_IMAGE_25_MODELS

+def is_gpt_image_variant_model(model: object) -> bool:
+    """识别 2.5/2.6 具体变体及其 Codex 别名，供公共参数与用量规则使用。"""
+    return CODEX_TOOL_MODELS.get(split_image_model(model)[1] or "") in GPT_IMAGE_VARIANT_MODELS
@@
 def image_model_qualities(model: object) -> tuple[str, ...]:
-    return IMAGE_25_QUALITIES if is_gpt_image_25_model(model) else IMAGE_QUALITIES
+    return IMAGE_25_QUALITIES if is_gpt_image_variant_model(model) else IMAGE_QUALITIES
@@
-    if not is_gpt_image_25_model(model):
+    if not is_gpt_image_variant_model(model):
         return size, str(quality or "auto")
```

保留 `is_gpt_image_25_model` 的原语义，不让名称写 2.5 的函数对 2.6 也返回 true。随后将以下公共调用点改用 `is_gpt_image_variant_model`，并同步 import：

| 调用点 | 需要保留的行为 |
| --- | --- |
| `utils/image_models.py:83/88` | 两代变体使用共同质量档和严格参数校验；旧 2.0 的宽松行为不变 |
| `utils/image_tokens.py:361` | 2.6 无上游 usage 时为 `(None, "unavailable")`，不调用旧图片输出估算 |
| `services/protocol/conversation.py:1324` | 2.6 输出无 usage 时同样标记 unavailable |
| `services/protocol/conversation.py:1543` | 保留上游模型不可用/没有权限的 HTTP status、type、code、param；回退文案从“2.5”改成通用图片模型 |

尺寸应作单独的版本规则处理：现有 2.5 的自定义尺寸校验保持不变；初次 2.6 可以只开放 `auto` 和三个标准尺寸。若采用这个最保守验收范围，可在 `validate_image_options` 的空值/auto 返回之后、旧自定义尺寸正则之前加入：

```python
# 2.6 先开放文档中明确的标准尺寸；自定义尺寸待该通道实测后扩展。
if codex_tool_model(model) in GPT_IMAGE_26_MODELS:
    if normalized_size not in {"1024x1024", "1536x1024", "1024x1536"}:
        raise ImageModelParameterError(
            "2.6 暂仅开放 auto、1024x1024、1536x1024、1024x1536", "size",
        )
    return normalized_size, normalized_quality
```

这是一项初次验收策略，不是宣称官方 2.6 不支持自定义尺寸。若选择沿用 2.5 的自定义尺寸上限，也应明确其暂定性质并增加真实尺寸核对。

前端同样保留 2.5 的旧函数，另增共用判定；2.6 的 codex 名称必须带明确变体，与后端白名单严格一致：

```typescript
/** 2.5/2.6 具体图像变体的 Codex 请求选项；不能据此承诺账号权限。 */
export function isGptImageVariantModel(model: string): boolean {
  return isGptImage25Model(model) ||
    /^(?:gpt-image-2\.6-(?:flare|sunburst)|(?:(?:plus|team|pro)-)?codex-gpt-image-2\.6-(?:flare|sunburst))$/.test(
      model.trim().toLowerCase(),
    );
}
```

把 `isCodexImageModel` 和 `imageQualityOptions` 的公共 2.5 判断换成这个新判定。现有 `isWebAutoImageModel` 和网页自动说明保留，`gpt-image-2.6-*` 显示 Codex 来源，不归入 Free 网页入口。

预期请求映射如下；任意一项都不能悄悄变成 2.0 或 2.5：

| 用户 `model` | 账号来源 | 上游 `tools[0].model` |
| --- | --- | --- |
| `gpt-image-2.6-flare` | Codex Plus/Team/Pro | `gpt-image-2.6-flare` |
| `codex-gpt-image-2.6-sunburst` | Codex Plus/Team/Pro | `gpt-image-2.6-sunburst` |
| `team-codex-gpt-image-2.6-flare` | Codex Team | `gpt-image-2.6-flare` |
| `pro-codex-gpt-image-2.6-sunburst` | Codex Pro | `gpt-image-2.6-sunburst` |

其他字段继续使用当前 `model=gpt-5.5`、`action=generate/edit`、`quality=auto`、`output_format=png`、`stream=True`。本地对外的 Chat Completions/Responses 图片兼容协议属于项目封装，可以调用同一图片管线；不能拿官方顶层 `model` 限制来否定这些本地兼容入口。

最直接的 PNG 对照是 [hp0912 的集中映射](https://github.com/hp0912/chatgpt2api/blob/e5bae8714da06c4e3676dd00d04bd56266c35d64/utils/helper.py#L17-L24) 和 [Codex 请求](https://github.com/hp0912/chatgpt2api/blob/e5bae8714da06c4e3676dd00d04bd56266c35d64/services/openai_backend_api.py#L781-L811)：客户端 `codex-gpt-image-2.6-sunburst` 被映射成准确的 `gpt-image-2.6-sunburst` 工具模型，而顶层文本模型仍为 `gpt-5.5`。其核心字段与本地既有请求一致：

```json
{
  "model": "gpt-5.5",
  "tools": [{
    "type": "image_generation",
    "model": "gpt-image-2.6-sunburst",
    "action": "generate",
    "size": "1024x1024",
    "quality": "auto",
    "output_format": "png"
  }],
  "tool_choice": {"type": "image_generation"},
  "store": false,
  "stream": true
}
```

其他证据：[FatalErrorR 的模型映射](https://github.com/FatalErrorR/chatgpt2api/blob/53119b5c4682c5606c9b4c80ad9d76d64105686e/utils/helper.py#L22-L44)、[其 Codex 工具 payload](https://github.com/FatalErrorR/chatgpt2api/blob/53119b5c4682c5606c9b4c80ad9d76d64105686e/services/openai_backend_api.py#L887-L924)，以及 [orangewoker 的 GIF 请求字段测试](https://github.com/orangewoker/chatgpt2api/blob/d1e8ed4a0607abd101e079ae9e9d4f8f83297dce/test/test_gif_output.py#L48-L64)。后者检查 mock 捕获的 urllib 请求仍选 2.6，同时携带 gif、帧数、间隔；它的帧数校验允许到 64，超出当前官方 schema 的 16，不能照搬这个范围。更广泛的仓库分类、共享提交、继承实现与实际验证状态由本次 fork 核查报告分别列出；存在代码不等于已经替本项目完成账号实测。

## 4. 第二阶段：按通道扩展参数与输出

| 能力 | 需要打通的本地位置 | 当前证据与验收边界 |
| --- | --- | --- |
| JPEG/WebP 静态输出 | `ConversationRequest`、各 HTTP 解析入口、任务 payload、Codex tool options；图片存储/远端响应/下载扩展名 | 可以复用静态图片处理，但目前上游请求固定 png。必须按实际结果记录 MIME，不能只是把请求改成 jpeg |
| complexity | `ConversationRequest` → `stream_codex_image_outputs` → `iter_codex_image_response_events`；前端与异步任务参数同步 | 工具 schema 已证实为独立字段。该账号通道真实接受后再开放 UI，不应靠提示词冒充参数透传 |
| GIF 生成与参考图动画 | 同上新增 `output_format/frame_count/frame_duration_ms`；保留二进制与动画帧；格式感知的存储、MIME、缩略图、压缩/清理 | 官方工具帧数 2–16，帧间隔 20–2000；支持生命周期 SSE，不支持 partial image、mask、自定义压缩。参考图动画在官方 Images 编辑端点有证据；若 Codex fork 不支持编辑 GIF，标注该通道限制 |
| SVG | 请求格式及条件作者配置、独立 SVG 保存与预览、作者用量与图像用量分开；避免用 Pillow 读取原 SVG | SVG 不是普通栅格图片；需要遵守 n=1 与该端点的流式/编辑限制。不能由工具枚举直接假设 Codex 账号具备 SVG 权限 |
| markup | 官方 Images 编辑通道的透明 PNG 图层上传/JSON 引用、首图尺寸/透明度/像素检查、mask 互斥 | 本地现有 `_composite_mask` 是把 mask 合入 RGBA 输入，不能直接升级成原生 markup。Codex 工具侧未取得可直接透传的 markup 证据 |
| Web 指定 2.6 | 网页 prepare/conversation 的真实 payload、模型选择字段、返回模型信息、source_type 路由和界面说明 | 当前所有 Web 图片入口都映射 `gpt-5-3` + `picture_v2`。增加一个 2.6 名字会发送相同旧请求，不能证明具体图片引擎变成 2.6 |
| 官方 API 账号 | 仅在决定新增通道后增加独立的 API Key/账号来源、计费/错误处理和 Images 请求服务 | 官方 API 的公开参数最完整，但本地当前使用订阅账号池。不能把订阅 OAuth token 当 API Key，也不能把新增付费 API 通道当成基础适配的必要条件 |

当前业务源码没有发现出图结果的“本地超分”调用。已证实的格式问题是固定 PNG 文件名、默认 MIME 和静态 PNG 压缩/缩略图处理。GIF 若被保存成 `.png` 再进入 `compress_images`，会被按 PNG 重写而丢掉动画；扩展阶段应避免这一实际路径，不沿用旧草稿的泛化描述。

## 5. 已运行的基线与下一步验收

### 本次实际结果

- 后端在 `scripts/run_offline_tests.py` 创建的隔离临时副本中运行，不复制生产 config/.env/data；requests、curl_cffi、urllib 与外连 socket 均被禁用。共 **84 个 unittest 测试通过**，0 failure、0 error、0 skipped。
- Bun 前端纯函数测试 **4 个通过，30 个断言，0 failure**。
- TypeScript 全项目检查尝试失败，原因是本地 `web/node_modules/typescript/bin/tsc` 不存在；没有安装依赖或修改 lockfile。
- 这些结果验证的是现有 2.5/Web/账号池等基线；本次没有应用 2.6 代码，因此不能表述成“2.6 测试已通过”。

后端实跑命令：

```powershell
uv run --no-sync python scripts/run_offline_tests.py test.test_image_model_routing test.test_gpt_image_25 test.test_image_25_protocols test.test_free_web_image test.test_account_image_capabilities test.test_image_tokens test.test_image_output_tokens test.test_image_task_service test.test_image_storage_service test.test_multi_image_results test.test_v1_models.ModelListTests.test_list_models_only_returns_image_models_backed_by_account_types test.test_v1_models.ModelListTests.test_list_models_does_not_return_codex_models_for_web_plus_accounts
```

其中 `test.test_image_output_tokens` 不是 unittest 风格，发现 0 个 unittest 测试，不计入上述 84 个实际测试。测试选择覆盖模型路由、2.5 请求与兼容协议、Free/OAuth 网页路径、Codex 账号来源、用量、任务、存储、多图去重、模型目录。

前端实跑命令（项目根目录）：

```powershell
bun test ./test/test_image_models_frontend.test.ts
```

全项目类型检查尝试（web 目录，因依赖缺失未通过）：

```powershell
node ./node_modules/typescript/bin/tsc --noEmit --incremental false
```

### PNG 实现后的必要测试

1. 纯路由：两个精确 ID、两个 codex 变体别名及 Plus/Team/Pro 前缀映射准确；Web/Free 不被混选；不支持的裸名明确拒绝；旧 `codex-gpt-image-2.5` 别名仍映射 Flare，裸 `gpt-image-2.5` 保持网页自动入口。
2. 捕获请求：对两个 2.6 变体验证 `tools[0].model` 原样命中，quality/size/action/output_format 正确，顶层控制模型和账号来源不变；编辑输入确实进入 `input_image`。
3. 用量：上游有 usage 时保留；缺失 usage 时不套旧公式、不返回估计数字；兼容 Chat/Responses/Images 的用量口径一致。
4. 错误：模拟模型未开放、403、429、无图片结果和已提交断流；保留 status/type/code/param，不删除仅缺 2.6 权限的正常账号，不降级、不重复提交出图。
5. 前端/目录：后端注册名与前端正则逐一对应，2.6 变体展示 Codex 来源和六档质量；标准尺寸以真实返回为准；模型目录的“有账号”不等于“已验证权限”。
6. 运行已有 2.5/Web/OAuth/恢复基线，再用有权限的 Codex 来源账号对两个变体分别做一次低质量、标准尺寸、单张 PNG 的真实生成与一次编辑；核对最终文件格式、实际尺寸、请求工具模型、返回元数据/usage。仅凭画面效果或目录存在不能证明引擎版本。

若上游不返回可验证的图像模型身份，结论应限定为“请求明确选择 2.6，服务返回图片”，而不是断言图片引擎已独立认证。GIF/SVG 等扩展再按各自约束和账号权限做独立验收。

## 6. 对现有 Image 2.6 草稿的复核意见

用户工作区已有 `docs/image26-adaptation-plan.zh-CN.md`、`docs/image26-upstream-survey.zh-CN.md`，本次未覆盖它们。以下条目需要用本轮证据修订：

| 草稿条目 | 当前核查后的准确口径 |
| --- | --- |
| “官方仅 Images 端点，所以可以复用 Codex” | 先区分顶层模型与工具模型；官方 Responses 工具枚举实际已经支持 2.6。Codex 复用另有 fork payload 证据，不能从端点表直接推导 |
| “GIF 帧数 2–64” | 当前 guide、Images generate/edit 和 Responses 工具 schema 均为 2–16 |
| “编辑链路统一拒绝 GIF” | 官方 Images 编辑支持 GIF 参考图动画；只有某个通道没有能力或未经验证时才限制该通道 |
| “SVG 必须 svg.model” | 官方 Images API 开启 model selection 时才要求；关闭时省略对象。Responses 工具另有自己的默认策略 |
| “2.6 沿用 2.5 尺寸就是官方事实” | 官方缺少独立 2.6 上限表；沿用只能作为本地暂定约束，标准尺寸先验收 |
| “把 is_gpt_image_25_model 直接别名为新代判定” | 保留旧函数的精确 2.5 语义；公共参数、用量、错误另用泛化谓词 |
| “上游返回 GIF 会被现有超分处理” | 本地当前无出图超分调用；具体风险在固定 PNG 文件名/MIME、静态压缩和缩略图 |
| “共享一套 token 费率就能复用每图估算” | 费率相同不代表每图 token 相同，2.6 缺上游用量时应为 unavailable |

所有 fork 数量与候选分类以本轮全量清单和固定提交的源码核查为准；旧草稿的仓库清单和检索计数不作为本轮已确认事实。
