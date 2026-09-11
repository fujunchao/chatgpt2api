# v0.16.1：生产补丁整合与 GPT Image 2.5

本文描述已发布的 `v0.16.1`。`v0.16.2` 新增了 Free 可用的裸 `gpt-image-2.5` Web 自动入口，见 [Free Web 接入说明](./free-web-image-integration.zh-CN.md)；下文历史版本的“裸名称不支持”不适用于 `v0.16.2`。

## 基线与范围

- 基线：`v1.6.0` / `66fee0c133599fc443997340ca00061a8ee261d9`。
- 用户补丁：`C2A-Production-Patches-20260910.zip`，SHA-256 为 `31192237d2675440ddccfa5cf77a19ea7bc9d8a428638f2e9c1237e5bab8a1ee`。
- 包含两份完整覆盖文件，不是可直接应用的 Git patch。已按 README 校验两个文件的 SHA-256，并分别与 v1.6.0 比较，没有直接整文件覆盖。
- 自有发布版本为 `0.16.1`；保留原配置、旧模型名称和默认值，镜像名为 `ghcr.io/fujunchao/chatgpt2api:0.16.1`。
- 未导入账号、运行注册或发起真实上游出图。本次验证的是本地逻辑、HTTP 兼容层、请求构造和构建，不是当前账号的上游模型权限。

## 补丁采用情况

| 原补丁改动 | 决定 | 当前处理 |
|---|---|---|
| Web 图片 SSE 使用 HTTP/1.1 | 采用 | 仅 `/backend-api/f/conversation` 图片请求设置 `CurlHttpVersion.V1_1`，其他请求不变 |
| 图片 SSE 超时改为 `(30, 90)` | 采用并补全恢复 | 提交阶段的 curl 28/92 被显式标记，预热、上传和 prepare 失败不进入“已提交会话恢复” |
| curl 92 后按 prompt/最近会话恢复 | 调整后采用 | 优先用 SSE 已知会话 ID；缺失时核对本次客户端消息 UUID，不根据标题或“最新一条”猜测 |
| 删除文本和图片 `finally.close()` | 不采用 | 保留确定性释放；构造、读取失败及重试退出路径均关闭连接 |
| 删除成功出图后的隐藏会话功能 | 不采用 | 保留原开关，清理线程使用独立连接，避免与生成线程关闭连接发生竞争 |

恢复会保留已经收到的文件 ID 和拦截状态。找不到本次会话时返回 `image_stream_interrupted`，不重复提交；已经确认提交后，轮询超时或下载失败也不再换账号重新生成。

Codex 连接/读取中断时同样不自动重复发送，因为该链路没有本项目可用的会话恢复接口。错误体截断或读取超时不会覆盖已收到的 HTTP 状态；并行多图全部失败时保留按索引首个结构化错误，避免把 403/429 一律改成 502。

## 模型名称与路由

模型规则集中在 `utils/image_models.py`，旧 `utils/helper.py` 保持原有导出接口。

| 请求模型 | 调用通道 | 实际图片工具模型 |
|---|---|---|
| `gpt-image-2` | 原 Web 图片链路 | 维持 v1.6.0 的原映射 |
| `codex-gpt-image-2` | Codex | `gpt-image-2` |
| `gpt-image-2.5-flare` | Codex | `gpt-image-2.5-flare` |
| `gpt-image-2.5-sunburst` | Codex | `gpt-image-2.5-sunburst` |
| `codex-gpt-image-2.5-flare` | Codex | `gpt-image-2.5-flare` |
| `codex-gpt-image-2.5-sunburst` | Codex | `gpt-image-2.5-sunburst` |
| `codex-gpt-image-2.5` | Codex | 明确默认 `gpt-image-2.5-flare` |

`codex-*` 名称还支持 `plus-`、`team-`、`pro-` 套餐前缀，例如 `pro-codex-gpt-image-2.5-sunburst`。裸 `gpt-image-2.5`、`gpt-image-2-5`、`gpt-image-3.0` 不在白名单中，不会静默回退成 2.0。

2.5 请求要求账号来源为 `codex`，且套餐为 Plus、Team 或 Pro；保留原账号池并发/配额筛选。普通网页登录 Token 不会因为选择了新名称就自动变成 Codex 来源账号。`/v1/models` 按本地账号条件展示入口，不是实测权限证明；若上游拒绝模型，保留错误，不删掉正常账号，也不伪装成旧模型成功。

