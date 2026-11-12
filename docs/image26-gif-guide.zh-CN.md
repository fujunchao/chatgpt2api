# v0.17.0：网页 Image 2.6 GIF 接入

本版本支持实验性的文生 GIF 和静态参考图动画化，使用现有网页账号及图片额度。Free/OAuth 网页账号已完成 Flare、Sunburst 的四项真实验收，原动画和哈希见 [验收记录](research/image26-gif-acceptance-2026-11-12.zh-CN.md)。具体账号权限和动画效果以上游为准。

## 网页工作台

打开画图页的“图像设置”，选择网页 2.6 模型，再选择“GIF（实验）”。描述主体的运动和循环方式，例如“小球不断上下弹跳，首尾自然衔接”。上传静态参考图后，可用同样的格式选项进行动画化。

结果卡片和原图预览播放原 GIF；下载使用 `.gif` 后缀及原始字节。生成耗时与动画播放时长分别保存。刷新页面、复用配置、重新生成和单图重试保留该轮的格式及帧提示。切换到其他模型时，编辑器恢复为静态格式；已排队或恢复中的任务继续使用自己的原目标。

管理员可在系统配置中关闭“网页 2.6 GIF 实验功能”。关闭后新 GIF 请求明确失败，已有动画仍可播放、下载。普通用户通过只返回能力开关的 `/api/image-capabilities` 获取状态，无需读取管理员配置。

## 模型和参数

| 参数 | 接受值 | 含义 |
| --- | --- | --- |
| `model` | `gpt-image-2.6`、`gpt-image-2.6-flare`、`gpt-image-2.6-sunburst` | 三项均使用网页账号；短名固定请求 Sunburst |
| `output_format` | `gif` | 本地动画生成目标，不作为网页原生字段发送 |
| `frame_count` | 可选整数 2–16 | 提示期望帧数；实际结果无需精确匹配 |
| `frame_duration_ms` | 可选整数 20–2000 | 提示帧间隔，单位毫秒；实际结果无需精确匹配 |
| `response_format` | `b64_json` 或 `url` | 返回原 GIF 的 base64 或保存地址 |

格式名支持大小写和首尾空白规范化；表单里的数字字符串会规范化为整数。PNG 仍作为客户端兼容默认值接受，静态 PNG/JPEG/WebP 结果继续按实际类型保存。JPEG/WebP/SVG 主动格式选择和未接通的复杂度、压缩等控制仍会在提交前报错。

帧数和间隔仅通过提示词表达，不注入网页 prepare（准备）或 conversation（会话提交）协议。不能据此声称本项目接通了官方 Image API 的原生动画字段。

## 调用

`POST /v1/images/generations`：

```json
{
  "model": "gpt-image-2.6-flare",
  "prompt": "白色背景上的蓝色小球左右移动，生成首尾衔接的循环 GIF",
  "output_format": "gif",
  "frame_count": 9,
  "frame_duration_ms": 200,
  "n": 1,
  "response_format": "b64_json"
}
```

`POST /v1/images/edits` 可使用现有 JSON 参考图或 multipart（表单文件上传），同时传入上述格式与帧提示。参考图及遮罩必须是静态输入；GIF 请求中的动画参考图、动画遮罩和后续帧已损坏的 GIF 会在合成或提交前明确拒绝。

```json
{
  "model": "gpt-image-2.6-sunburst",
  "prompt": "让参考图中的小球持续上下弹跳，首尾衔接",
  "output_format": "gif",
  "images": [{"image_url": "data:image/png;base64,替换为静态参考图的base64"}]
}
```

Chat 的 `/v1/chat/completions` 图片模式在顶层接受相同选项，普通和流式响应均使用 `data:image/gif`。Responses 的 `/v1/responses` 可在顶层或图片工具里设置选项：

```json
{
  "model": "gpt-5",
  "input": "生成小球上下弹跳的循环动画",
  "tools": [{
    "type": "image_generation",
    "model": "gpt-image-2.6-flare",
    "output_format": "gif",
    "frame_count": 9,
    "frame_duration_ms": 200
  }]
}
```

工具中的图片型号决定实际网页请求。任一层明确请求 GIF 时，另一层的 PNG 兼容默认值不会将其覆盖；各层不支持的格式或原生字段仍会独立拒绝，不能通过另一层覆盖掩盖错误。

后台任务 `/api/image-tasks/generations` 和 `/api/image-tasks/edits` 接受同样的格式及帧提示。继续等待接口沿用原账号和原会话，跨重启后仍按该任务的 GIF 目标验收。

## 返回与失败

GIF 结果保留原始字节，URL 使用 `.gif`，媒体类型为 `image/gif`。`data` 中增加实际动画信息：

```json
{
  "url": "https://你的服务地址/images/实际文件.gif",
  "format": "gif",
  "mime_type": "image/gif",
  "animated": true,
  "frame_count": 9,
  "frame_durations_ms": [200, 200, 200, 200, 200, 200, 200, 200, 200],
  "duration_ms": 1800,
  "loop": 0
}
```

这里 `duration_ms` 为动画播放时长；任务顶层的同名字段为生成耗时，网页历史分别保存。`loop=0` 表示无限循环。未获得数字用量时继续省略 `usage` 并标记 `usage_source="unavailable"`。

成功必须是至少两帧、所有帧可解码的 GIF。网页可能同时返回 GIF 和 PNG 预览，本项目只选择完整 GIF。只返回 PNG、单帧 GIF、损坏 GIF 或 SVG 时返回 `animated_gif_not_generated`，不会自动重新提交生成，也不会复制帧伪造动画。提示中的帧数、尺寸和运动效果不保证精确匹配。

## 配置

```json
{
  "image_web_gif_enabled": true,
  "image_gif_poll_timeout_secs": 300
}
```

开关默认开启，GIF 等待预算默认 300 秒。普通与补充轮询都遵守 GIF 设置；更长的原 `image_poll_timeout_secs` 同样生效。调整等待预算只延长原会话读取，不重新生成。

动画参考图的完整编辑、Codex/官方 API 原生 GIF 控制、付费网页账号的 GIF 权限不属于本次验收范围。
