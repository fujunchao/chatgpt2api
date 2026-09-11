# Free 网页账号图片入口

适用版本：`v0.16.2`，在 `v0.16.1` 基础上新增 Free 网页图片入口，保留原有 Codex 路由和生产传输补丁。

## 实现目标

用户已确认：同一个 ChatGPT Free 免费账号通过原 `gpt-image-2` 可以出图。因此这次**不重写健康的网页协议**，而是增加一个可以被客户端选择的 `gpt-image-2.5` 兼容入口，复用同一条 Web 图片请求，并正确区分 Web 与 Codex 的账号来源。

`gpt-image-2.5` 是**本项目的 Web 自动路由名称**，不是从上游回包确认的图片引擎版本。不能用这个名字、成功返回图片、分辨率或本地回显证明实际使用了某个 2.5 变体。

## 模型与账号

| 请求名称 | 通道 / 账号条件 | 实际选择方式 |
| --- | --- | --- |
| `gpt-image-2.5` | Web：`web`、`password` 或默认 Web 来源；正常且有图片额度的 Free / 付费账号 | 与旧 `gpt-image-2` 相同：对话 `model=gpt-5-3` 和 `system_hints=["picture_v2"]`，图片引擎由官网选择 |
| `gpt-image-2` | 保持原 Web 入口及原选号策略 | 不改变默认值、提示词、尺寸/质量传递或上游参数 |
| `gpt-image-2.5-flare` / `gpt-image-2.5-sunburst` | 保持 Codex 来源及 Plus / Team / Pro 条件 | 保持原图片工具请求参数；没有改成 Web 后备路径 |
| `codex-gpt-image-2.5*` / 既有套餐前缀 | 保持现有 Codex 路由 | 不更换工具模型映射，不降低账号条件 |

新 Web 入口在本地初筛和远端账号刷新后都验证来源；不会因为 Web 配额耗尽就使用 Codex 账号或付费 API。`password` 只是网页登录来源的一种存储标记，不修改登录流程和账号记录的来源值。

“Web 自动”描述的是**图片引擎由官网选择**，并不意味着本次把顶层对话 `model` 改成了字面值 `auto`。由于旧请求已被用户验证成功，本次保留其上游对话参数；将来如有协议变化，再依据该账号的实际请求单独适配。

## 模型目录和界面

有 Web 来源账号时，`GET /v1/models` 会增加此入口；只有 Codex 账号时不会增加。禁用或异常账号不提供新入口，图片配额仍在请求时校验。

新增的本项目扩展说明如下：

```json
{
  "id": "gpt-image-2.5",
  "owned_by": "chatgpt2api",
  "description": "ChatGPT Web 图片兼容入口，支持有配额的 Free 网页账号；图片引擎由官网自动选择，具体版本未知，不能指定 Flare / Sunburst。",
  "metadata": {
    "route": "web",
    "model_selection": "upstream_auto",
    "variant_selection": false
  }
}
```

匿名上游模型目录中的同名项不会覆盖本地入口的来源条件或能力说明。

图片工作台显示 `gpt-image-2.5 · Web 自动`；Codex 选项附加 `· Codex` 并说明所需账号。新 Web 入口沿用 Web 的质量/尺寸选项，不宣称具备精确原生分辨率、`xhigh/max` 或变体选择能力。Web 的尺寸和质量通过提示传达，不是保证被执行的官方图片工具参数。

## 调用示例

下面的密钥是本项目 API 密钥，不是 ChatGPT Cookie 或 OpenAI Platform API Key。示例端口沿用 Docker 默认映射；如果部署端口不同，替换地址即可。

### 文生图

```bash
curl http://127.0.0.1:3000/v1/images/generations \
  -H "Authorization: Bearer <chatgpt2api-api-key>" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-image-2.5","prompt":"一只橘猫坐在窗台上","n":1,"response_format":"b64_json"}'
```

### 参考图编辑

```bash
curl http://127.0.0.1:3000/v1/images/edits \
  -H "Authorization: Bearer <chatgpt2api-api-key>" \
  -F "model=gpt-image-2.5" \
  -F "prompt=将背景改成蓝色，保留主体" \
  -F "image=@reference.png"
```

JSON 编辑、多参考图、`stream=true`、Chat 图片模式及后台图片任务也接受该名称。Responses 可用独立的工具模型字段：

```json
{
  "model": "gpt-5",
  "input": "画一个蓝色圆形",
  "tools": [{"type": "image_generation", "model": "gpt-image-2.5"}]
}
```

这仍是本项目的兼容路由，并不是用 Free 令牌调用官方付费 Images API。

## 结果、用量与错误

- 不把请求模型名当作已确认的上游图片版本；具体引擎/变体未知。
- 没有上游实际用量时，新 Web 入口省略 `usage`、返回 `usage_source="unavailable"`；流式结果和后台任务同样保留这个标记。旧 `gpt-image-2` 的估算行为不变。
- Web 账号不可用或无额度时返回 `429 insufficient_quota` / `no available web image quota`，不会静默换成 Codex。
- Free 账号请求既有 Codex 变体仍会受原账号条件约束，不会因新增 Web 别名而获得 Codex 图片权限。
- 保留图片 HTTP/1.1、严格消息 ID 恢复和已提交请求不盲目重投的生产补丁。本次没有引入其他 Fork 的全局 403 重试、登录、注册或存储改动。

## 验证范围

2026-09-11 本地验证：181 项后端离线回归、4 项前端逻辑测试、独立 TypeScript 类型检查和前端生产构建全部通过。

离线回归通过真实 HTTP 兼容入口、账号池筛选、Web 请求构造、参考图上传构造及 SSE 解析，只模拟外部 HTTP、账号健康检查与图片下载。使用虚构账号、隔离配置与临时存储，禁止外连。

回归覆盖：

- Free 模型目录、Web 自动说明、匿名目录同名项去重；
- 新旧入口 prepare/submit 请求语义一致、HTTP/1.1 保留；
- Free 文生图、multipart 多参考图与 JSON 编辑；
- password/default Web 来源、混合 Codex 账号池、配额/禁用/限流、刷新后来源变化；
- 原 Codex 变体不回退 Web；
- 流式、Chat、Responses、后台任务和未知用量。

```bash
python -X utf8 -B scripts/run_offline_tests.py
bun test test/test_image_models_frontend.test.ts
# 在 web 目录
node node_modules/typescript/bin/tsc --noEmit --incremental false
npm run build -- --webpack
```

用户对旧入口的成功反馈不等于本次独立运行了新入口的真实上游出图测试；本次隔离测试也不确认实际图片引擎身份。请使用 `ghcr.io/fujunchao/chatgpt2api:0.16.2` 或本版本源码构建；旧 `v0.16.1` 镜像不包含这个入口。

## 参考实现

- [qawow 的 Free Web 测试记录与请求身份边界](https://github.com/qawow/chatgpt2api-grok/blob/134bbf6a19470f0e7f7259b89264f5f3f1e9e061/CHANGELOG.md#L26-L30)。
- [qawow 新旧名称保持同一 Web 请求的实现](https://github.com/qawow/chatgpt2api-grok/blob/134bbf6a19470f0e7f7259b89264f5f3f1e9e061/utils/helper.py#L17-L31)。

本次在现有实现上做小范围适配，没有整仓移植该项目。
