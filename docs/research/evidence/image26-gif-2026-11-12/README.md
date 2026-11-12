# Image 2.6 免费网页 GIF 核查证据

对应报告：[Image 2.6 免费网页账号 GIF](../../image26-free-web-gif-2026-11-12.zh-CN.md)。核查日期为 2026-11-12，当前业务源码基准为 `249b47117b9f851f8a3f01c03dec9ba26e15d6a0`。

| 文件 | 内容 |
| --- | --- |
| `fork-inventory.zh-CN.md` | 1,774 条完整记录、全部关键词候选和 29 个不可访问节点的可读清单 |
| `forks.json` | 每个节点的身份、父源、当前固定提交、默认/非默认分支、命中提交和访问状态 |
| `sha-scans.json` | 907 个固定提交的文本筛查状态、命中文件、固定归档 URL，以及复用或新抓取方式 |
| `survey-summary.json` | 本轮枚举、分支刷新和筛查的统计及时间 |
| `inaccessible-forks.json` | 29 次逐项 REST 仓库读取的 404 结果 |
| `upstream-scan.json` | 上游重新抓取的归档哈希及型号、GIF 关键词检查 |
| `fork-implementations.json` | 8 个完整网页 2.6 仓库和额外 Codex 实现的模型表、请求、GIF 和测试性质 |
| `source-excerpts.json` | 73 条固定提交源码 URL、文件、行号与原文 |
| `local-probe-results.json` | 当前三处 GIF 阻断以及已有动画保护的离线结果 |
| `probe_current_gif.py` | 合成两帧 GIF、隔离临时存储的可复现探针，不请求上游 |
| `verification.json` | 全量数据、8 个当前网页提交和离线结果之间的一致性检查 |

从仓库根目录可重现当前基准的离线探针：

```powershell
& '.\.venv\Scripts\python.exe' 'docs\research\evidence\image26-gif-2026-11-12\probe_current_gif.py'
```

探针用于重现 v0.16.5 的限制，输出至系统临时目录；GIF 适配后应以新的正向集成回归替代这些拒绝断言。合成文件、请求替身和源码命中均不构成真实免费账号 GIF 成功证据。

完整网络读取了全部可访问的当前分支头；文本筛查范围、归档复用和不可访问项的界限写在主报告与清单中。`free_gif_verified=false` 和 `native_web_gif_fields_verified=false` 表示本轮未取得相应证明，不能解释为这些能力一定不存在。
