# Image 2.6 网页账号通道证据

核查日期：2026-11-12，Asia/Shanghai。范围仅限 ChatGPT 网页账号调用 `picture_v2` 图片会话。复用本会话已下载、已核对的固定源码，不重新枚举 fork，不调用真实生图接口，不修改业务代码。

**7 个候选都有代码级的网页 2.6 精确模型传递路径**：两个完整名称 `gpt-image-2.6-sunburst` / `gpt-image-2.6-flare` 在 resolver、prepare 和 submit 阶段都得到保留。它们全部沿用 `system_hints: ["picture_v2"]`，不是把新模型作为普通聊天模型发送。这里的“支持”指源码中的请求路径，不能解释为 7 个仓库均已验证真实账号权限。

网页专用计划最有价值的三点是：**内置图片模型不被旧缓存覆盖；显式模型不被默认值改写；选号时排除 Codex 来源并保留网页 Token、密码登录和 OAuth 登录的账号**。新格式、复杂度、标注和原生尺寸没有从这 7 个实现中获得网页原生字段证据，不宜直接移植公开 API 或 Codex 工具的参数。

## 1. 七个网页实现：固定提交与两次发送

这 7 个仓库均已在前一轮第一方 GitHub 元数据中确认属于 `basketikun/chatgpt2api` network。前 6 个使用 `main`，`gkingt` 必须使用 `my_1.5.0` 分支；其 `main` 无对应适配。这里不把同 SHA 镜像算作独立样本。