上游地址仍为 `/backend-api/codex/responses`：顶层控制模型保留 `gpt-5.5`，真正的 2.5 选择写入 `tools[0].model`。未猜测或原样透传未经验证的 2.5 Web conversation slug。

## 参数与兼容 API

- 保留 `/v1/images/generations`、multipart/JSON `/v1/images/edits` 与后台图片任务入口。
- Chat Completions 图片模式补齐 `size`、`quality` 透传。
- Responses 优先读取图片工具的 `tools[].model`，与顶层对话模型区分；兼容旧的顶层图片别名写法，并保留多张参考图。
- 2.5 支持 `auto/low/medium/high/xhigh/max` 质量选择；切回旧模型会复位不适用的新档位。
- 仅对新增 2.5 模型校验尺寸：宽高为 16 的倍数、最大边 3840、长短边比例不超过 3:1、总像素 655360–8294400，或 `auto`。旧 2.0 的宽松参数行为不变。
- 前端 3:4 / 4:3 预设改为 `1008x1344` / `1344x1008`，避免原来的 1365 边长不符合约束。
- 修复工作台模型偏好恢复顺序，新模型和质量档位不会被初始默认值提前覆盖。

本次继续输出 PNG，未扩展 `background`、压缩格式、官方 Responses 会话持久化等全部参数。顶层 Responses 模型主要沿用兼容响应语义，不代表客户端可以任意切换私有上游的控制模型。

### 图片 API 示例

以下是对本项目的请求，不是官方 API Key 调用；Bearer 使用本项目管理员或用户密钥。

```json
{
  "model": "gpt-image-2.5-sunburst",
  "prompt": "一只橘猫坐在窗台上，午后阳光",
  "n": 1,
  "size": "1024x1024",
  "quality": "high",
  "response_format": "url"
}
```

发送至 `POST /v1/images/generations`。

### Responses 示例

```json
{
  "model": "gpt-5",
  "input": "生成一张简洁的咖啡杯产品照片",
  "tools": [{
    "type": "image_generation",
    "model": "gpt-image-2.5-flare",
    "size": "1024x1024",
    "quality": "high"
  }]
}
```

发送至 `POST /v1/responses`，图片模型取工具字段，不会把顶层 `gpt-5` 当成图片模型。

## 用量与结果

- 优先保留 Codex 上游返回的 `usage`；多张独立调用的用量按调用累加。
- 去除 `response.output_item.done` 与 `response.completed` 重复携带的同一图片，避免一张图重复返回。
- 2.5 没有上游用量时，不套用旧图片 Token 公式，省略 `usage`，返回 `usage_source: "unavailable"`。
- 旧模型保留原估算，标为 `estimated`；真实上游用量标为 `upstream`。若一批结果只有部分调用有用量，不把部分值冒充整批总量。
- 后台任务保存并返回用量来源。图片 SSE 会携带已有的上游用量；本次不声明实现完整的 Chat Completions `stream_options.include_usage` 协议。

## 部署方式

这次新增了模型模块，还修改了协议入口和前端。**不能继续只覆盖旧 ZIP 中的两个文件**，否则可能缺少模块，或者被旧挂载覆盖掉新逻辑。

推荐从当前源码重新构建：

```powershell
# 在本地仓库根目录执行
docker compose -f docker-compose.image25.yml up -d --build
```

该编排不使用远端 `latest`；复用 `config.json` 和 `data/`，不会写入或替换密钥。切换生产前保留现有数据，移除旧的两个源码覆盖挂载；不要与旧实例同时写同一份账号/任务数据。若需要先验收，使用独立数据副本和不同端口，而不是直接并发挂载生产数据。

普通源码开发仍可使用 `uv run main.py` 与前端开发服务。前端构建生成 `web/out`，FastAPI 静态托管使用 `web_dist`；Dockerfile 会自动完成该复制。

已于 2026-09-11 完成前端生产构建；本地开发可将静态产物复制到项目根目录的 `web_dist`，Docker 构建会自动完成复制。

