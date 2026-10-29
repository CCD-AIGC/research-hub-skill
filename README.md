# Research Hub Skill · 全域调研

一个 Codex skill，同步研究国内平台、海外社区与 RSS，支持市场需求、创业验证、竞品口碑和内容起号选题。

**内置两个研究引擎与 RSS 采集器，一次安装即可使用基础功能。** 不需要先安装其他 skill。Python 3.12+；RSS 只用标准库。海外的部分来源需要可选 CLI、API Key 或已有登录配置。

## 安装

使用 Agent Skills CLI：

```bash
npx skills add CCD-AIGC/research-hub-skill --skill research-hub -g -a codex
```

也可以请 Codex 的 skill-installer 安装本仓库的 `skills/research-hub` 目录。

在 Codex 中调用：

```text
用 $research-hub 调研最近30天一人公司常用工具的用户痛点、竞品差评和内容机会。
国内、海外和 RSS 都看，每个结论附原始来源，区分事实和待验证假设。
```

## 三类来源

| 渠道 | 引擎 / 来源 | 说明 |
|---|---|---|
| 国内 | last30days-cn v4.0.0-cn | 微博、小红书、B站、知乎、抖音、微信公众号、百度、头条 |
| 海外 | mvanhorn/last30days-skill 3.31.0 固定快照 | Reddit、Hacker News、GitHub、YouTube、X 等，按当前后端可用性运行 |
| RSS / Atom | 内置采集器 + 14 个原站订阅 | 中文产品、创业市场、内容与营销；支持替换 JSON / OPML |

国内适配器的覆盖范围不代表所有平台免登录可用。每次运行都会保留正常结果、公开搜索兜底、登录失败、超时等状态。没有日期的搜索线索不会被包装为近期帖子，缺失互动数据不会被填写成 0。

海外代码来自 [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill)，国内代码来自已安装的 MIT 中文本地化快照。具体版本、许可与集成修改见 [第三方说明](THIRD_PARTY_NOTICES.md) 及 [引擎来源记录](skills/research-hub/references/engines.json)。本项目不声称得到上游作者背书。

## 直接运行

以下命令从仓库根目录运行。实际执行 skill 时，Codex 会解析其绝对路径。

```bash
python3 skills/research-hub/scripts/research.py --diagnose

python3 skills/research-hub/scripts/research.py "一人公司工具" \
  --global-query "solopreneur tools" \
  --rss-query "一人公司" --rss-query "solopreneur" --rss-query "bootstrapping" \
  --quick
```

默认同时运行三路；可加 `--scope cn`、`--scope global` 或 `--scope rss`。时间窗口为 1–30 天，支持 `--days 7 --as-of 2026-10-29`。

复杂主题应由 Codex 生成多角度查询计划，传 `--global-plan /absolute/path/plan.json`。格式见 [查询计划](skills/research-hub/references/planning.md)。没有计划时脚本采用明确标注的单关键词检索，仍会调用海外研究引擎。

替换 RSS 源：

```bash
python3 skills/research-hub/scripts/research.py "创作者经营" \
  --scope rss --feeds /absolute/path/feeds.opml \
  --rss-query "creator" --rss-query "创作者"
```

## 结果与证据

默认生成独立的 `work/research-hub/<run>/`，可用 `--out /absolute/new/directory` 指定新目录，已有研究不会被覆盖。

- `evidence.json`：统一结构、原始 URL 去重、每个出现记录的日期、平台指标、获取方式和原始记录 ID。
- `evidence.md`：可读的来源覆盖表与证据摘录，供 Codex 分析。
- `raw/`：各引擎原始数据、诊断和日志。

最终分析由主持 Codex 模型完成。脚本不把转发当作独立验证，不合计不同平台的互动指标，也不把讨论热度等同于市场规模或付费意愿。RSS 只覆盖订阅当前返回的内容，无法保证完整历史覆盖。

## 配置与权限

现有配置可放在 `~/.config/last30days/.env`、`~/.config/last30days-cn/.env`，或使用进程环境。具体变量见 [数据源说明](skills/research-hub/references/sources.md)。

默认关闭自动浏览器和 Cookie 提取，不创建账号或自动购买服务。`--allow-browser` 只在用户明确授权后使用。`--public-only` 可忽略已有 API 配置，便于免费验收；已有付费后端的常规运行可能按其服务规则消耗额度。

仓库只包含代码、公开订阅 URL、测试和许可；不包含用户密钥、Cookie、登录状态或真实运行报告。

## 验证

```bash
python3 -m unittest discover -s tests -v
```

测试覆盖 RSS/Atom、日期窗口、未知日期、跨渠道去重、零值与缺失指标、失败状态保留、同名实体排除、三路子进程整合以及保留已有输出。测试使用本机 HTTP fixture 和隔离引擎，不依赖外部平台或 API Key。GitHub Actions 运行相同检查。

## License

MIT。两个底层引擎和 Bird 子集保留各自原始许可。
