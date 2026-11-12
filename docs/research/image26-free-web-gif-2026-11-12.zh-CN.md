# Image 2.6 免费网页账号 GIF：上游、全部 fork 与本地适配方案

核查日期：2026-11-12，Asia/Shanghai。本地和远端基准为 `249b47117b9f851f8a3f01c03dec9ba26e15d6a0`，即 v0.16.5。

实施后更新：本报告保留实施前的源码调查结论；v0.17.0 已按 [阶段计划](../image26-gif-implementation-plan.zh-CN.md) 实现网页 GIF，并完成四项 Free/OAuth 真实动画验收。当前用法见 [GIF 接入说明](../image26-gif-guide.zh-CN.md)，实测原图、帧数和哈希见 [验收记录](image26-gif-acceptance-2026-11-12.zh-CN.md)。以下“尚未实施/尚未实测”均描述调研快照。

本项目已经接通 Image 2.6 的网页静态出图。GIF 的可行改造方向是：**在现有网页管线上增加实验性的 GIF 目标，用提示词描述动画，再按实际多帧 GIF 验收并保存原字节。** 本轮确认了 8 个不同 owner 的完整网页 2.6 适配 fork（派生仓库），其中 3 个有提示词 GIF 实现；这些源码和离线测试还不能证明免费网页账号拥有 GIF 权限。

建议优先采用 gkingt 的多帧校验思路和 jiawen-afk 的格式保存、等待预算，同时复用本项目现有的网页账号筛选与原会话恢复机制。官方 Image API 的 GIF 字段尚无对应网页协议证据，不能原样传给网页请求。本轮交付源码证据、改造方案和离线探针；当前业务代码仍为上述基准，免费 GIF 可用性需在完成适配后单独实测。

## 上游及全部公开 fork 的核查范围

