# Image 2.6 上游、fork 与本项目适配结论

> 本文保留实施前的调研快照和基线；v0.16.4 的实际网页实现及验收结果见 [网页接入说明](image26-web-integration.zh-CN.md)。文中的“尚未实现/实测”描述属于调研阶段。

核查日期：2026-11-12（北京时间）；本地版本：`HEAD=5927143`，v0.16.3。下文 fork 指分叉仓库，SHA/HEAD 用于固定所查提交，Codex 指本项目现有的订阅账号图像工具通道。

**已确认 10 个不同的直接 fork 有完整的 Image 2.6 源码调用链，其中 8 个位于默认分支、2 个位于非默认分支。** 本项目真实上游是 `basketikun/chatgpt2api`，其当前 main 尚未接入 2.6。用户已确认本项目以网页账号适配 2.6，当前实施目标及步骤见 [网页账号适配计划](image26-web-account-adaptation-plan.zh-CN.md)；本报告继续作为上游和不同通道实现的调研依据。

这里的“已适配”指固定提交的静态源码支持；本轮没有对外部 fork 或本地账号发送真实 2.6 生图请求。源码指定了型号，仍需本地有权限的账号验收，才能确认生产可用。

## 1. 上游与全量检查范围

本地 origin 为 [fujunchao/chatgpt2api](https://github.com/fujunchao/chatgpt2api)，[GitHub 第一方元数据](https://api.github.com/repos/fujunchao/chatgpt2api) 的 parent/source 均指向 [basketikun/chatgpt2api](https://github.com/basketikun/chatgpt2api)。上游固定 main 为 `92dd80e91543157d36a4ddad60e765c5293760e9`。

上游的 [模型注册](https://github.com/basketikun/chatgpt2api/blob/92dd80e91543157d36a4ddad60e765c5293760e9/utils/helper.py#L17) 只有 `gpt-image-2` / `codex-gpt-image-2`，[图片工具请求](https://github.com/basketikun/chatgpt2api/blob/92dd80e91543157d36a4ddad60e765c5293760e9/services/openai_backend_api.py#L792-L793) 仍发送旧 `gpt-image-2`。固定源码文本筛查没有 2.6 标识。

| 范围 | 本次实际结果 |
| --- | --- |
| 直接 fork 分页枚举 | 17 页，1,624 个唯一条目 |
| 加入 fork 后代的完整网络枚举 | 1,774 个唯一条目 |
| 可解析仓库及默认提交 | 1,745 个；与上游当时 forks_count=1,745 对齐 |
| 无法解析的条目 | 29 个 NOT_FOUND；原因未确认，不计为已检查源码 |
| 当前分支头 | 2,351 个，去重为 908 个 SHA；189 个仓库有多分支 |
| 默认分支检查 | 348/348 份固定源码快照全部成功，覆盖 1,745 个可解析 fork |
| 非默认分支检查 | 560/560 份独有源码快照全部成功；合计 908/908 份、2,351/2,351 个当前分支头，最终下载失败 0 |
| 默认关键词命中 | 18 个仓库 / 17 个 SHA，含拒绝 2.6 的测试、兼容别名和继承镜像 |
| 全部分支关键词命中 | 22 个仓库 / 23 个 SHA；候选中包含别名、反例和继承，逐仓库结论见下文 |
| 文本筛查量 | 908 份快照中检查 205,108 个文本候选文件 |
| 实际父链归属 | 1,599 个直接 fork、146 个后代 fork，均追溯到 basketikun |

源码筛查覆盖常见源码、文档和配置文本，不执行外部代码；它不是逐行人工审计所有文件，也不覆盖未公开仓库、无当前分支指向的历史提交或二进制内部内容。对命中候选再追踪“客户端模型 → 实际发送字段 → 返回图片”的完整链路。新推送可能改变后续结果。

全量仓库表、分支状态和失败边界见 [完整 fork 清单](research/image26-fork-inventory.zh-CN.md)。

## 2. 10 个可复核的适配 fork

先列 8 个默认分支中的实现，再列 2 个非默认分支中的实现。这 10 个仓库均属于本次上游网络中的直接 fork，检查的固定提交各不相同。其中 jiawen-afk 与 mxw13579 共享部分实现，不能把不同仓库说成完全独立的协议。每行链接指向实际发送或映射代码；完整输入、账号选择、生成/编辑与返回证据见 [逐仓库实现核查](research/image26-fork-implementations.zh-CN.md)。

| 仓库 / 固定提交 | 确认的 2.6 路线 | 实际代码证据 | 对本项目的参考 |
| --- | --- | --- | --- |
| [FatalErrorR/chatgpt2api](https://github.com/FatalErrorR/chatgpt2api) · `53119b5c4682` | Web 精确原名；Codex 工具精确映射 | [模型映射](https://github.com/FatalErrorR/chatgpt2api/blob/53119b5c4682c5606c9b4c80ad9d76d64105686e/utils/helper.py#L22-L44)、[工具请求](https://github.com/FatalErrorR/chatgpt2api/blob/53119b5c4682c5606c9b4c80ad9d76d64105686e/services/openai_backend_api.py#L887-L929) | 模型版本与账号来源分开；明确的 Sunburst 不改成 Flare |
| [hp0912/chatgpt2api](https://github.com/hp0912/chatgpt2api) · `e5bae8714da0` | Web 原名；Codex 别名映射到同名图片工具 | [注册表](https://github.com/hp0912/chatgpt2api/blob/e5bae8714da06c4e3676dd00d04bd56266c35d64/utils/helper.py#L17-L34)、[实际 payload](https://github.com/hp0912/chatgpt2api/blob/e5bae8714da06c4e3676dd00d04bd56266c35d64/services/openai_backend_api.py#L781-L811) | 最接近本地：顶层控制模型保持 `gpt-5.5`，改变 `tools[0].model`；未知模型明确报错 |
| [orangewoker/chatgpt2api-h](https://github.com/orangewoker/chatgpt2api-h) · `d1e8ed4a0607` | Codex 精确选择 Flare/Sunburst | [模型表](https://github.com/orangewoker/chatgpt2api-h/blob/d1e8ed4a0607abd101e079ae9e9d4f8f83297dce/utils/helper.py#L34-L40)、[工具请求](https://github.com/orangewoker/chatgpt2api-h/blob/d1e8ed4a0607abd101e079ae9e9d4f8f83297dce/services/openai_backend_api.py#L777-L808)、[请求字段测试](https://github.com/orangewoker/chatgpt2api-h/blob/d1e8ed4a0607abd101e079ae9e9d4f8f83297dce/test/test_gif_output.py#L29-L71) | GIF 参数放入图片工具；其 Web 2.6 名称仍是兼容别名，帧数规则不能原样照搬 |
| [jiawen-afk/chatgpt2api](https://github.com/jiawen-afk/chatgpt2api) · `7ab8c2028113` | Web prepare/conversation 保留两个具体型号 | [原名映射](https://github.com/jiawen-afk/chatgpt2api/blob/7ab8c20281133f8e78f54b8c762a604e702abebb/services/openai_backend_api.py#L693-L702)、[发送](https://github.com/jiawen-afk/chatgpt2api/blob/7ab8c20281133f8e78f54b8c762a604e702abebb/services/openai_backend_api.py#L1158-L1168)、[旧缓存回归](https://github.com/jiawen-afk/chatgpt2api/blob/7ab8c20281133f8e78f54b8c762a604e702abebb/test/test_multi_image_results.py#L270-L294) | 旧模型缓存不能覆盖新型号；该 fork 的旧 Codex 通道不计为 2.6 |
| [mxw13579/chatgpt2api](https://github.com/mxw13579/chatgpt2api) · `d3fa3571eb04` | Web 原名透传与生成/编辑返回 | [原名映射](https://github.com/mxw13579/chatgpt2api/blob/d3fa3571eb045f2f9e83a1a22f755dfe373ea026/services/openai_backend_api.py#L694-L703)、[发送](https://github.com/mxw13579/chatgpt2api/blob/d3fa3571eb045f2f9e83a1a22f755dfe373ea026/services/openai_backend_api.py#L1146-L1156)、[返回](https://github.com/mxw13579/chatgpt2api/blob/d3fa3571eb045f2f9e83a1a22f755dfe373ea026/services/protocol/conversation.py#L1351-L1367) | 与上一项共享思路；单独核查的不同仓库及固定提交 |
| [IFuZYI/chatgpt2api](https://github.com/IFuZYI/chatgpt2api) · `af7bef567604` | Go 重写的 Web 图片链精确传递版本 slug（上游模型名） | [模型映射](https://github.com/IFuZYI/chatgpt2api/blob/af7bef567604877e0e6d452c64ed4d6ee8208004/internal/upstream/image_chain.go#L28-L60)、[发送](https://github.com/IFuZYI/chatgpt2api/blob/af7bef567604877e0e6d452c64ed4d6ee8208004/internal/upstream/image_chain.go#L167-L229)、[结果返回](https://github.com/IFuZYI/chatgpt2api/blob/af7bef567604877e0e6d452c64ed4d6ee8208004/internal/protocol/image_generate.go#L306-L348) | 2.6 不受文本模型目录缺项影响；维护者有实测声明，本轮未复现 |
| [lc2022560478/chatgpt2api](https://github.com/lc2022560478/chatgpt2api) · `17f7ef184980` | Web 专门分支原样使用两个 2.6 常量 | [精确映射](https://github.com/lc2022560478/chatgpt2api/blob/17f7ef18498055ebccb280f9ca065be1fce817ed/services/openai_backend_api.py#L624-L645)、[发送](https://github.com/lc2022560478/chatgpt2api/blob/17f7ef18498055ebccb280f9ca065be1fce817ed/services/openai_backend_api.py#L1055-L1101)、[结果返回](https://github.com/lc2022560478/chatgpt2api/blob/17f7ef18498055ebccb280f9ca065be1fce817ed/services/protocol/conversation.py#L471-L522) | 版本常量和请求保持一致；该 fork 的旧 Codex 通道不计为升级 |
| [fengqiaozhu/chatgpt2api](https://github.com/fengqiaozhu/chatgpt2api) · `bc779d032961` | `codex-gpt-image-2.6` 经配置精确选择 Flare/Sunburst | [配置限定](https://github.com/fengqiaozhu/chatgpt2api/blob/bc779d03296138744a2d798b0dd64eefeaa5a8a1/services/config.py#L522-L526)、[工具请求](https://github.com/fengqiaozhu/chatgpt2api/blob/bc779d03296138744a2d798b0dd64eefeaa5a8a1/services/openai_backend_api.py#L798-L824)、[调用及返回](https://github.com/fengqiaozhu/chatgpt2api/blob/bc779d03296138744a2d798b0dd64eefeaa5a8a1/services/protocol/conversation.py#L1264-L1297) | 裸别名的目标由配置控制；Web 名称仍共享默认模型，只计明确的 Codex 路线 |

另有 2 个有效实现位于非默认分支，使用时必须选择所列分支；不能据此写成其 main 已支持：

| 仓库 / 分支 / 固定提交 | 确认的路径与证据 | 参考边界 |
| --- | --- | --- |
| [gkingt/chatgpt2api](https://github.com/gkingt/chatgpt2api) · `my_1.5.0` · `8c319b2f2319` | [Web 原名](https://github.com/gkingt/chatgpt2api/blob/8c319b2f2319b5111e03ea6ea33a579d7887b81d/services/openai_backend_api.py#L623-L632)、[Codex 工具请求](https://github.com/gkingt/chatgpt2api/blob/8c319b2f2319b5111e03ea6ea33a579d7887b81d/services/openai_backend_api.py#L833-L873)、[调用与返回](https://github.com/gkingt/chatgpt2api/blob/8c319b2f2319b5111e03ea6ea33a579d7887b81d/services/protocol/conversation.py#L1312-L1354) | 明确标实验适配；上游拒绝时返回能力错误，不回落旧模型 |
| [AstonChenDev/chatgpt2api](https://github.com/AstonChenDev/chatgpt2api) · `my-custom` · `cc558d281da0` | [原名工具映射](https://github.com/AstonChenDev/chatgpt2api/blob/cc558d281da07d7d90bc840cf92bc3176334c148/utils/helper.py#L166-L170)、[工具请求](https://github.com/AstonChenDev/chatgpt2api/blob/cc558d281da07d7d90bc840cf92bc3176334c148/services/openai_backend_api.py#L908-L935)、[图片返回](https://github.com/AstonChenDev/chatgpt2api/blob/cc558d281da07d7d90bc840cf92bc3176334c148/services/protocol/conversation.py#L1380-L1411) | 两个规范 2.6 名称归 Codex；SSE（服务端事件流）逐条提取图片，账号来源必须协调 |

下列命中不应作为同等级证据：X-manist 的 2.6 是“不支持”的负断言；gxyo/Namas-pan 的名称仍映射默认旧路由；Peteroooooooo 在 2.6 失败后回落 `gpt-image-2`；xiangsl 将 Sunburst 也归为 Flare；hl128k 与 jiawen-afk 完全同 SHA。详细限制与其他同源项目均已列入实现核查文档。

## 3. 官方协议核查：两个具体变体与正确请求位置

官方 ID 是：

- [`gpt-image-2.6-sunburst`](https://developers.openai.com/api/docs/models/gpt-image-2.6-sunburst)。
- [`gpt-image-2.6-flare`](https://developers.openai.com/api/docs/models/gpt-image-2.6-flare)。

两个模型页列出直接 Images 生成/编辑端点。**它们也可以作为 Responses 的 `image_generation` 工具模型**，由 [Responses create schema](https://developers.openai.com/api/reference/resources/responses/methods/create) 直接确认；不能放进官方 Responses 顶层的文本 `model`。官方工具默认 Sunburst 是工具 schema 的约定，不自动成为本项目短别名或默认图片型号。

以下为本地既有 Codex 通道的请求对照，供理解不同通道的模型位置。当前网页账号适配使用 `/backend-api/f/conversation/prepare` 与 `/backend-api/f/conversation`，不使用下面这份 Codex 请求结构：

```json
{
  "model": "gpt-5.5",
  "tools": [
    {
      "type": "image_generation",
      "model": "gpt-image-2.6-sunburst",
      "action": "generate",
      "quality": "auto",
      "output_format": "png"
    }
  ],
  "stream": true
}
```

这是说明模型位置的请求片段，省略了现有鉴权、输入消息、工具选择和尺寸提示等字段。编辑时沿用本地已有参考图输入与 `action=edit`。该形态有 hp0912、FatalErrorR 的实际构造代码佐证；官方 API 文档并不能单独证明本地订阅账号的 `/backend-api/codex/responses` 权限。

[图像指南](https://developers.openai.com/api/docs/guides/image-generation#gpt-image-26) 中 `quality`（渲染质量）和 `complexity`（生成前规划复杂度）是独立字段。2.6 可以复用 `auto/low/medium/high/xhigh/max` 质量档；PNG 最小阶段无需强制新增 complexity。标准尺寸先验收 `auto`、`1024x1024`、`1536x1024`、`1024x1536`，不能把本地 2.5 的自定义尺寸规则说成已经验证的 2.6 原生 4K 能力。

这段属于官方 API / Codex 工具的协议对照；当前网页计划只沿用网页四档质量与尺寸提示，不据此宣称网页接受这些原生控制字段。

## 4. 本项目的网页账号最小改造

当前 `utils/image_models.py` 未注册任何 2.6 入口，模型检查为 false，生成入口返回 `400/model_not_found`。网页实现需要将新型号归到 Web 注册表，在两次网页请求中保留精确名称，并显式使用本地网页来源白名单。

| 本地文件与位置 | 必需改动 | 原因 |
| --- | --- | --- |
| [utils/image_models.py](https://github.com/fujunchao/chatgpt2api/blob/5927143ec4421886b5e1f563718b564c0bdf52d9/utils/image_models.py#L11) | 新增 Web 两个具体 ID 和明确映射到 Sunburst 的本地短名；新增网页 2.6 判定 | 一个模型真源驱动路由和目录，保持旧模型的各自通道 |
| [services/openai_backend_api.py](https://github.com/fujunchao/chatgpt2api/blob/5927143ec4421886b5e1f563718b564c0bdf52d9/services/openai_backend_api.py#L561) | `_image_model_slug` 先处理 2.6 原名；prepare 与 submit 使用同值、同 picture_v2 | 不能只加名称后仍映射为 gpt-5-3；保留现有网页协议与生产恢复 |
| [services/protocol/conversation.py](https://github.com/fujunchao/chatgpt2api/blob/5927143ec4421886b5e1f563718b564c0bdf52d9/services/protocol/conversation.py#L1364) | 新入口显式使用 source_type=web，刷新后重新校验来源和配额 | 复用 web/password/oauth_login 白名单，不照搬参考 fork 的空来源选号 |
| [utils/image_tokens.py](https://github.com/fujunchao/chatgpt2api/blob/5927143ec4421886b5e1f563718b564c0bdf52d9/utils/image_tokens.py#L348) 与 [ImageOutput](https://github.com/fujunchao/chatgpt2api/blob/5927143ec4421886b5e1f563718b564c0bdf52d9/services/protocol/conversation.py#L354) | 2.6 Web 有实际 usage 则保留，缺失标 unavailable | 不套旧图片引擎公式，不把请求型号当实际引擎身份 |
| [conversation.py 的错误处理](https://github.com/fujunchao/chatgpt2api/blob/5927143ec4421886b5e1f563718b564c0bdf52d9/services/protocol/conversation.py#L1543) | 保留 Web 型号权限、额度与认证错误；仅确认未提交时有界换其它网页账号，型号不变 | 不误删有效账号，不改旧模型或变体，不重复提交出图 |
| [web/src/lib/image-models.ts](https://github.com/fujunchao/chatgpt2api/blob/5927143ec4421886b5e1f563718b564c0bdf52d9/web/src/lib/image-models.ts#L1) 与 [模型目录](https://github.com/fujunchao/chatgpt2api/blob/5927143ec4421886b5e1f563718b564c0bdf52d9/services/protocol/openai_v1_models.py#L11) | 标识 Web，使用网页四档质量提示，目录只由合法网页账号生成 | 权限需要网页实测，不能直接套 Codex/API 六档原生质量声明 |
| [图片存储](https://github.com/fujunchao/chatgpt2api/blob/5927143ec4421886b5e1f563718b564c0bdf52d9/services/image_storage_service.py#L199) 与 [图片响应](https://github.com/fujunchao/chatgpt2api/blob/5927143ec4421886b5e1f563718b564c0bdf52d9/services/image_service.py#L53) | 保留实际 PNG/JPEG/WebP 静态字节，文件后缀和 MIME 一致；复查压缩、清理 | 网页不能原生指定输出格式，不能假定收到的一定是 PNG |

保留 `is_gpt_image_25_model` 和旧网页自动判定的精确语义，新的 2.6 Web 另行判定。当前采用 [网页专用计划](image26-web-account-adaptation-plan.zh-CN.md) 中三个入口和来源约束，已有 2.5 的路由不改写。

[网页专用计划](image26-web-account-adaptation-plan.zh-CN.md) 给出实施顺序、对应文件、映射示意和测试矩阵；[原本地评估](research/image26-local-assessment.zh-CN.md) 保留官方 API 与最初 Codex 候选方案的对照。本轮仅更新研究和计划文档，业务代码尚未改为 2.6。

## 5. 新能力分阶段处理

以下保留通用调研中的能力对照。当前网页实施的首期范围和后续开放条件以 [网页计划第 4 节](image26-web-account-adaptation-plan.zh-CN.md#4-参数能力的首期边界) 为准；API/Codex 工具的格式、帧数、复杂度和原生尺寸字段不能直接当作网页协议字段。

| 能力 | 应完成的扩展 | 当前证据边界 |
| --- | --- | --- |
| PNG 生成与编辑 | 先完成上述注册、参数、账号、用量、错误和界面一致性；核查实际输出 | 本地 PNG 工具请求与结果解析可复用，有直接 fork 源码佐证 |
| JPEG/WebP/GIF/SVG 输出 | 从请求、异步任务到存储、文件扩展名、MIME（媒体类型）和预览都记录真实格式 | 当前请求及保存链固定 PNG；只是改 output_format 会留下错误文件名/响应或动画丢失 |
| complexity | 作为独立参数贯通请求模型、协议、任务与前端 | 官方工具 schema 支持，仍需该订阅账号通道实测 |
| Web 指定 2.6 | 参考 jiawen-afk / mxw13579 的原名透传与旧缓存回归，在本地单独设计版本路由 | 本地目前 Web 使用 `gpt-5-3` + `picture_v2`；改展示名称不能证明具体图像引擎改变 |
| markup（编辑标注层） | 透明 PNG 标注层、原图尺寸与旋转校验、mask 互斥及真实上传通道 | 官方 Images 编辑有证据；本地已有 mask 合成不能等同原生 markup |

GIF 当前官方 [指南](https://developers.openai.com/api/docs/guides/image-generation#generate-animated-gif-output)、[生成](https://developers.openai.com/api/reference/resources/images/methods/generate)、[编辑](https://developers.openai.com/api/reference/resources/images/methods/edit) 与 Responses 工具 schema 为 **2–16 帧，默认 9**。工具帧间隔 **20–2000 ms**，默认 200；GIF 需要预览权限。生命周期事件流与 partial image（分段图像）流是不同能力，不能笼统禁止全部流式响应。

[SVG 指南](https://developers.openai.com/api/docs/guides/image-generation#generate-svg-output) 和生成 schema 有自己的 `n=1`、生成/编辑与条件作者模型规则；`svg.model` 不是所有 Images 请求无条件必填。相关源码和协议边界详见本地评估。现有两份 Image 2.6 草稿的“64 帧”“编辑统一禁止 GIF”“SVG 作者模型一律必填”“当前本地超分会处理输出”等结论，需按本轮实际证据修订。

## 6. 验证结果与落地验收

本轮已经运行现有代码基线：隔离副本、禁用外部网络的后端 **84 项测试通过**；前端 Bun **4 项测试、30 个断言通过**。测试覆盖现有模型路由、2.5 协议、Free/OAuth 网页入口、Codex 账号池、用量、任务、存储、多图与目录。全项目 TypeScript（类型检查）未完成，原因是本地缺少 `web/node_modules/typescript/bin/tsc`；没有为本次研究安装依赖。

这证明当前基线在所测范围内可用，**不代表 2.6 已实现或真实出图已验证**。实跑命令与准确测试范围见本地评估。

实现最小 PNG 改动后的验收应包含：

1. 精确路由与账号筛选：两变体和本地短名全部归 Web；合法网页登录来源可用，Codex/未知来源排除；旧 2.5 的各自通道保持预期。
2. 捕获实际请求：网页 prepare 和 submit 的 `model` 是同一精确变体，并带 picture_v2；参考图进入多模态编辑输入；失败时不改成旧模型重新生图。
3. 用量与错误：真实 usage 保留，缺失标 unavailable；403/429/无图片/已提交断流保留具体错误，不误删账号或重复提交。
4. 前端、目录、任务与响应：网页模型名与来源一致，多图去重与 Base64/URL 返回有效；静态图片的字节、MIME、文件后缀和实际尺寸正确。
5. 用当前实际使用的网页来源账号分别对两个变体做静态生成和编辑；核对两次网页请求的型号、返回元数据、用量与实际格式/尺寸。Free 和付费账号分别记录权限结果；上游若不提供引擎身份，结论限于“网页明确请求 2.6 并返回图片”。

当前仍需实测的关键点是本地账号的 2.6 权限、实际返回模型身份、自定义尺寸及 GIF/SVG 的通道权限；不应通过模型目录存在或画面效果猜测。

## 7. 研究附件

- [完整 fork 网络与分支清单](research/image26-fork-inventory.zh-CN.md)：全量分页、固定提交、默认与非默认筛查、不可解析条目。
- [当前网页账号适配计划](image26-web-account-adaptation-plan.zh-CN.md)：用户确认的实施路线、阶段、文件改动和验收条件。
- [网页通道证据](research/image26-web-channel-evidence.zh-CN.md)：7 个网页实现、来源隔离与原生参数边界。
- [逐仓库适配与反例](research/image26-fork-implementations.zh-CN.md)：10 个直接 fork 的完整调用链、测试与来源；其他同源项目另列。
- [官方协议与本地最小改造](research/image26-local-assessment.zh-CN.md)：本地文件/行号、未应用的差异示例、格式扩展与基线复现命令。
