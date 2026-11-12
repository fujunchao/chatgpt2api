# Image 2.6：fork 实现逐仓库核查

核查日期：2026-11-12，Asia/Shanghai。本文主表核查默认分支的固定提交，另单列两个非默认分支的有效实现；完整 fork 和分支清单见同目录的 `image26-fork-inventory.zh-CN.md`。

已确认 **8 个不同直接 fork 有静态完整生成链**：请求接受 Image 2.6 的名称，指定 2.6 的具体上游模型，并将图片结果返回。这 8 个仓库的 GitHub `parent` 和 `source` 均为 `basketikun/chatgpt2api`，默认分支均为 `main`，HEAD 彼此不同。它们并非 8 套完全独立发明，尤其 `jiawen-afk` 与 `mxw13579` 共享部分实现。这里的确认是源码核查；没有使用真实账号替这 8 个仓库逐一出图，不能将代码支持写成 8 次线上实测。

全量非默认分支检查又确认 `gkingt` 与 `AstonChenDev` 的两条完整路径。因此默认与非默认分支合计，本文详细核查 **10 个不同直接 fork 的代码级 2.6 指定路径**，没有使用同 SHA 镜像或只改别名的仓库凑数。后二者的 `main` 没有对应适配，使用时必须选择文中指定分支。

## 1. 八个直接 fork 的证据