本次没有启动或停止任何生产容器，Docker 镜像构建/真实上游联调不包含在离线测试结论里。Codex 保留原有 urllib 传输，未一并重做代理层；原版独立的手动 `resume-poll` 接口问题也不等同于本次实现的自动断流恢复。

## 验证方式

### 最终验证结果（2026-09-11）

| 检查 | 结果 |
|---|---|
| 完整后端离线回归 | 167 项通过，0 失败、0 错误 |
| 其中本次新增后端回归 | 51 项通过 |
| 前端纯逻辑回归 | 3 项通过，20 次断言 |
| 独立 TypeScript 检查 | `tsc --noEmit --incremental false` 通过 |
| 前端生产构建 | Next.js 16.2.3 / webpack 通过，12 个静态页面生成完成 |
| Python 语法 | API、服务、工具、测试、脚本目录共 101 个文件解析通过 |
| 新 Compose 文件 | YAML 解析通过，镜像固定为 `ghcr.io/fujunchao/chatgpt2api:0.16.1` |

前端构建配置原有的 `ignoreBuildErrors` 未用作绕过类型检查：上表的 TypeScript 检查是独立执行的。Docker 容器运行、浏览器端到端操作和真实账号出图尚未验证。

```powershell
uv run python scripts/run_offline_tests.py
uv run python scripts/run_offline_tests.py --new-only
bun test test/test_image_models_frontend.test.ts
Set-Location web
node node_modules/typescript/bin/tsc --noEmit --incremental false
npm run build -- --webpack
```

离线运行器只复制源码与 VERSION，创建虚构配置，不复制 `.env`、原 `config.json` 或 `data/`；禁止出站请求，跳过需要真实服务的原有人工/HTTP 测试。依赖与分词器资源需事先准备好。

原 v1.6.0 的 7 个已知离线失败是测试替身/预期滞后：已补齐 FakeProxySettings 的 profile 接口，更新 Data URL 文件名和错误文案断言，并把远程图片测试改为明确的成功/失败模拟，没有为通过测试回退现有 API 行为。

前端 Bun 1.2.21 的冻结安装遇到下载完整性错误；核对代表性包的官方 integrity 与锁文件相同后，使用 npm 官方源安装（仍进行包完整性校验、未禁用 TLS 校验、未修改 Bun 锁文件）。因此前端构建验证基于 package.json 的安装结果，不把它描述为一次成功的 Bun 冻结安装。

## Standards（规范轴）

原补丁初评：1 项新增英文注释与默认中文注释规范不一致；1 项判断性问题为分散恢复逻辑可能重复。整合时新增注释使用中文，模型规则集中，恢复复用明确的消息 ID 查找与原有轮询。最终规范轴只读复核未发现新增硬规范问题或高价值维护性问题。

## Spec（行为轴）

原补丁的主要行为风险为：错误恢复到其他会话、缩短超时却仅处理 curl92、丧失确定性连接释放、隐藏会话开关失效。本次按前述采用矩阵处理，未整文件覆盖。

实现复核又用纯内存探针发现“恢复成功后轮询超时仍重投”和“并行全失败丢失 403/429”，均已修复并补回归；Codex 超时重投及 HTTP 错误体截断边界也补有测试。未把这些离线检查当作真实 2.5 账号权限验证。

两轴结论分别保留：原补丁规范轴 2 项、行为轴 4 项；当前实现的复核问题均有针对性修复与测试，不跨轴混排严重程度。

## 参考来源

- [GPT Image 2.5 Sunburst](https://developers.openai.com/api/docs/models/gpt-image-2.5-sunburst)
- [GPT Image 2.5 Flare](https://developers.openai.com/api/docs/models/gpt-image-2.5-flare)
- [官方图片参数说明](https://developers.openai.com/api/docs/guides/image-generation#customize-image-output)
- [AstonChenDev 的模型参数贯通实现](https://github.com/AstonChenDev/chatgpt2api/commit/7ce6e0659e4245c4efb8c7b435ee84d47bde0aba)
- [FatalErrorR 的 Codex 模型别名实现](https://github.com/FatalErrorR/chatgpt2api/commit/acca0f992c8dca06b42f5d500ca5dd9171d06119)

移植参考的是 AstonChenDev 的模型参数贯通方式与 FatalErrorR 的显式 Codex 别名设计，没有整体覆盖它们的业务代码或发布配置。