[本项目 GitHub 元数据](https://api.github.com/repos/fujunchao/chatgpt2api)的 `parent`（直接上游）和 `source`（网络根仓库）均为 [basketikun/chatgpt2api](https://github.com/basketikun/chatgpt2api)。上游当前 `main` 固定提交为 `92dd80e91543157d36a4ddad60e765c5293760e9`，最后推送时间为 2026-10-25T11:19:02Z。

上游本体尚未适配 2.6：其[模型表](https://github.com/basketikun/chatgpt2api/blob/92dd80e91543157d36a4ddad60e765c5293760e9/utils/helper.py#L17)只有 `gpt-image-2` 和 `codex-gpt-image-2`；[工具请求](https://github.com/basketikun/chatgpt2api/blob/92dd80e91543157d36a4ddad60e765c5293760e9/services/openai_backend_api.py#L793-L797)仍选择 2.0 并固定 PNG。本轮重新下载上游归档，206 个非 NUL 文件未发现 2.6 标识；GIF 命中只是上传类型和后缀识别。

本轮重新获取[全部直接 fork 分页](https://api.github.com/repos/basketikun/chatgpt2api/forks?per_page=100&sort=newest)，再递归检查有后代的仓库，并刷新可访问仓库的全部默认与非默认分支头。

| 核查项 | 结果 |
| --- | --- |
| 直接分页 | 17 页，1,624 条记录 |
| 递归后代 | 17 个后代入口，额外 150 条记录 |
| 去重枚举 | 1,774 条 fork 记录 |
| 可访问并读取源码的仓库 | 1,745 个；父链全部追溯到上游 |
| 不可访问的仓库 | 29 个；本轮逐项 REST API 返回 404，未读取其源码 |
| 当前分支头 | 2,351 / 2,351；包含 sunnywang666 的全部 267 个分支 |
| 按固定提交去重后的源码 | 907 / 907：默认分支 347 个，非默认独有 560 个 |
| 归档复用 | 903 个远端仍指向同一 SHA（固定提交）的已核实源码快照 |
| 新提交 | 4 个重新下载并筛查；上游本体另行重新抓取 |
| 筛查失败、未补扫的超大文本候选 | 0 / 0 |
| 2.6 关键词候选 | 23 个仓库，其中含本项目，外部 22 个；关键词命中不等于已适配 |
| 深度源码比较 | 实际读取 14 个仓库，13 个同源 fork、1 个独立外围参考 |

GitHub 根仓库元数据的 `forks_count/network_count` 都是 1,745；递归枚举多出的 29 条记录恰为当前不可访问项。这里只说明本轮集合的数值关系，GitHub 没有说明具体不可访问原因。完整清单和逐项 404 记录见 [fork 清单](evidence/image26-gif-2026-11-12/fork-inventory.zh-CN.md)、[全部节点及分支](evidence/image26-gif-2026-11-12/forks.json)和[扫描摘要](evidence/image26-gif-2026-11-12/sha-scans.json)。

“全部筛查”指可访问仓库当前各分支头的规定文本源码范围：Python、Go、JS/TS、Markdown、JSON、YAML、TOML、网页和配置等已知后缀。二进制、未知后缀、压缩资源内部文件和只存在于历史提交的内容未纳入关键词筛查。无命中不能证明未公开部署或动态路由绝无 2.6 能力；完整请求链的结论来自以下人工深查。

## 至少 8 个完整网页 2.6 适配 fork

每行均核对了模型注册、模型映射、prepare（准备请求）和 submit（提交请求）：两个具体 2.6 变体进入网页图片会话，保留具体型号及 `picture_v2`（网页图片提示）。这里确认的是源码路径，真实账号权限和最终图片引擎身份另行记录。

| 仓库、分支、固定提交 | 模型与网页请求证据 | 当前 GIF 能力及验证程度 |
| --- | --- | --- |
| [jiawen-afk/chatgpt2api](https://github.com/jiawen-afk/chatgpt2api)，`main`，`7ab8c2028113` | [模型表](https://github.com/jiawen-afk/chatgpt2api/blob/7ab8c20281133f8e78f54b8c762a604e702abebb/utils/helper.py#L20-L38)；[映射](https://github.com/jiawen-afk/chatgpt2api/blob/7ab8c20281133f8e78f54b8c762a604e702abebb/services/openai_backend_api.py#L693-L703)；[准备](https://github.com/jiawen-afk/chatgpt2api/blob/7ab8c20281133f8e78f54b8c762a604e702abebb/services/openai_backend_api.py#L1017-L1032)；[提交](https://github.com/jiawen-afk/chatgpt2api/blob/7ab8c20281133f8e78f54b8c762a604e702abebb/services/openai_backend_api.py#L1158-L1170) | 提示词请求 GIF、动画校验、正确后缀与媒体类型、300 秒等待预算；GIF 专项测试为合成样本与请求替身，实测耗时注释未注明套餐。 |
| [mxw13579/chatgpt2api](https://github.com/mxw13579/chatgpt2api)，`main`，`d3fa3571eb04` | [模型表](https://github.com/mxw13579/chatgpt2api/blob/d3fa3571eb045f2f9e83a1a22f755dfe373ea026/utils/helper.py#L20-L38)；[映射](https://github.com/mxw13579/chatgpt2api/blob/d3fa3571eb045f2f9e83a1a22f755dfe373ea026/services/openai_backend_api.py#L694-L703)；[准备](https://github.com/mxw13579/chatgpt2api/blob/d3fa3571eb045f2f9e83a1a22f755dfe373ea026/services/openai_backend_api.py#L1005-L1015)；[提交](https://github.com/mxw13579/chatgpt2api/blob/d3fa3571eb045f2f9e83a1a22f755dfe373ea026/services/openai_backend_api.py#L1146-L1156) | 静态网页 2.6；当前分支没有 GIF 输出请求和动画验收。 |
| [lc2022560478/chatgpt2api](https://github.com/lc2022560478/chatgpt2api)，`main`，`17f7ef184980` | [模型表](https://github.com/lc2022560478/chatgpt2api/blob/17f7ef18498055ebccb280f9ca065be1fce817ed/utils/helper.py#L17-L27)；[映射](https://github.com/lc2022560478/chatgpt2api/blob/17f7ef18498055ebccb280f9ca065be1fce817ed/services/openai_backend_api.py#L624-L645)；[准备](https://github.com/lc2022560478/chatgpt2api/blob/17f7ef18498055ebccb280f9ca065be1fce817ed/services/openai_backend_api.py#L939-L953)；[提交](https://github.com/lc2022560478/chatgpt2api/blob/17f7ef18498055ebccb280f9ca065be1fce817ed/services/openai_backend_api.py#L1097-L1110) | 静态网页 2.6；当前分支没有 GIF 输出请求和动画验收。 |
| [hp0912/chatgpt2api](https://github.com/hp0912/chatgpt2api)，`main`，`e5bae8714da0` | [模型表](https://github.com/hp0912/chatgpt2api/blob/e5bae8714da06c4e3676dd00d04bd56266c35d64/utils/helper.py#L17-L34)；[映射](https://github.com/hp0912/chatgpt2api/blob/e5bae8714da06c4e3676dd00d04bd56266c35d64/services/openai_backend_api.py#L571-L584)；[准备](https://github.com/hp0912/chatgpt2api/blob/e5bae8714da06c4e3676dd00d04bd56266c35d64/services/openai_backend_api.py#L877-L890)；[提交](https://github.com/hp0912/chatgpt2api/blob/e5bae8714da06c4e3676dd00d04bd56266c35d64/services/openai_backend_api.py#L1022-L1031) | 静态网页 2.6；[维护者明确未实测网页新 ID](https://github.com/hp0912/chatgpt2api/blob/e5bae8714da06c4e3676dd00d04bd56266c35d64/README.md#L129-L130)，没有免费 GIF 证明。 |
| [FatalErrorR/chatgpt2api](https://github.com/FatalErrorR/chatgpt2api)，`main`，`53119b5c4682` | [模型表](https://github.com/FatalErrorR/chatgpt2api/blob/53119b5c4682c5606c9b4c80ad9d76d64105686e/utils/helper.py#L22-L44)；[映射](https://github.com/FatalErrorR/chatgpt2api/blob/53119b5c4682c5606c9b4c80ad9d76d64105686e/services/openai_backend_api.py#L676-L684)；[准备](https://github.com/FatalErrorR/chatgpt2api/blob/53119b5c4682c5606c9b4c80ad9d76d64105686e/services/openai_backend_api.py#L989-L1000)；[提交](https://github.com/FatalErrorR/chatgpt2api/blob/53119b5c4682c5606c9b4c80ad9d76d64105686e/services/openai_backend_api.py#L1157-L1166) | 提示词请求 GIF，只检查文件头；缺少真实动画验收，测试样本实际为单帧，WebDAV 保存还有错误媒体类型。 |
| [IFuZYI/chatgpt2api](https://github.com/IFuZYI/chatgpt2api)，`main`，`af7bef567604` | [模型表](https://github.com/IFuZYI/chatgpt2api/blob/af7bef567604877e0e6d452c64ed4d6ee8208004/internal/protocol/models.go#L14-L25)；[映射](https://github.com/IFuZYI/chatgpt2api/blob/af7bef567604877e0e6d452c64ed4d6ee8208004/internal/upstream/image_chain.go#L28-L60)；[准备](https://github.com/IFuZYI/chatgpt2api/blob/af7bef567604877e0e6d452c64ed4d6ee8208004/internal/upstream/image_chain.go#L111-L124)；[提交](https://github.com/IFuZYI/chatgpt2api/blob/af7bef567604877e0e6d452c64ed4d6ee8208004/internal/upstream/image_chain.go#L215-L257) | Go 网页静态通道；[维护者称静态出图已实测](https://github.com/IFuZYI/chatgpt2api/blob/af7bef567604877e0e6d452c64ed4d6ee8208004/docs/feature-status.md#L77-L85)，没有 Free 套餐和 GIF 的分层记录。 |
| [gkingt/chatgpt2api](https://github.com/gkingt/chatgpt2api)，`my_1.5.0`，`8c319b2f2319` | [模型表](https://github.com/gkingt/chatgpt2api/blob/8c319b2f2319b5111e03ea6ea33a579d7887b81d/utils/helper.py#L17-L29)；[映射](https://github.com/gkingt/chatgpt2api/blob/8c319b2f2319b5111e03ea6ea33a579d7887b81d/services/openai_backend_api.py#L621-L632)；[准备](https://github.com/gkingt/chatgpt2api/blob/8c319b2f2319b5111e03ea6ea33a579d7887b81d/services/openai_backend_api.py#L933-L945)；[提交](https://github.com/gkingt/chatgpt2api/blob/8c319b2f2319b5111e03ea6ea33a579d7887b81d/services/openai_backend_api.py#L1074-L1086) | 提示词请求 GIF、至少两帧验收、正确格式保存和网页来源隔离；[明确标为实验](https://github.com/gkingt/chatgpt2api/blob/8c319b2f2319b5111e03ea6ea33a579d7887b81d/README.md#L107-L113)，GIF 回归使用合成结果。 |
| [Micah123321/chatgpt2api](https://github.com/Micah123321/chatgpt2api)，`main`，`663175e6e0f2` | [模型表](https://github.com/Micah123321/chatgpt2api/blob/663175e6e0f2014e47ab324c7c3fbcf354c580e2/utils/helper.py#L20-L33)；[映射](https://github.com/Micah123321/chatgpt2api/blob/663175e6e0f2014e47ab324c7c3fbcf354c580e2/services/openai_backend_api.py#L684-L697)；[准备](https://github.com/Micah123321/chatgpt2api/blob/663175e6e0f2014e47ab324c7c3fbcf354c580e2/services/openai_backend_api.py#L1000-L1014)；[提交](https://github.com/Micah123321/chatgpt2api/blob/663175e6e0f2014e47ab324c7c3fbcf354c580e2/services/openai_backend_api.py#L1135-L1150) | 继承 jiawen 的静态通道并将裸名修正为 Flare；不同提交，但不是全新协议实现，当前没有 GIF 请求。 |

以上是 8 个仓库，不是 8 套独立协议。Micah 属于继承实现；另外检查的 hl128k 与 jiawen 的 HEAD 完全相同，没有将其计作新增方案。Micah 的裸名选择 Flare 是该 fork 的约定，本项目当前裸名固定 Sunburst，无需随它修改。

另核查了 3 个同源的 Codex 2.6 适配：[orangewoker/chatgpt2api-h 的 GIF 工具字段](https://github.com/orangewoker/chatgpt2api-h/blob/d1e8ed4a0607abd101e079ae9e9d4f8f83297dce/services/openai_backend_api.py#L775-L808)、[fengqiaozhu 的具体工具型号](https://github.com/fengqiaozhu/chatgpt2api/blob/bc779d03296138744a2d798b0dd64eefeaa5a8a1/services/openai_backend_api.py#L798-L824)、[AstonChenDev 的 my-custom 分支](https://github.com/AstonChenDev/chatgpt2api/blob/cc558d281da07d7d90bc840cf92bc3176334c148/services/openai_backend_api.py#L908-L935)。它们能说明工具链如何适配，但不能证明免费网页登录能力。gxyo 有 GIF 返回保留代码，然而[其 2.6 名称仍映射旧默认型号](https://github.com/gxyo/chatgpt2api/blob/65302d7a19ca77eafd28cd3bdedabf741865820a/services/openai_backend_api.py#L811-L828)，没有计入上述 8 个精确网页方案。239573049/WebImage 的第一方 API 当前 `fork=false`，只作为外围参考。

## 三个网页 GIF 实现中可采用的部分

**gkingt 最值得参考的是成功判定。** [动画提示词](https://github.com/gkingt/chatgpt2api/blob/8c319b2f2319b5111e03ea6ea33a579d7887b81d/services/protocol/conversation.py#L273-L290)配合[多帧校验](https://github.com/gkingt/chatgpt2api/blob/8c319b2f2319b5111e03ea6ea33a579d7887b81d/utils/image_formats.py#L100-L118)，要求真实 GIF 至少两帧。[实际构造请求的离线测试](https://github.com/gkingt/chatgpt2api/blob/8c319b2f2319b5111e03ea6ea33a579d7887b81d/test/test_web_image26.py#L26-L44)明确检查网页请求体没有 `output_format/frame_count`。其[来源测试](https://github.com/gkingt/chatgpt2api/blob/8c319b2f2319b5111e03ea6ea33a579d7887b81d/test/test_web_image26.py#L76-L89)保留网页 Token、密码、OAuth 来源并排除 Codex，这一思路本项目已经实现，应继续复用。

**jiawen 的等待和保存更完整。** [提示词](https://github.com/jiawen-afk/chatgpt2api/blob/7ab8c20281133f8e78f54b8c762a604e702abebb/services/protocol/conversation.py#L280-L298)明确以网页提示请求动画；[结果校验](https://github.com/jiawen-afk/chatgpt2api/blob/7ab8c20281133f8e78f54b8c762a604e702abebb/services/protocol/conversation.py#L340-L390)拒绝静态结果；[保存](https://github.com/jiawen-afk/chatgpt2api/blob/7ab8c20281133f8e78f54b8c762a604e702abebb/services/image_storage_service.py#L218-L243)保持 `.gif` 与 `image/gif`；[GIF 请求预算](https://github.com/jiawen-afk/chatgpt2api/blob/7ab8c20281133f8e78f54b8c762a604e702abebb/services/protocol/conversation.py#L1693-L1697)提升到 300 秒。[实测近三分钟的注释](https://github.com/jiawen-afk/chatgpt2api/blob/7ab8c20281133f8e78f54b8c762a604e702abebb/utils/helper.py#L41-L44)没有说明免费或付费套餐；[GIF 测试样本](https://github.com/jiawen-afk/chatgpt2api/blob/7ab8c20281133f8e78f54b8c762a604e702abebb/test/test_gif_output.py#L18-L21)是本地合成动画。

**FatalErrorR 只能按局部代码参考。** [提示词](https://github.com/FatalErrorR/chatgpt2api/blob/53119b5c4682c5606c9b4c80ad9d76d64105686e/services/protocol/conversation.py#L248-L263)已请求 GIF，但[结果处理](https://github.com/FatalErrorR/chatgpt2api/blob/53119b5c4682c5606c9b4c80ad9d76d64105686e/services/protocol/conversation.py#L331-L365)仅按文件头区分，缺少与 GIF 目标匹配的动画验收。本轮用 Pillow 读取其[固定测试样本](https://github.com/FatalErrorR/chatgpt2api/blob/53119b5c4682c5606c9b4c80ad9d76d64105686e/test/test_gif_output.py#L15-L37)，确认只有一帧。此外，[WebDAV 保存调用](https://github.com/FatalErrorR/chatgpt2api/blob/53119b5c4682c5606c9b4c80ad9d76d64105686e/services/image_storage_service.py#L222-L230)未传媒体类型，会使用[默认 image/png](https://github.com/FatalErrorR/chatgpt2api/blob/53119b5c4682c5606c9b4c80ad9d76d64105686e/services/image_storage_service.py#L134-L138)。

帧规则也不能照抄：[jiawen](https://github.com/jiawen-afk/chatgpt2api/blob/7ab8c20281133f8e78f54b8c762a604e702abebb/utils/helper.py#L184-L198)和 Fatal 使用 2–64 帧，gkingt 使用 2–16；gkingt 还[统一拒绝 GIF 的 stream 字段](https://github.com/gkingt/chatgpt2api/blob/8c319b2f2319b5111e03ea6ea33a579d7887b81d/utils/image_formats.py#L76-L96)。本项目应区分本地任务进度、网页会话事件流和原生分帧输出，不能因此关闭全部进度通知。

## 官方能力与免费网页账号权限

本轮按 OpenAI Docs 技能实际读取了[图片生成指南](https://developers.openai.com/api/docs/guides/image-generation#generate-animated-gif-output)、[生成接口 schema](https://developers.openai.com/api/reference/resources/images/methods/generate)以及 [Sunburst](https://developers.openai.com/api/docs/models/gpt-image-2.6-sunburst)、[Flare](https://developers.openai.com/api/docs/models/gpt-image-2.6-flare)模型页。

官方 Image API 支持 `output_format="gif"`，可从生成或编辑端点得到动画；指南帧数为 2–16，默认 9，每帧 20–2000 ms，默认 200 ms。生成 schema 明确要求所选模型具有 GIF preview（预览）权限。指南对帧间隔的操作范围与 schema 对 GIF 编码时长的表述并不完全相同，本文仅建议把指南区间用于本地提示参数，不据此声明网页协议限制。

这些官方页面没有证明免费 ChatGPT 网页账号具有相同权限；上述 fork 也没有同时提供 Free 套餐、账号来源、具体型号、真实多帧文件及复现步骤的完整验收记录。结论应分别写成“源码支持”“离线链路通过”“某个 Free 账号实测成功”。API 的预览权限要求不能直接转换成网页登录账号权限判定。

官方 GIF 不支持原生 streaming（流式图像输出）、partial images（分段图像）和自定义压缩。已有本地任务状态通知可以继续设计为进度事件，但这不证明网页原生 GIF 分帧流已接通，真实网页生成生命周期仍需验证。

## 本项目的最小改造

当前有三处明确阻断：[请求选项校验](https://github.com/fujunchao/chatgpt2api/blob/249b47117b9f851f8a3f01c03dec9ba26e15d6a0/utils/image_models.py#L105-L115)、[生成结果校验](https://github.com/fujunchao/chatgpt2api/blob/249b47117b9f851f8a3f01c03dec9ba26e15d6a0/services/protocol/conversation.py#L173-L181)、[存储校验](https://github.com/fujunchao/chatgpt2api/blob/249b47117b9f851f8a3f01c03dec9ba26e15d6a0/services/image_storage_service.py#L200-L211)。已有 GIF 格式嗅探、真实媒体类型、动画压缩跳过和海报缩略图可以复用；当前没有出图超分或统一转 PNG 的调用，不能按旧草稿假设重写这些不存在的处理。

建议分成两个可验证阶段：先贯通真实多帧结果的保存与显示，再开放实验 GIF 目标并做单个 Free 账号验收。两个阶段均在现有 2.6 网页路由内完成；裸名继续映射 Sunburst，具体型号原样传递。

| 文件与位置 | 改造内容 | 必须验证的行为 |
| --- | --- | --- |
| `utils/image_format.py:19`、`services/protocol/conversation.py:173` | 记录实际帧数及帧时长；GIF 目标要求格式为 GIF、至少两帧、所有帧可解码；静态与动画能力分开判断 | 拒绝 PNG、单帧 GIF、损坏 GIF 和未知格式；合格 GIF 保留全部原字节；不强制实际帧数等于提示值 |
| `services/image_storage_service.py:22,200` | 放行已验证的 GIF；添加 `.gif` 白名单；按真实格式取文件名；索引记录格式和动画元信息 | 本地与 WebDAV 都使用 `.gif`、`image/gif`；相册、ZIP、空间清理可看到 GIF；不得把 GIF 塞进静态格式集合 |
| `services/image_service.py:54,257` | 复用现有媒体类型识别和动画压缩跳过；列表可保留静态海报，原图用于播放与下载 | 压缩前后原 GIF 哈希一致；海报不替代原图；文件后缀正确时本地响应媒体类型正确 |
| `utils/image_models.py:105`、`services/config.py` | 配置控制实验入口；将客户端 `output_format=gif` 定义为本地目标；可选帧数和间隔只作提示 | PNG 兼容默认值继续有效；其余未接通原生控制仍明确拒绝；默认静态请求不改变 |
| `services/protocol/openai_v1_image_generations.py:19`、`openai_v1_image_edit.py:55`、`api/image_inputs.py:66` | JSON、multipart 共用目标格式和提示参数的规范化；传到请求对象 | 放开校验后不会在解析层丢字段；先覆盖文生 GIF 和静态参考图生成 GIF |
| `services/protocol/openai_v1_chat_complete.py:234`、`openai_v1_response.py:455` | Chat、Responses 顶层及工具字段使用同一规范化结果；明确工具字段与 PNG 兼容默认值的优先规则 | 预检与实际执行一致；流式和非流式入口结果类型正确 |
| `services/protocol/conversation.py:250,330,722` | `ConversationRequest` 贯通 GIF 目标；提示词描述运动、真实多帧文件和连续循环；给 GIF 单独配置较长等待预算，可参考 300 秒 | prepare、submit 保持具体 2.6 型号与 `picture_v2`；不注入未经证实的网页原生帧字段 |
| `services/protocol/conversation.py:1442`、`services/account_service.py:156` | 复用当前 `web/password/oauth_login` 来源和排除 Codex 的规则 | 真正的免费验收只使用已确认的 Free 网页账号，不能以混合池中的 Plus 成功冒充 Free |
| `api/image_tasks.py`、`services/image_task_service.py:125,219,388,528` | submit、handler、保存、加载、公开任务结果、续轮询同时保留 GIF 目标及提示 | 重启后仍按原目标校验；只读取原账号、原会话，不重新提交或切号生成 |
| `web/src/lib/api.ts:518`、`web/src/store/image-conversations.ts:33` | 发送、历史、复用、重试、任务恢复保留目标格式 | GIF 请求选项不会在界面继续等待或历史复用时退回静态默认值 |
| `web/src/lib/image-data.ts:4`、`web/src/components/image-lightbox.tsx:191`、图片页组件 | 增加 GIF87a/GIF89a 嗅探、`image/gif` data URL 与 `.gif` 下载名；实验入口显示 GIF 和运动提示；原图用已有 `<img>` 播放 | 预览播放实际 GIF，下载原始动画；海报和原图用途明确；初期可不显示未验证的帧数高级控制 |

任务恢复尤其不能只补保存：[当前加载代码](https://github.com/fujunchao/chatgpt2api/blob/249b47117b9f851f8a3f01c03dec9ba26e15d6a0/services/image_task_service.py#L388-L419)使用显式字段白名单；GIF 目标若保存却未加载，服务重启后会丢失。[续轮询](https://github.com/fujunchao/chatgpt2api/blob/249b47117b9f851f8a3f01c03dec9ba26e15d6a0/services/image_task_service.py#L506-L539)必须用原目标验收，避免把后来读到的 PNG 当作 GIF 成功。

失败也属于契约：GIF 请求得到 PNG、单帧、文本或格式不匹配时，应一次终止并返回结构化错误，例如“上游未返回动画 GIF”。格式失败不能触发切号重投、第二次生成或本地复制重复帧伪装成功。超时后继续等待只读原会话，保留原账号摘要与 GIF 目标。实际帧数、时长由返回文件记录，提示值不作为精确输出承诺。

首期验收文生 GIF 与静态参考图动画化。当前上传方法发送原始字节，但参考文件名固定 `.png`；这不能证明将 GIF 原图作为输入时保留时间维度。原 GIF 的继续编辑应在独立验证后开放，不能默默截帧而声称完整动画编辑。

## 本轮验证与改造后的验收契约

本轮只用 Pillow 合成的两帧 GIF 和临时存储运行离线探针；它不是上游生成结果。结果保存为 [local-probe-results.json](evidence/image26-gif-2026-11-12/local-probe-results.json)，可复现脚本为 [probe_current_gif.py](evidence/image26-gif-2026-11-12/probe_current_gif.py)。

| 离线检查 | 实际结果 |
| --- | --- |
| 动画识别 | GIF、`.gif`、`image/gif`、2 帧、200/300 ms，识别正确 |
| 请求门 | 拒绝 GIF 目标，参数为 `output_format` |
| 结果门 | 拒绝 GIF，502 / `unsupported_image_format`（不支持的图片格式） |
| 存储门 | 在清理和写入前拒绝 GIF |
| 名称与白名单 | 生成名仍是 `.png`，`.gif` 不在存储白名单 |
| PNG 基线 | 保存正确，原字节不变 |
| 既有动画压缩保护 | 动画原字节不变 |
| 海报缩略图 | 生成单帧 PNG，不改原 GIF |
| 错误后缀的影响 | GIF 内容名为 `.png` 时，本地响应报 `image/png` |

前一回合已经运行的 3 项现有限制回归均通过；业务源码没有变化，本轮没有重复它们。没有运行外部 fork 的测试套件，外部测试仅按实际源码判别为请求替身或合成样本；另实际用 Pillow 确认 FatalErrorR 的测试 GIF 为单帧。

改造后应增加有行为意义的集成回归：各入口传同一目标；真实多帧原字节贯穿 base64/URL/WebDAV/下载；静态、单帧和损坏 GIF 仅提交一次即失败；任务跨重启仍保留目标；PNG/CVA 默认值、OAuth Free 来源与静态编辑继续通过；前端正确嗅探、命名和播放原动画。

下面是**拟适配后的接口验收模板，当前 v0.16.5 会拒绝这些 GIF 字段**。使用本地 API 密钥向 `POST /v1/images/generations` 发送，先隔离一个已确认套餐为 Free 的网页来源账号，分别验收两个具体型号。以下帧字段属于本地提示，只有实施了相应提示选项才使用。

```json
{
  "model": "gpt-image-2.6-flare",
  "prompt": "生成一个真实的循环动画 GIF：白色背景上一颗蓝色小球在左右两个位置间平滑移动，回到起点连续循环。请返回实际多帧 GIF 文件。",
  "n": 1,
  "size": "auto",
  "quality": "low",
  "output_format": "gif",
  "frame_count": 9,
  "frame_duration_ms": 200,
  "response_format": "b64_json"
}
```

解码返回的 `data[0].b64_json`，确认 GIF、至少两帧、每帧可解码，并观察提示中的运动；记录实际帧数、时长、尺寸和循环。再核对 `.gif` 下载名、`image/gif` 响应、原图播放、压缩前后哈希以及重启后的原会话恢复。用一张静态参考图验收动画化作为第二步。记录真实账号套餐、来源、请求型号、提交次数和脱敏响应；不要在报告中保存网页凭据。

若 Free 账号只返回静态图、单帧文件或权限错误，应记录该账号或该通道未通过。尚未确认的项目是：免费网页 GIF 权限、网页原生动画字段、帧提示精度、GIF 输入编辑的时间维度、最终图片引擎可核验身份。源码补丁完成后仍需上述实测，才能声称本项目的免费账号 GIF 能力可用。

完整数据保存在 [核查摘要](evidence/image26-gif-2026-11-12/survey-summary.json)、[8 个网页及额外实现的证据表](evidence/image26-gif-2026-11-12/fork-implementations.json)、[73 条固定提交引用与原文](evidence/image26-gif-2026-11-12/source-excerpts.json)、[上游重新抓取结果](evidence/image26-gif-2026-11-12/upstream-scan.json)和[不可访问节点](evidence/image26-gif-2026-11-12/inaccessible-forks.json)。这些文件保留可复核的提交、路径、行号和覆盖界限。

[数据一致性验证](evidence/image26-gif-2026-11-12/verification.json)另核对了全部分支对应的扫描提交、8 个网页仓库与全量清单的提交一致性、引用行号和离线探针结果。证据文件说明见[证据目录说明](evidence/image26-gif-2026-11-12/README.md)。