| 仓库 | 固定 HEAD | 已指定的 2.6 路径 | 核查边界 |
| --- | --- | --- | --- |
| [FatalErrorR/chatgpt2api](https://github.com/FatalErrorR/chatgpt2api) | `53119b5c4682c5606c9b4c80ad9d76d64105686e` | Web 原 ID；Codex `tools[0].model` 使用 2.6 映射 | 静态生成、编辑链已追踪；GIF 另有字段，但不能据此声称全部新能力已验证 |
| [hp0912/chatgpt2api](https://github.com/hp0912/chatgpt2api) | `e5bae8714da06c4e3676dd00d04bd56266c35d64` | Web 原 ID；`codex-` 名称映射到同名 2.6 图片工具 | 静态 PNG；未知 Codex 模型明确报错 |
| [orangewoker/chatgpt2api-h](https://github.com/orangewoker/chatgpt2api-h) | `d1e8ed4a0607abd101e079ae9e9d4f8f83297dce` | Codex 三个 2.6 名称映射到 Flare/Sunburst 工具 | **仅 Codex 路径计入**；普通 Web 的 2.6 名称仍是兼容别名 |
| [jiawen-afk/chatgpt2api](https://github.com/jiawen-afk/chatgpt2api) | `7ab8c20281133f8e78f54b8c762a604e702abebb` | Web `prepare`、`conversation` 保留 Flare/Sunburst 原名 | 不把其固定旧模型的 Codex 通道计为 2.6；有旧目录缓存回归测试 |
| [mxw13579/chatgpt2api](https://github.com/mxw13579/chatgpt2api) | `d3fa3571eb045f2f9e83a1a22f755dfe373ea026` | Web `prepare`、`conversation` 保留 Flare/Sunburst 原名 | 与上一项有共享代码，仍是不同仓库及不同 HEAD |
| [IFuZYI/chatgpt2api](https://github.com/IFuZYI/chatgpt2api) | `af7bef567604877e0e6d452c64ed4d6ee8208004` | Go Web 图片链将 2.6 名称作为上游 slug 传递 | 维护者文档声称三名称已实测；本轮没有复现实测 |
| [lc2022560478/chatgpt2api](https://github.com/lc2022560478/chatgpt2api) | `17f7ef18498055ebccb280f9ca065be1fce817ed` | Web 两个 2.6 常量经专门分支原样传递 | 普通 Codex 通道仍使用旧模型；仅 Web 2.6 路径计入 |
| [fengqiaozhu/chatgpt2api](https://github.com/fengqiaozhu/chatgpt2api) | `bc779d03296138744a2d798b0dd64eefeaa5a8a1` | Codex `codex-gpt-image-2.6` 经独立配置选 Flare/Sunburst，传入图片工具 | **仅 Codex 路径计入**；Web 三名称同路由；配置选择变体，不接受后缀形式的 Codex 别名 |

各项 GitHub 归属均独立读取第一方元数据，可分别复核：
[FatalErrorR](https://api.github.com/repos/FatalErrorR/chatgpt2api)、[hp0912](https://api.github.com/repos/hp0912/chatgpt2api)、[orangewoker](https://api.github.com/repos/orangewoker/chatgpt2api-h)、[jiawen-afk](https://api.github.com/repos/jiawen-afk/chatgpt2api)、[mxw13579](https://api.github.com/repos/mxw13579/chatgpt2api)、[IFuZYI](https://api.github.com/repos/IFuZYI/chatgpt2api)、[lc2022560478](https://api.github.com/repos/lc2022560478/chatgpt2api)、[fengqiaozhu](https://api.github.com/repos/fengqiaozhu/chatgpt2api)。这些 API 元数据会变化，本文源码证据以固定 SHA 为准。

### 1.1 FatalErrorR：Web 与 Codex 分别映射

- 模型定义：[`utils/helper.py:22-44`](https://github.com/FatalErrorR/chatgpt2api/blob/53119b5c4682c5606c9b4c80ad9d76d64105686e/utils/helper.py#L22-L44) 定义 Web 两个 2.6 ID，以及 Codex 三个本地名称。裸 `codex-gpt-image-2.6` 默认选 Flare；明确的 `-sunburst` 保留 Sunburst。
- Web 映射：[`resolve_image_upstream_model:163-178`](https://github.com/FatalErrorR/chatgpt2api/blob/53119b5c4682c5606c9b4c80ad9d76d64105686e/utils/helper.py#L163-L178) 对 2.6 版本返回原名；默认旧模型的设置不会覆盖它。
- Codex 请求：[`services/openai_backend_api.py:887-929`](https://github.com/FatalErrorR/chatgpt2api/blob/53119b5c4682c5606c9b4c80ad9d76d64105686e/services/openai_backend_api.py#L887-L929) 将 `codex_tool_model(model)` 写入 `tools[0].model`，顶层仍为调用图片工具的文本模型。输入有参考图时 `action=edit`，否则 `generate`。
- 返回链：[`services/protocol/conversation.py:1356-1385`](https://github.com/FatalErrorR/chatgpt2api/blob/53119b5c4682c5606c9b4c80ad9d76d64105686e/services/protocol/conversation.py#L1356-L1385) 将 `request.model` 传到后端，提取 `image_generation_call.result`，交给 `format_image_result` 返回。
- 可借鉴：版本与来源分开定义；但裸名称的 Flare 默认属于该 fork 的本地约定，不应与官方默认混同。GIF 分支在工具内部写 `output_format`、`frame_count` 和 `frame_duration_ms`；其具体限制需要再与当前官方协议核对。

### 1.2 hp0912：统一 Web ID 与 Codex ID 的映射

- 模型定义：[`utils/helper.py:17-34`](https://github.com/hp0912/chatgpt2api/blob/e5bae8714da06c4e3676dd00d04bd56266c35d64/utils/helper.py#L17-L34) 将版本化 Web ID 纳入一张表，再由 `codex-{model}` 生成对应 Codex 映射。
- Web 请求保留原名：[`services/openai_backend_api.py:571-584`](https://github.com/hp0912/chatgpt2api/blob/e5bae8714da06c4e3676dd00d04bd56266c35d64/services/openai_backend_api.py#L571-L584) 只有旧 `gpt-image-2` 使用默认配置，其余版本保留原 ID。
- Codex 实际请求：[`services/openai_backend_api.py:781-811`](https://github.com/hp0912/chatgpt2api/blob/e5bae8714da06c4e3676dd00d04bd56266c35d64/services/openai_backend_api.py#L781-L811) 查 `CODEX_IMAGE_MODELS[base_model]`；查不到立即报错，查到后写 `tools[0].model`。例如 `codex-gpt-image-2.6-sunburst` 对应 `gpt-image-2.6-sunburst`。
- 返回链：[`services/protocol/conversation.py:1263-1288`](https://github.com/hp0912/chatgpt2api/blob/e5bae8714da06c4e3676dd00d04bd56266c35d64/services/protocol/conversation.py#L1263-L1288) 保留 `request.model`，提取内联图片并返回 Base64/URL。
- Responses 兼容入口：[`openai_v1_response.py:425-446`](https://github.com/hp0912/chatgpt2api/blob/e5bae8714da06c4e3676dd00d04bd56266c35d64/services/protocol/openai_v1_response.py#L425-L446) 单独读取 `tool.model`，没有将顶层文本模型当作最终图片模型。
- 可借鉴：模型注册、账号来源和实际工具模型使用同一映射；未知模型不静默回退。

### 1.3 orangewoker：Codex 的真实模型字段与 GIF 参数

- 模型定义：[`utils/helper.py:34-40`](https://github.com/orangewoker/chatgpt2api-h/blob/d1e8ed4a0607abd101e079ae9e9d4f8f83297dce/utils/helper.py#L34-L40) 明确给出三项 Codex 2.6 映射，裸名称默认 Flare。
- 发送链：[`services/openai_backend_api.py:777-808`](https://github.com/orangewoker/chatgpt2api-h/blob/d1e8ed4a0607abd101e079ae9e9d4f8f83297dce/services/openai_backend_api.py#L777-L808) 将具体 2.6 模型写入 `tools[0].model`。GIF 请求另外写工具内的 `output_format=gif`、`frame_count` 和 `frame_duration_ms`。
- 返回链：[`services/protocol/conversation.py:1330-1367`](https://github.com/orangewoker/chatgpt2api-h/blob/d1e8ed4a0607abd101e079ae9e9d4f8f83297dce/services/protocol/conversation.py#L1330-L1367) 将模型及格式参数传至后端，取得内联图片，再按输出格式交给结果格式化。
- 测试证据：[`test/test_gif_output.py:29-71`](https://github.com/orangewoker/chatgpt2api-h/blob/d1e8ed4a0607abd101e079ae9e9d4f8f83297dce/test/test_gif_output.py#L29-L71) 既测试套餐前缀的映射，也截取实际构造的 `urllib` 请求数据，检查工具模型和 GIF 参数。本文确认这些测试存在，没有声称本轮运行了外部仓库测试。
- 限制：[`CHANGELOG.md:15-21`](https://github.com/orangewoker/chatgpt2api-h/blob/d1e8ed4a0607abd101e079ae9e9d4f8f83297dce/CHANGELOG.md#L15-L21) 已明确 Web 2.6 仍是兼容别名，不能将其 Web 路径计作 Flare/Sunburst 精确选择。其 GIF 帧数校验允许到 64，不能直接套用到本项目的当前官方协议。

### 1.4 jiawen-afk：网页原名透传与旧缓存兼容

- 模型注册：[`utils/helper.py:20-32`](https://github.com/jiawen-afk/chatgpt2api/blob/7ab8c20281133f8e78f54b8c762a604e702abebb/utils/helper.py#L20-L32) 和 [`services/config.py:85-95`](https://github.com/jiawen-afk/chatgpt2api/blob/7ab8c20281133f8e78f54b8c762a604e702abebb/services/config.py#L85-L95) 同时新增两个 2.6 名称。
- 请求入口：[`openai_v1_image_generations.py:16-41`](https://github.com/jiawen-afk/chatgpt2api/blob/7ab8c20281133f8e78f54b8c762a604e702abebb/services/protocol/openai_v1_image_generations.py#L16-L41) 把指定模型放入 `ConversationRequest`，再经过账号池生成与结果收集。
- 后端映射与发送：[`openai_backend_api.py:693-702`](https://github.com/jiawen-afk/chatgpt2api/blob/7ab8c20281133f8e78f54b8c762a604e702abebb/services/openai_backend_api.py#L693-L702) 返回版本化原名；[`prepare:1017-1032`](https://github.com/jiawen-afk/chatgpt2api/blob/7ab8c20281133f8e78f54b8c762a604e702abebb/services/openai_backend_api.py#L1017-L1032) 与 [`start:1158-1168`](https://github.com/jiawen-afk/chatgpt2api/blob/7ab8c20281133f8e78f54b8c762a604e702abebb/services/openai_backend_api.py#L1158-L1168) 均使用此结果作为 Web 请求的 `model`。
- 返回链：[`services/protocol/conversation.py:1366-1382`](https://github.com/jiawen-afk/chatgpt2api/blob/7ab8c20281133f8e78f54b8c762a604e702abebb/services/protocol/conversation.py#L1366-L1382) 下载已生成图片、编码后调用 `format_image_result`。
- 有意义的回归：[`test_multi_image_results.py:270-294`](https://github.com/jiawen-afk/chatgpt2api/blob/7ab8c20281133f8e78f54b8c762a604e702abebb/test/test_multi_image_results.py#L270-L294) 让模型缓存仅保留旧 `gpt-image-2`，再检查两个 2.6 型号在 `prepare` 与生成/编辑实际请求中仍被保留。
- 限制：该 fork 的 Codex 图片工具仍固定为旧 `gpt-image-2`；这里确认的是 Web 路径。

### 1.5 mxw13579：与上一项共享思路，但独立固定快照

- 模型注册：[`utils/helper.py:20-32`](https://github.com/mxw13579/chatgpt2api/blob/d3fa3571eb045f2f9e83a1a22f755dfe373ea026/utils/helper.py#L20-L32)。
- 后端映射：[`openai_backend_api.py:694-703`](https://github.com/mxw13579/chatgpt2api/blob/d3fa3571eb045f2f9e83a1a22f755dfe373ea026/services/openai_backend_api.py#L694-L703) 对版本化 Web 模型返回原名；[`prepare:1006-1015`](https://github.com/mxw13579/chatgpt2api/blob/d3fa3571eb045f2f9e83a1a22f755dfe373ea026/services/openai_backend_api.py#L1006-L1015) 与 [`start:1146-1156`](https://github.com/mxw13579/chatgpt2api/blob/d3fa3571eb045f2f9e83a1a22f755dfe373ea026/services/openai_backend_api.py#L1146-L1156) 保留该型号。
- 返回链：[`conversation.py:1351-1367`](https://github.com/mxw13579/chatgpt2api/blob/d3fa3571eb045f2f9e83a1a22f755dfe373ea026/services/protocol/conversation.py#L1351-L1367) 下载图片并返回标准结果。
- 测试：[`test_multi_image_results.py:270-294`](https://github.com/mxw13579/chatgpt2api/blob/d3fa3571eb045f2f9e83a1a22f755dfe373ea026/test/test_multi_image_results.py#L270-L294) 同样覆盖旧缓存及生成/编辑实际请求字段。其 HEAD 与 `jiawen-afk` 不同，不能把两份代码说成两种独立协议。

### 1.6 IFuZYI：Go 重写版本，2.6 专门绕过默认模型映射

- 注册：[`internal/protocol/models.go:14-25`](https://github.com/IFuZYI/chatgpt2api/blob/af7bef567604877e0e6d452c64ed4d6ee8208004/internal/protocol/models.go#L14-L25) 同时列入裸 2.6 与两个变体。注释说明网页图片 slug 不一定在文本 `/backend-api/models` 目录中出现。
- 兼容 API 输入：[`internal/api/image_generation_routes.go:93-101`](https://github.com/IFuZYI/chatgpt2api/blob/af7bef567604877e0e6d452c64ed4d6ee8208004/internal/api/image_generation_routes.go#L93-L101) 将客户端模型放入 `ImageRequest`；编辑分支在同文件 `126-134` 保留模型和参考图。
- 映射：[`internal/upstream/image_chain.go:28-60`](https://github.com/IFuZYI/chatgpt2api/blob/af7bef567604877e0e6d452c64ed4d6ee8208004/internal/upstream/image_chain.go#L28-L60) 对 2.6 名称直接返回 `baseModel`，明确避免把它们全变为 `defaultUpstream`。
- 发送：[`prepare:106-123`](https://github.com/IFuZYI/chatgpt2api/blob/af7bef567604877e0e6d452c64ed4d6ee8208004/internal/upstream/image_chain.go#L106-L123) 与 [`generate:167-229`](https://github.com/IFuZYI/chatgpt2api/blob/af7bef567604877e0e6d452c64ed4d6ee8208004/internal/upstream/image_chain.go#L167-L229) 依此写 Web `model`；[`StreamImage:396-453`](https://github.com/IFuZYI/chatgpt2api/blob/af7bef567604877e0e6d452c64ed4d6ee8208004/internal/upstream/image_chain.go#L396-L453) 对模型分流，不混用普通文本端点。
- 返回：[`internal/protocol/image_generate.go:306-348`](https://github.com/IFuZYI/chatgpt2api/blob/af7bef567604877e0e6d452c64ed4d6ee8208004/internal/protocol/image_generate.go#L306-L348) 下载图片，写 `b64_json`，再 `FormatImageResult` 返回。
- 验证等级：[`image_model_settings_test.go:38-49`](https://github.com/IFuZYI/chatgpt2api/blob/af7bef567604877e0e6d452c64ed4d6ee8208004/internal/upstream/image_model_settings_test.go#L38-L49) 是防误映射的源码测试；[`docs/feature-status.md:77-85`](https://github.com/IFuZYI/chatgpt2api/blob/af7bef567604877e0e6d452c64ed4d6ee8208004/docs/feature-status.md#L77-L85) 是维护者“三个名称已实测出图”的第一方声明。本轮仅核查声明，未使用其账号复现。

### 1.7 lc2022560478：常量化版本与完整 Web 返回链

- 版本常量：[`utils/helper.py:17-27`](https://github.com/lc2022560478/chatgpt2api/blob/17f7ef18498055ebccb280f9ca065be1fce817ed/utils/helper.py#L17-L27) 定义 `IMAGE_26_FLARE_MODEL`、`IMAGE_26_SUNBURST_MODEL`，纳入注册表。
- 入口：[`openai_v1_image_generations.py:16-44`](https://github.com/lc2022560478/chatgpt2api/blob/17f7ef18498055ebccb280f9ca065be1fce817ed/services/protocol/openai_v1_image_generations.py#L16-L44) 将客户端模型放入 `ConversationRequest`，通过账号池生成，再收集标准结果。
- 精确映射：[`openai_backend_api.py:624-645`](https://github.com/lc2022560478/chatgpt2api/blob/17f7ef18498055ebccb280f9ca065be1fce817ed/services/openai_backend_api.py#L624-L645) 对两个 2.6 常量专门返回 `base_model`。
- 发送：[`prepare:939-950`](https://github.com/lc2022560478/chatgpt2api/blob/17f7ef18498055ebccb280f9ca065be1fce817ed/services/openai_backend_api.py#L939-L950) 与 [`start:1055-1101`](https://github.com/lc2022560478/chatgpt2api/blob/17f7ef18498055ebccb280f9ca065be1fce817ed/services/openai_backend_api.py#L1055-L1101) 都使用精确映射结果。
- 返回：[`conversation.py:471-522`](https://github.com/lc2022560478/chatgpt2api/blob/17f7ef18498055ebccb280f9ca065be1fce817ed/services/protocol/conversation.py#L471-L522) 下载图片并返回 Base64/URL；已生成结果下载失败会给出具体错误，避免再生一张图片。
- 测试：[`test_account_image_capabilities.py:102-107`](https://github.com/lc2022560478/chatgpt2api/blob/17f7ef18498055ebccb280f9ca065be1fce817ed/test/test_account_image_capabilities.py#L102-L107) 检查映射保留两个具体 2.6 ID。计入的是 Web 通道，其旧 Codex 图片工具不能因此视作升级。

### 1.8 fengqiaozhu：配置选择变体的 Codex 2.6 通道

- 注册：[`utils/helper.py:17-35`](https://github.com/fengqiaozhu/chatgpt2api/blob/bc779d03296138744a2d798b0dd64eefeaa5a8a1/utils/helper.py#L17-L35) 定义 `codex-gpt-image-2.6` 及套餐前缀，识别为 Codex 通道。
- 配置：[`services/config.py:522-526`](https://github.com/fengqiaozhu/chatgpt2api/blob/bc779d03296138744a2d798b0dd64eefeaa5a8a1/services/config.py#L522-L526) 只允许 `gpt-image-2.6-flare` 与 `gpt-image-2.6-sunburst`，默认选 Flare。客户端使用裸 Codex 别名，由管理员配置决定变体。
- 调用与返回：[`conversation.py:1264-1297`](https://github.com/fengqiaozhu/chatgpt2api/blob/bc779d03296138744a2d798b0dd64eefeaa5a8a1/services/protocol/conversation.py#L1264-L1297) 将配置值传为 `image_model`，再提取内联结果和返回标准 Base64/URL。
- 实际发送字段：[`openai_backend_api.py:798-824`](https://github.com/fengqiaozhu/chatgpt2api/blob/bc779d03296138744a2d798b0dd64eefeaa5a8a1/services/openai_backend_api.py#L798-L824) 写入 `tools[0].model`，参考图有无分别选择 `edit`/`generate`，输出 PNG。
- 测试与边界：[`test_image_model_26.py:85-98`](https://github.com/fengqiaozhu/chatgpt2api/blob/bc779d03296138744a2d798b0dd64eefeaa5a8a1/test/test_image_model_26.py#L85-L98) 证明 Codex 别名与套餐前缀使用配置的 Sunburst；普通 Web 2.6 名称不走该通道。Web 变体未精确选择的问题列于下表，不能因 Codex 支持而说 Web 也完整支持。

## 2. 搜索命中但需要降低等级的路径

| 仓库与固定 SHA | 核查结果 | 第一方证据 |
| --- | --- | --- |
| Namas-pan/chatgpt2api @ `39b58e769aff1f15f1a81471a0750e461174338e` | 裸 2.6 只是别名，仍发送 `config.default_upstream_model_name`；未形成精确 2.6 选择 | [backend:571-587](https://github.com/Namas-pan/chatgpt2api/blob/39b58e769aff1f15f1a81471a0750e461174338e/services/openai_backend_api.py#L571-L587) |
| gxyo/chatgpt2api @ `65302d7a19ca77eafd28cd3bdedabf741865820a` | 两变体也被映射到同一默认模型，不能把“接受 2.6 名称”当成精确选择 | [backend:811-828](https://github.com/gxyo/chatgpt2api/blob/65302d7a19ca77eafd28cd3bdedabf741865820a/services/openai_backend_api.py#L811-L828) |
| fengqiaozhu/chatgpt2api 的 **Web 路径** @ `bc779d03296138744a2d798b0dd64eefeaa5a8a1` | Web 三名称共享默认路由，不可当精确变体选择；有效的 Codex 通道已在主表单独确认 | [Web 配置:516-526](https://github.com/fengqiaozhu/chatgpt2api/blob/bc779d03296138744a2d798b0dd64eefeaa5a8a1/services/config.py#L516-L526)、[声明](https://github.com/fengqiaozhu/chatgpt2api/blob/bc779d03296138744a2d798b0dd64eefeaa5a8a1/CHANGELOG.md#L7) |
| Peteroooooooo/chatgpt2api @ `a73e13045fdf79e38b52a71a427dd4e7071fa3e7` | 先试 2.6 Sunburst，但遇 400/404 后降为旧 `gpt-image-2`；有日志但客户端未必知道实际型号，不能按“稳定精确 2.6”计入主表 | [backend:833-874](https://github.com/Peteroooooooo/chatgpt2api/blob/a73e13045fdf79e38b52a71a427dd4e7071fa3e7/services/openai_backend_api.py#L833-L874)、[降级测试:54-59](https://github.com/Peteroooooooo/chatgpt2api/blob/a73e13045fdf79e38b52a71a427dd4e7071fa3e7/test/test_image_upstream_model.py#L54-L59) |
| xiangsl/chatgpt2api @ `50d84c486dfa27fffde54538e8e47dc09fde540f` | 独立 `image_26.py` 浏览器协议有参考价值；Web `model=auto`，所有 2.6 别名包括 Sunburst 被归为 Flare，不能直接声称两个变体都可精确选择 | [helper:21-27](https://github.com/xiangsl/chatgpt2api/blob/50d84c486dfa27fffde54538e8e47dc09fde540f/utils/helper.py#L21-L27)、[独立协议:1-35](https://github.com/xiangsl/chatgpt2api/blob/50d84c486dfa27fffde54538e8e47dc09fde540f/services/protocol/image_26.py#L1-L35)、[测试:21-29](https://github.com/xiangsl/chatgpt2api/blob/50d84c486dfa27fffde54538e8e47dc09fde540f/test/test_image_26_protocol.py#L21-L29) |
| leiseek/chatgpt2api @ `907349ab9607437e83a7376e18e23311c51404bb` | 注册裸 2.6，并对 Codex 去前缀后发送裸名；缺少两个官方变体的精确映射证据，默认 Web 动态路由不能确保 2.6 | [helper:23-37](https://github.com/leiseek/chatgpt2api/blob/907349ab9607437e83a7376e18e23311c51404bb/utils/helper.py#L23-L37)、[backend:843-861](https://github.com/leiseek/chatgpt2api/blob/907349ab9607437e83a7376e18e23311c51404bb/services/openai_backend_api.py#L843-L861) |
| X-manist/chatgpt2api @ `a4d1720dc291b0ae933065d55ec2193f840b8d69` | 2.6 命中来自明确的负断言，实际上不支持 | [test_gpt_image_25_model.py:29](https://github.com/X-manist/chatgpt2api/blob/a4d1720dc291b0ae933065d55ec2193f840b8d69/test/test_gpt_image_25_model.py#L29) |

`hl128k/chatgpt2api` 是 `jiawen-afk` 的后代，GitHub `source` 仍是 `basketikun/chatgpt2api`，HEAD 与 `jiawen-afk` 完全相同 `7ab8c202...`，可单独列作继承支持的仓库，但不能算新增方案，也未用于凑主表 8 个。归属见 [API](https://api.github.com/repos/hl128k/chatgpt2api)，继承的实际请求测试见 [固定源码](https://github.com/hl128k/chatgpt2api/blob/7ab8c20281133f8e78f54b8c762a604e702abebb/test/test_multi_image_results.py#L270-L294)。完整清单还包括 `jiawen-afk` 的其他后代，见 fork 清单文档。

## 3. 非默认分支中的两个额外有效实现

### 3.1 gkingt：my_1.5.0 分支，明确标记实验能力

仓库：[gkingt/chatgpt2api](https://github.com/gkingt/chatgpt2api)。实际检查分支 `my_1.5.0`，SHA `8c319b2f2319b5111e03ea6ea33a579d7887b81d`；默认 `main` 不包含此适配。GitHub [元数据](https://api.github.com/repos/gkingt/chatgpt2api) 的 parent/source 都是 `basketikun/chatgpt2api`。

- [`utils/helper.py:17-29`](https://github.com/gkingt/chatgpt2api/blob/8c319b2f2319b5111e03ea6ea33a579d7887b81d/utils/helper.py#L17-L29) 定义两个 Web 2.6 ID，以及对应的 Codex ID 和套餐前缀。
- Web 原名传递见 [`openai_backend_api.py:623-632`](https://github.com/gkingt/chatgpt2api/blob/8c319b2f2319b5111e03ea6ea33a579d7887b81d/services/openai_backend_api.py#L623-L632)。Codex 调用在 [`conversation.py:1312-1354`](https://github.com/gkingt/chatgpt2api/blob/8c319b2f2319b5111e03ea6ea33a579d7887b81d/services/protocol/conversation.py#L1312-L1354) 去掉 `codex-` 后把具体模型传为 `image_model`，返回标准图片结果；上游拒绝则返回能力错误，不回旧模型。
- [`openai_backend_api.py:833-873`](https://github.com/gkingt/chatgpt2api/blob/8c319b2f2319b5111e03ea6ea33a579d7887b81d/services/openai_backend_api.py#L833-L873) 把实际模型写到 `tools[0].model`，额外字段 `output_format`、`frame_count`、`frame_duration_ms` 和 `complexity` 也在图片工具内部。
- [`README.md:102-145`](https://github.com/gkingt/chatgpt2api/blob/8c319b2f2319b5111e03ea6ea33a579d7887b81d/README.md#L102-L145) 将其标为实验适配，明确“Image API 文档不是 Codex 订阅端点支持证明”。Web GIF 通过提示词请求，帧数/时长不保证严格遵守；Web SVG/复杂度未开放。这是本项目应借鉴的能力边界说明，而非真实账号可用性的证明。

### 3.2 AstonChenDev：my-custom 分支，canonical 2.6 ID 直接使用 Codex

仓库：[AstonChenDev/chatgpt2api](https://github.com/AstonChenDev/chatgpt2api)。实际检查分支 `my-custom`，SHA `cc558d281da07d7d90bc840cf92bc3176334c148`；默认 `main` 不包含此适配。GitHub [元数据](https://api.github.com/repos/AstonChenDev/chatgpt2api) 的 parent/source 都是 `basketikun/chatgpt2api`。

- [`utils/helper.py:23-27`](https://github.com/AstonChenDev/chatgpt2api/blob/cc558d281da07d7d90bc840cf92bc3176334c148/utils/helper.py#L23-L27) 将两个 2.6 规范名称归到 Codex 通道；[`codex_image_tool_model:166-170`](https://github.com/AstonChenDev/chatgpt2api/blob/cc558d281da07d7d90bc840cf92bc3176334c148/utils/helper.py#L166-L170) 对它们保留原名。
- [`openai_backend_api.py:908-935`](https://github.com/AstonChenDev/chatgpt2api/blob/cc558d281da07d7d90bc840cf92bc3176334c148/services/openai_backend_api.py#L908-L935) 将该映射写到 `tools[0].model`，参考图使用 `action=edit`，输出 PNG。
- [`conversation.py:1380-1411`](https://github.com/AstonChenDev/chatgpt2api/blob/cc558d281da07d7d90bc840cf92bc3176334c148/services/protocol/conversation.py#L1380-L1411) 保留请求模型，逐条消费 SSE、只收集图片结果并返回，减少一次保存全部事件造成的内存占用。
- [`test_account_image_capabilities.py:88-94`](https://github.com/AstonChenDev/chatgpt2api/blob/cc558d281da07d7d90bc840cf92bc3176334c148/test/test_account_image_capabilities.py#L88-L94) 确认两个 2.6 ID 使用 Codex 账号来源并保持同名工具模型。此实现不将相同名称当作 Web 名称使用，账号来源要与本地现有约定协调。

## 4. 同源衍生的额外参考，不混入直接 fork 数量

以下仓库也逐一读取元数据、默认分支和源代码；其当前 GitHub network 与 `basketikun` 不同或仓库已独立，不能当作上游的直接 fork 凑数量。

| 仓库与 SHA | 作用与限制 | 源码证据 |
| --- | --- | --- |
| zuelu/chatgpt2api @ `98d6d9ae50c562068e09b873f50be54eb3431725` | Codex 精确变体透传，裸名称默认 Sunburst；GIF/SVG 单独使用官方 Images API 账号池，适合作为后续能力扩展参考 | [来源声明](https://github.com/zuelu/chatgpt2api/blob/98d6d9ae50c562068e09b873f50be54eb3431725/README.md#L5)、[映射与返回:1316-1348](https://github.com/zuelu/chatgpt2api/blob/98d6d9ae50c562068e09b873f50be54eb3431725/services/protocol/conversation.py#L1316-L1348)、[真实工具字段:990-1015](https://github.com/zuelu/chatgpt2api/blob/98d6d9ae50c562068e09b873f50be54eb3431725/services/openai_backend_api.py#L990-L1015) |
| wangai14/chatgpt2api-portable @ `992c7168b1481bdef7f942f2bd519f16ba2df973` | 一张 Codex 映射表，明确静态 PNG 与真实账号未验证的边界；上游已变为 yukkcat | [helper:31-36](https://github.com/wangai14/chatgpt2api-portable/blob/992c7168b1481bdef7f942f2bd519f16ba2df973/utils/helper.py#L31-L36)、[工具字段:1096-1123](https://github.com/wangai14/chatgpt2api-portable/blob/992c7168b1481bdef7f942f2bd519f16ba2df973/services/openai_backend_api.py#L1096-L1123)、[验证等级:40-44](https://github.com/wangai14/chatgpt2api-portable/blob/992c7168b1481bdef7f942f2bd519f16ba2df973/PATCH_INFO.json#L40-L44) |
| camelys624/atelier @ `585cd8b97d257354b02a774c647c11f04a90dd61` | 复用原协议、重新组织前端和调度，2.6 默认定义为 Codex 来源，并将模型 ID 写到图片工具 | [模型表:11-15](https://github.com/camelys624/atelier/blob/585cd8b97d257354b02a774c647c11f04a90dd61/server/image-models.ts#L11-L15)、[实际模型字段:767-790](https://github.com/camelys624/atelier/blob/585cd8b97d257354b02a774c647c11f04a90dd61/adapter/protocol/services/openai_backend_api.py#L767-L790)、[协议出处:228](https://github.com/camelys624/atelier/blob/585cd8b97d257354b02a774c647c11f04a90dd61/README.md#L228) |
| 239573049/WebImage @ `a7c926ced41820af30a1d22ca5c79096f0a36d92` | Web 2.6 名称原样传递，并增加真实文件格式识别；当前 `fork=false` | [映射:614-632](https://github.com/239573049/WebImage/blob/a7c926ced41820af30a1d22ca5c79096f0a36d92/services/openai_backend_api.py#L614-L632)、[2.6测试:70-86](https://github.com/239573049/WebImage/blob/a7c926ced41820af30a1d22ca5c79096f0a36d92/test/test_web_image_models.py#L70-L86) |
| LanQin996/WebImage @ `940c9d952d2c1839e5e184fc864903a246240672` | 上一仓库的后代，版本名保留；GitHub `source=239573049/WebImage` | [版本定义](https://github.com/LanQin996/WebImage/blob/940c9d952d2c1839e5e184fc864903a246240672/utils/helper.py#L21-L25)、[映射](https://github.com/LanQin996/WebImage/blob/940c9d952d2c1839e5e184fc864903a246240672/services/openai_backend_api.py#L654-L690) |
| Fun-lovingMrZhang/WebImage @ `ccae91172e02e714dc8f62ea78eff876212d9dde` | 同属 WebImage network，2.6 注册和原名映射继承 | [版本定义](https://github.com/Fun-lovingMrZhang/WebImage/blob/ccae91172e02e714dc8f62ea78eff876212d9dde/utils/helper.py#L21-L25)、[映射](https://github.com/Fun-lovingMrZhang/WebImage/blob/ccae91172e02e714dc8f62ea78eff876212d9dde/services/openai_backend_api.py#L614-L632) |
| ProdanCristian/chatgpt2api @ `fe0b068d2b59b55d417cfc0a917ca5e6c40a9791` | 当前 parent/source 为 `yukkcat/chatgpt2api`；三个 2.6 名称仍映射为 Web `auto`，虽有 GIF 参数与格式保存，不代表精确 2.6 variant | [metadata](https://api.github.com/repos/ProdanCristian/chatgpt2api)、[映射:804-813](https://github.com/ProdanCristian/chatgpt2api/blob/fe0b068d2b59b55d417cfc0a917ca5e6c40a9791/services/openai_backend_api.py#L804-L813)、[明确的别名约定:30-38](https://github.com/ProdanCristian/chatgpt2api/blob/fe0b068d2b59b55d417cfc0a917ca5e6c40a9791/docs/maps/backend-map.md#L30-L38) |

## 5. 对本项目的实现启示

1. **精确选择应落到发送字段。** Web 请求的 `model` 与 Codex Responses 的顶层文本 `model`、图片 `tools[0].model` 是三个不同位置。模型目录、前端选项或 README 的改名不足以证明升级。
2. **集中模型版本及来源。** hp0912 的统一映射、FatalErrorR 的 Web/Codex 分表可以对照；本地应利用现有 `utils/image_models.py` 路由结构扩展，不复制多份硬编码列表。
3. **保持变体语义。** 显式 `-sunburst` 不应改成 Flare，显式 2.6 不应在 400/404 后自动回旧模型。若产品需要自动选择，另定义清楚的本地别名与实际模型返回信息。
4. **保护旧配置和缓存。** jiawen-afk / mxw13579 的旧缓存回归最接近本地升级问题：只存有旧模型的缓存也不能让 2.6 消失或被错误归为普通聊天。
5. **模型可路由不等于全部新能力。** 先验证静态生成、编辑、多图和 Base64/URL 返回；GIF/SVG、复杂度、标注、帧参数和文件 MIME/后缀应分别按真实通道验证。不要把普通账号可用、Codex 可用、官方 API 可用混为一个布尔值。

## 6. 未能确认的点

- 没有对上述 10 个 fork 逐一使用真实 ChatGPT/Codex 账号生成图片；源码测试与维护者“实测”的声明均已明确区分。
- Web 上游 model slug 与官方 API 模型 ID 可能出现不同的账号权限或稳定性；仅原名透传不能保证本项目的每个账号立即可用。
- 非默认分支扫描的最终完整范围由 fork 清单文档给出，本文主表都是固定的已核查默认分支，不使用搜索索引的“无命中”证明其他分支不存在支持。
- 外围 `imagegen-mcp` 的 2.6 更新声明不属于本项目上游 fork，未纳入计数。

检索过程使用了项目 chatgpt2api-search 技能，但其配置的 `127.0.0.1:8000/v1/search` 本轮拒绝连接；后续改用已授权 GitHub CLI 的第一方 API、代码搜索与固定 SHA 的 codeload 源码。未执行外部仓库的服务、安装脚本或真实生图接口。