| 仓库、分支和固定 SHA | resolver 保留 2.6 的证据 | prepare 的实际字段 | submit 的实际字段 | 结论 |
| --- | --- | --- | --- | --- |
| jiawen-afk/chatgpt2api，`main`，`7ab8c20281133f8e78f54b8c762a604e702abebb` | [`_image_model_slug:693-702`](https://github.com/jiawen-afk/chatgpt2api/blob/7ab8c20281133f8e78f54b8c762a604e702abebb/services/openai_backend_api.py#L693-L702) 对新版本返回 `base_model`；只有旧 `gpt-image-2` 被映射到默认文本 slug | [`1017-1027`](https://github.com/jiawen-afk/chatgpt2api/blob/7ab8c20281133f8e78f54b8c762a604e702abebb/services/openai_backend_api.py#L1017-L1027)：`model` 使用同 resolver，提示为 `picture_v2` | [`1158-1168`](https://github.com/jiawen-afk/chatgpt2api/blob/7ab8c20281133f8e78f54b8c762a604e702abebb/services/openai_backend_api.py#L1158-L1168)：再次使用同 resolver；顶层和消息 metadata 保留图片提示 | 代码支持 Web 两个具体名称；有旧缓存和生成/编辑请求测试 |
| mxw13579/chatgpt2api，`main`，`d3fa3571eb045f2f9e83a1a22f755dfe373ea026` | [`694-703`](https://github.com/mxw13579/chatgpt2api/blob/d3fa3571eb045f2f9e83a1a22f755dfe373ea026/services/openai_backend_api.py#L694-L703) 对 2.6 返回 `base_model`，默认配置仅影响旧模型 | [`1005-1015`](https://github.com/mxw13579/chatgpt2api/blob/d3fa3571eb045f2f9e83a1a22f755dfe373ea026/services/openai_backend_api.py#L1005-L1015) | [`1146-1156`](https://github.com/mxw13579/chatgpt2api/blob/d3fa3571eb045f2f9e83a1a22f755dfe373ea026/services/openai_backend_api.py#L1146-L1156) | 同样支持 Web 原名，两阶段均为 `picture_v2`；与上一仓库共享部分实现，HEAD 不同 |
| lc2022560478/chatgpt2api，`main`，`17f7ef18498055ebccb280f9ca065be1fce817ed` | [`624-645`](https://github.com/lc2022560478/chatgpt2api/blob/17f7ef18498055ebccb280f9ca065be1fce817ed/services/openai_backend_api.py#L624-L645) 两个 `IMAGE_26_*` 常量专门进入 `upstream_model=base_model` 分支 | [`940-951`](https://github.com/lc2022560478/chatgpt2api/blob/17f7ef18498055ebccb280f9ca065be1fce817ed/services/openai_backend_api.py#L940-L951) | [`1097-1107`](https://github.com/lc2022560478/chatgpt2api/blob/17f7ef18498055ebccb280f9ca065be1fce817ed/services/openai_backend_api.py#L1097-L1107) | 代码支持 Web 精确名称，两阶段均为 `picture_v2` |
| hp0912/chatgpt2api，`main`，`e5bae8714da06c4e3676dd00d04bd56266c35d64` | [`571-584`](https://github.com/hp0912/chatgpt2api/blob/e5bae8714da06c4e3676dd00d04bd56266c35d64/services/openai_backend_api.py#L571-L584)：显式版本保留原 ID，避免回到默认别名 | [`877-888`](https://github.com/hp0912/chatgpt2api/blob/e5bae8714da06c4e3676dd00d04bd56266c35d64/services/openai_backend_api.py#L877-L888) | [`1022-1032`](https://github.com/hp0912/chatgpt2api/blob/e5bae8714da06c4e3676dd00d04bd56266c35d64/services/openai_backend_api.py#L1022-L1032) | 代码支持 Web 精确名称；维护者明确说官网新 ID 尚未实测 |
| FatalErrorR/chatgpt2api，`main`，`53119b5c4682c5606c9b4c80ad9d76d64105686e` | [`utils/helper.py:163-172`](https://github.com/FatalErrorR/chatgpt2api/blob/53119b5c4682c5606c9b4c80ad9d76d64105686e/utils/helper.py#L163-L172) 对 `WEB_IMAGE_2_6_MODELS` 返回原名；[`backend:676-684`](https://github.com/FatalErrorR/chatgpt2api/blob/53119b5c4682c5606c9b4c80ad9d76d64105686e/services/openai_backend_api.py#L676-L684) 使用该结果 | [`989-998`](https://github.com/FatalErrorR/chatgpt2api/blob/53119b5c4682c5606c9b4c80ad9d76d64105686e/services/openai_backend_api.py#L989-L998) | [`1157-1162`](https://github.com/FatalErrorR/chatgpt2api/blob/53119b5c4682c5606c9b4c80ad9d76d64105686e/services/openai_backend_api.py#L1157-L1162) | 代码支持 Web 精确名称；其另有 Codex 支持，但本报告只计 Web |
| IFuZYI/chatgpt2api，`main`，`af7bef567604877e0e6d452c64ed4d6ee8208004` | [`internal/upstream/image_chain.go:28-60`](https://github.com/IFuZYI/chatgpt2api/blob/af7bef567604877e0e6d452c64ed4d6ee8208004/internal/upstream/image_chain.go#L28-L60) 默认分支返回 2.6 `baseModel`，不使用 `defaultUpstream` 改写 | [`111-142`](https://github.com/IFuZYI/chatgpt2api/blob/af7bef567604877e0e6d452c64ed4d6ee8208004/internal/upstream/image_chain.go#L111-L142) 的 `model` 和 `picture_v2` | [`215-257`](https://github.com/IFuZYI/chatgpt2api/blob/af7bef567604877e0e6d452c64ed4d6ee8208004/internal/upstream/image_chain.go#L215-L257) 的 `model` 和 `picture_v2` | Go Web 实现原名传递；维护者有三名称实测声明，账号套餐未分层 |
| gkingt/chatgpt2api，`my_1.5.0`，`8c319b2f2319b5111e03ea6ea33a579d7887b81d` | [`621-632`](https://github.com/gkingt/chatgpt2api/blob/8c319b2f2319b5111e03ea6ea33a579d7887b81d/services/openai_backend_api.py#L621-L632) 对 `IMAGE_26_MODELS` 原名传递 | [`933-943`](https://github.com/gkingt/chatgpt2api/blob/8c319b2f2319b5111e03ea6ea33a579d7887b81d/services/openai_backend_api.py#L933-L943) | [`1074-1084`](https://github.com/gkingt/chatgpt2api/blob/8c319b2f2319b5111e03ea6ea33a579d7887b81d/services/openai_backend_api.py#L1074-L1084) | 两阶段 Web 精确名称；明确实验支持且不保证全部账号开放 |

这些 Python 实现的端点都为 `/backend-api/f/conversation/prepare` 与 `/backend-api/f/conversation`；Go 实现在上表给出的两个函数中同样使用它们。参考图经上传成为 `file-service://...` 资产，submit 使用多模态消息，未改用公开 Images API 的上传 schema。

## 2. 缓存和默认回退的边界

“图片目录里没有 2.6”与“不能使用 2.6”不能直接等同。7 个实现的网页 resolver 都先用本地支持表识别版本，再保留版本原名；其 2.6 分支不会询问 `/backend-api/models` 是否列有此名称，不会因为旧默认配置是 `gpt-5-*` 而改写它。

- **jiawen-afk 的缓存合并是直接可复用的证据。** [`services/config.py:141-146`](https://github.com/jiawen-afk/chatgpt2api/blob/7ab8c20281133f8e78f54b8c762a604e702abebb/services/config.py#L141-L146) 将 `DEFAULT_IMAGE_MODELS` 与缓存合并，不让非空旧缓存覆盖新内置版本；[`480-499`](https://github.com/jiawen-afk/chatgpt2api/blob/7ab8c20281133f8e78f54b8c762a604e702abebb/services/config.py#L480-L499) 的默认模型也基于合并后列表校验。其 [`test_multi_image_results.py:270-294`](https://github.com/jiawen-afk/chatgpt2api/blob/7ab8c20281133f8e78f54b8c762a604e702abebb/test/test_multi_image_results.py#L270-L294) 让缓存只剩 `gpt-image-2`，仍检查两个 2.6 型号在 prepare 和无参考图/有参考图 submit 中原样发送。
- **mxw13579 采用相同缓存规则。** [`config.py:141-146`](https://github.com/mxw13579/chatgpt2api/blob/d3fa3571eb045f2f9e83a1a22f755dfe373ea026/services/config.py#L141-L146) 及 [`同名测试:270-294`](https://github.com/mxw13579/chatgpt2api/blob/d3fa3571eb045f2f9e83a1a22f755dfe373ea026/test/test_multi_image_results.py#L270-L294) 证明它不是只给前端新增名称。
- **lc、hp、Fatal、gkingt 依赖内置模型表。** 2.6 的固定注册见 [lc/helper:17-27](https://github.com/lc2022560478/chatgpt2api/blob/17f7ef18498055ebccb280f9ca065be1fce817ed/utils/helper.py#L17-L27)、[hp/helper:17-34](https://github.com/hp0912/chatgpt2api/blob/e5bae8714da06c4e3676dd00d04bd56266c35d64/utils/helper.py#L17-L34)、[Fatal/helper:22-26](https://github.com/FatalErrorR/chatgpt2api/blob/53119b5c4682c5606c9b4c80ad9d76d64105686e/utils/helper.py#L22-L26)、[gkingt/helper:17-29](https://github.com/gkingt/chatgpt2api/blob/8c319b2f2319b5111e03ea6ea33a579d7887b81d/utils/helper.py#L17-L29)。这些注册与第 1 节 resolver 直接衔接。
- **IFu 的图片表与文本目录分开。** [`models.go:14-25`](https://github.com/IFuZYI/chatgpt2api/blob/af7bef567604877e0e6d452c64ed4d6ee8208004/internal/protocol/models.go#L14-L25) 内置 2.6 名称；[`image_model_settings_test.go:38-49`](https://github.com/IFuZYI/chatgpt2api/blob/af7bef567604877e0e6d452c64ed4d6ee8208004/internal/upstream/image_model_settings_test.go#L38-L49) 检查默认配置为旧模型也不会覆盖 2.6。其维护者 [`feature-status.md:93-101`](https://github.com/IFuZYI/chatgpt2api/blob/af7bef567604877e0e6d452c64ed4d6ee8208004/docs/feature-status.md#L93-L101) 声明 `/backend-api/models` 只提供文本目录；本报告不把这项说明扩大为所有账号和未来网页版本都绝无图片能力字段。

目录可能仍在刷新时请求上游；关键区别是**刷新结果不是显式 2.6 请求能否保留原名的前置条件**。例如 jiawen-afk 的 [`image_model_service.py:55-75`](https://github.com/jiawen-afk/chatgpt2api/blob/7ab8c20281133f8e78f54b8c762a604e702abebb/services/image_model_service.py#L55-L75) 会刷新模型，但未发现新图片名时的失败不会取代本地合并规则。

## 3. 账号来源与 Free/付费权限

必须分别记录“账号能够进入候选池”“上游接受该具体 model”“上游确实生成图片”。前两项的本地布尔值不能互相替代。

### 3.1 来源筛选：多数 fork 不能直接照搬

| 仓库 | 网页选号行为 | 对网页专用计划的影响 |
| --- | --- | --- |
| jiawen-afk | [`conversation.py:1710-1715`](https://github.com/jiawen-afk/chatgpt2api/blob/7ab8c20281133f8e78f54b8c762a604e702abebb/services/protocol/conversation.py#L1710-L1715) 对 Web 用 `source_type=None`；[`account_service.py:151-154`](https://github.com/jiawen-afk/chatgpt2api/blob/7ab8c20281133f8e78f54b8c762a604e702abebb/services/account_service.py#L151-L154) 此时匹配所有来源 | 混合号池可能选到 Codex 来源，不构成“只用网页账号”的保证 |
| mxw13579 | [`conversation.py:1683-1686`](https://github.com/mxw13579/chatgpt2api/blob/d3fa3571eb045f2f9e83a1a22f755dfe373ea026/services/protocol/conversation.py#L1683-L1686) 同样用 `None`；[`来源匹配:151-154`](https://github.com/mxw13579/chatgpt2api/blob/d3fa3571eb045f2f9e83a1a22f755dfe373ea026/services/account_service.py#L151-L154) 不排除 Codex | 同上 |
| hp0912 | [`conversation.py:1322-1325`](https://github.com/hp0912/chatgpt2api/blob/e5bae8714da06c4e3676dd00d04bd56266c35d64/services/protocol/conversation.py#L1322-L1325) Web 用 `None`；[`匹配:150-153`](https://github.com/hp0912/chatgpt2api/blob/e5bae8714da06c4e3676dd00d04bd56266c35d64/services/account_service.py#L150-L153) 不限制来源 | 其“路由正确”测试检查的是使用哪个协议函数，不能证明 Web 选号排除了 Codex |
| FatalErrorR | [`conversation.py:1436-1439`](https://github.com/FatalErrorR/chatgpt2api/blob/53119b5c4682c5606c9b4c80ad9d76d64105686e/services/protocol/conversation.py#L1436-L1439) Web 用 `None`；[`匹配:191-194`](https://github.com/FatalErrorR/chatgpt2api/blob/53119b5c4682c5606c9b4c80ad9d76d64105686e/services/account_service.py#L191-L194) 不限制来源 | 同上 |
| lc2022560478 | [`conversation.py:1694-1697`](https://github.com/lc2022560478/chatgpt2api/blob/17f7ef18498055ebccb280f9ca065be1fce817ed/services/protocol/conversation.py#L1694-L1697) Web 用 `None`；[`匹配:245-248`](https://github.com/lc2022560478/chatgpt2api/blob/17f7ef18498055ebccb280f9ca065be1fce817ed/services/account_service.py#L245-L248) 不限制来源 | 同上；额度、预检和冷却是另一层约束 |
| IFuZYI | [`image_generation_routes.go:310-319`](https://github.com/IFuZYI/chatgpt2api/blob/af7bef567604877e0e6d452c64ed4d6ee8208004/internal/api/image_generation_routes.go#L310-L319) Web `SlotOptions` 无 `SourceType`；[`account.go:510-515`](https://github.com/IFuZYI/chatgpt2api/blob/af7bef567604877e0e6d452c64ed4d6ee8208004/internal/service/account.go#L510-L515) 空来源匹配所有账号 | Go 实现也不能直接作为排除 Codex 的依据 |
| gkingt | [`conversation.py:1388-1391`](https://github.com/gkingt/chatgpt2api/blob/8c319b2f2319b5111e03ea6ea33a579d7887b81d/services/protocol/conversation.py#L1388-L1391) 对网页 2.6 用 `chatgpt_web`；[`account_service.py:256-262`](https://github.com/gkingt/chatgpt2api/blob/8c319b2f2319b5111e03ea6ea33a579d7887b81d/services/account_service.py#L256-L262) 将它解释为来源不是 `codex` | 有明确网页来源隔离，可借鉴行为；实际允许的来源名应与本地账号规范对齐 |

gkingt 的 [`test_web_image26.py:76-89`](https://github.com/gkingt/chatgpt2api/blob/8c319b2f2319b5111e03ea6ea33a579d7887b81d/test/test_web_image26.py#L76-L89) 同时覆盖不调用 Codex、网页 Token/密码/OAuth 导入可使用该来源，以及 Codex 来源被排除。把来源直接写为 `web` 可能误排除本地合法的 `password` / `oauth_login` 账号，因此需要用本项目规范判断其“网页凭据”类别。

### 3.2 权限：没有七个仓库逐套餐实测的证据

- jiawen-afk、mxw13579、hp0912、FatalErrorR 的基础候选判断是账号状态和 `quota>0`，Web 调用不加付费 `plan_types`。以 [`jiawen/account_service.py:133-166`](https://github.com/jiawen-afk/chatgpt2api/blob/7ab8c20281133f8e78f54b8c762a604e702abebb/services/account_service.py#L133-L166) 为例，Free 不会仅因套餐类型被该代码排除；但这是调度规则，不能证明 Free 的 2.6 上游权限。
- lc2022560478 的 [`候选判断:218-232`](https://github.com/lc2022560478/chatgpt2api/blob/17f7ef18498055ebccb280f9ca065be1fce817ed/services/account_service.py#L218-L232) 增加成功、额度和模型不存在的冷却，仍不是对每个具体 2.6 model 的权限验证。
- IFu 的 [`账号判断:463-480`](https://github.com/IFuZYI/chatgpt2api/blob/af7bef567604877e0e6d452c64ed4d6ee8208004/internal/service/account.go#L463-L480) 依据可调度状态与额度，其 [`feature-status.md:77-85`](https://github.com/IFuZYI/chatgpt2api/blob/af7bef567604877e0e6d452c64ed4d6ee8208004/docs/feature-status.md#L77-L85) 声明三个 2.6 名称均实测出图，但没有提供账号来源、套餐、每模型权限或可重复运行的分层结果。
- hp0912 的 [`README.md:129-130`](https://github.com/hp0912/chatgpt2api/blob/e5bae8714da06c4e3676dd00d04bd56266c35d64/README.md#L129-L130) 明确说官网新 ID 接受情况尚未实测。
- gkingt 的 [`README.md:107-113`](https://github.com/gkingt/chatgpt2api/blob/8c319b2f2319b5111e03ea6ea33a579d7887b81d/README.md#L107-L113) 明确标为实验协议适配、不代表全部账号开放；其 [`候选条件:212-223`](https://github.com/gkingt/chatgpt2api/blob/8c319b2f2319b5111e03ea6ea33a579d7887b81d/services/account_service.py#L212-L223) 还拒绝 `image_quota_unknown`。

**因此，当前可确认的是 7 个 Web 请求构造实现，无法确认 7 个 Free/付费账号均已通过真实 2.6 验证。** 本轮没有真实账号生图，不将 mock 测试写成线上实测，不从“目录展示该模型”推导账号具有权限。后续计划的验收需要分别记录网页 Free、Plus 等实际拥有的套餐 × 两个具体模型 × 生成/编辑；未知权限应保持未知状态。

## 4. 新能力：网页原生请求字段的证据缺口

只检查实际发送至网页两个端点的 payload，不采用 Codex `image_generation` 工具字段或公开 `/v1/images/*` schema 替代它们。

| 能力 | 七个网页实现能证明的内容 | 当前计划边界 |
| --- | --- | --- |
| 精确模型 | 第 1 节证明两个完整 ID 都进入 prepare 和 submit 的 `model` | 可作为第一阶段的主要改造和契约验收目标 |
| `complexity` | 没有网页原生字段证据；gkingt [`conversation.py:1618-1622`](https://github.com/gkingt/chatgpt2api/blob/8c319b2f2319b5111e03ea6ea33a579d7887b81d/services/protocol/conversation.py#L1618-L1622) 对 Web 该选项提前报错 | 不在第一阶段宣布支持；需实际网页请求字段证据后再计划接入 |
| GIF、帧数/时长 | jiawen [`build_image_prompt:280-298`](https://github.com/jiawen-afk/chatgpt2api/blob/7ab8c20281133f8e78f54b8c762a604e702abebb/services/protocol/conversation.py#L280-L298) 和 gkingt [`273-290`](https://github.com/gkingt/chatgpt2api/blob/8c319b2f2319b5111e03ea6ea33a579d7887b81d/services/protocol/conversation.py#L273-L290) 明确仅通过提示词请求动画；gkingt [`实际请求测试:26-44`](https://github.com/gkingt/chatgpt2api/blob/8c319b2f2319b5111e03ea6ea33a579d7887b81d/test/test_web_image26.py#L26-L44) 检查网页 payload 没有 `output_format` 和 `frame_count` | 如后续试验提示词 GIF，须明确为实验能力，并校验真实 GIF 多帧字节；不能宣称原生帧数参数已接通 |
| GIF 返回保留 | gkingt [`test_web_image26.py:91-108`](https://github.com/gkingt/chatgpt2api/blob/8c319b2f2319b5111e03ea6ea33a579d7887b81d/test/test_web_image26.py#L91-L108) 回放真实格式的多帧 GIF，保留原字节；静态 PNG/单帧 GIF 作为格式不匹配拒绝 | 证明本地保存与校验逻辑，不能证明上游一定产生动画 |
| SVG | 没有网页原生输出 selector；gkingt 的 Web 校验明确不开放 SVG，见 [`1618-1622`](https://github.com/gkingt/chatgpt2api/blob/8c319b2f2319b5111e03ea6ea33a579d7887b81d/services/protocol/conversation.py#L1618-L1622) | 独立缺口，不移植 Codex/公开 API 参数到网页 payload |
| `markup`、原生遮罩编辑 | 这些网页 submit 使用 `multimodal_text` 参考图与附件，未发现网页的 2.6 `markup` 或原生 mask 参数 | 参考图编辑可纳入静态验收；不能扩展为原生标注/遮罩能力已确认 |
| 原生尺寸与质量 | 示例的 `size` / `quality` 通过提示词给网页模型，见 [`jiawen:294-297`](https://github.com/jiawen-afk/chatgpt2api/blob/7ab8c20281133f8e78f54b8c762a604e702abebb/services/protocol/conversation.py#L294-L297)、[`gkingt:282-285`](https://github.com/gkingt/chatgpt2api/blob/8c319b2f2319b5111e03ea6ea33a579d7887b81d/services/protocol/conversation.py#L282-L285)；Go [`image_generate.go:209`](https://github.com/IFuZYI/chatgpt2api/blob/af7bef567604877e0e6d452c64ed4d6ee8208004/internal/protocol/image_generate.go#L209) 同样构建图片提示词。引用的 submit 中宽高是参考图的属性 | 记录上游实际输出尺寸；提示词约束或本地放大不能作为原生尺寸参数支持证据 |
| JPEG/WebP、压缩、部分图片流 | 未取得网页专用原生 selector 的证据；gkingt Web 提前拒绝主动 JPEG/WebP 选择 | 文件响应的真实 MIME 可以保留；不承诺可控制该格式或压缩档 |

本会话已实取的 [官方模型目录](https://developers.openai.com/api/docs/models) 和 [Image generation 指南](https://developers.openai.com/api/docs/guides/image-generation) 可作为公开模型及 API 能力背景，但**不能证明私有网页会话端点接受这些 API 参数**。本报告没有用它们填补网页协议缺口，也没有新增真实接口调用。

## 5. 可供网页专用计划采用的验收条目

以下是未来实施时的验收目标，不代表本轮已修改或运行它们。

1. 两个精确 2.6 model 进入现有网页管线；resolver、prepare、submit 完全一致。旧默认文本 slug、空目录或旧模型缓存均不改写显式 2.6。参考 [hp 请求测试:35-64](https://github.com/hp0912/chatgpt2api/blob/e5bae8714da06c4e3676dd00d04bd56266c35d64/test/test_image_model_routing.py#L35-L64)、[jiawen 旧缓存测试:270-294](https://github.com/jiawen-afk/chatgpt2api/blob/7ab8c20281133f8e78f54b8c762a604e702abebb/test/test_multi_image_results.py#L270-L294)。
2. Token、密码登录和 OAuth 登录形成合法网页候选；Codex 来源在展示模型、选号和重试阶段均排除。参考 [gkingt 来源测试:76-89](https://github.com/gkingt/chatgpt2api/blob/8c319b2f2319b5111e03ea6ea33a579d7887b81d/test/test_web_image26.py#L76-L89)。
3. 对“模型不接受”“账号无额度”“认证错误”“需要网页交互验证”分别保存真实错误。显式 2.6 不自动改成旧模型或另一个变体；额度重试保持原 model。参考 [gkingt 拒绝与额度区分:119-134](https://github.com/gkingt/chatgpt2api/blob/8c319b2f2319b5111e03ea6ea33a579d7887b81d/test/test_web_image26.py#L119-L134)。
4. 网页生成和参考图编辑、Base64/URL 返回、多图、超时及账号轮换沿用本地已建立的通路，并记录请求 model、实际分辨率和 MIME；不将获取通用额度当作 2.6 分层权限实测。
5. 第一期明确只验收已获网页字段证据的静态请求与响应。GIF/SVG/complexity/markup/原生尺寸控制须作为独立研究与验收阶段，取得网页请求证据后再启用。

本文复核了固定源码及存在的测试，未运行外部仓库测试或真实账号出图；所有权限和新能力的不确定性均保留。
