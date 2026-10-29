# Research Hub Skill · 全域调研

[English](README.md)

一个 Codex skill，同步研究国内平台、海外社区与 RSS，把真实讨论转成有出处的市场判断、创业验证和内容起号实验。

**内置两个研究引擎与 RSS 采集器，一次安装即可使用基础功能。** 不需要先安装其他 skill。Python 3.12+；RSS 只用标准库。海外的部分来源需要可选 CLI、API Key 或已有登录配置。

## 安装与调用

使用 Agent Skills CLI：

```bash
npx skills add CCD-AIGC/research-hub-skill --skill research-hub -g -a codex
```

在 Codex 中调用：

```text
用 $research-hub 调研最近30天一人公司常用工具的用户痛点、竞品差评和内容机会。
国内、海外和 RSS 都看，每个结论附原始来源，区分观察、解释和待验证假设。
```

## 三类来源

| 渠道 | 引擎 / 来源 | 说明 |
|---|---|---|
| 国内 | last30days-cn v4.0.0-cn | 微博、小红书、B站、知乎、抖音、微信公众号、百度、头条 |
| 海外 | mvanhorn/last30days-skill 3.31.0 固定快照 | Reddit、Hacker News、GitHub、YouTube、X 等，按当前后端可用性运行 |
| RSS / Atom | 内置采集器 + 14 个原站订阅 | 中文产品、创业市场、内容与营销；支持替换 JSON / OPML |

国内适配器列表不代表所有平台免登录可用。每次运行会保留正常结果、公开搜索兜底、登录失败和超时等状态。没有日期的搜索线索不会被包装成近期帖子，缺失互动数据不会被填写成 0。

海外代码来自 [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill)，国内代码来自已安装的 MIT 中文本地化快照。具体版本、许可与集成修改见[第三方说明](THIRD_PARTY_NOTICES.md)及[引擎来源记录](skills/research-hub/references/engines.json)。

## 商业判断与内容实验

Research Hub 1.1.0 增加中文分析方法：区分来源观察、模型解释和待验证假设；检查用户情境、替代行为、付费信号、竞品摩擦与反例；再为商业或内容判断设计低成本验证。流程见[商业与内容分析工作流](skills/research-hub/references/business-content-workflow.md)，来源与许可边界见[方法来源记录](skills/research-hub/references/method-sources.md)。新方法使用已有 `evidence.json`，不改变三路采集逻辑。

调研参考了 [dbskill](https://github.com/dontbesilent2025/dbskill) 和 [baoyu-skills](https://github.com/JimLiu/baoyu-skills)。dbskill 为 CC BY-NC 4.0，其技能文本与知识原子没有被复制、改写或纳入 MIT 包；新工作流围绕 Research Hub 的证据结构独立撰写。Baoyu 为 MIT，本项目只记录小红书图文分析的参考范围，不包含其图像生成或发布工作流。

## 直接运行

从仓库根目录运行：

```bash
python3 skills/research-hub/scripts/research.py --diagnose

python3 skills/research-hub/scripts/research.py "一人公司工具" \
  --global-query "solopreneur tools" \
  --rss-query "一人公司" --rss-query "solopreneur" --rss-query "bootstrapping" \
  --quick
```

默认同时运行三路；可加 `--scope cn`、`--scope global` 或 `--scope rss`。时间窗口为 1–30 天，支持 `--days 7 --as-of 2026-10-29`。复杂主题应由 Codex 生成多角度查询计划，格式见[查询计划](skills/research-hub/references/planning.md)。

替换 RSS 源：

```bash
python3 skills/research-hub/scripts/research.py "创作者经营" \
  --scope rss --feeds /absolute/path/feeds.opml \
  --rss-query "creator" --rss-query "创作者"
```

## 结果与证据

每次运行默认写入新的 `work/research-hub/<run>/` 目录，可用 `--out /absolute/new/directory` 指定位置，已有研究不会被覆盖。

- `evidence.json`：统一结构、原始 URL 去重、各次出现的日期、平台指标、获取方式及原始记录 ID。
- `evidence.md`：来源覆盖表和证据摘录。
- `raw/`：引擎原始结果、诊断和日志。

最终分析由主持 Codex 模型完成。转发不等于独立验证；不同平台互动指标不相加；讨论热度不等于市场规模或付费意愿。RSS 只覆盖订阅当前返回的文章。

## 配置与隐私

现有配置可放在 `~/.config/last30days/.env`、`~/.config/last30days-cn/.env`，或使用进程环境。具体变量见[数据源说明](skills/research-hub/references/sources.md)。

默认关闭自动浏览器和 Cookie 提取，不创建账号或自动购买服务。`--allow-browser` 只在用户明确授权后使用。`--public-only` 可忽略已有 API 配置；已配置的付费后端可能按服务规则消耗额度。

## 验证

```bash
python3 -m unittest discover -s tests -v
```

测试覆盖 RSS/Atom、日期窗口、未知日期、跨渠道去重、缺失指标、失败状态、同名实体排除、三路整合和已有输出保护。测试使用本机 HTTP fixture 与隔离引擎，不依赖外部平台或 API Key。GitHub Actions 运行相同检查。

## 许可

Research Hub 项目代码为 MIT。两个底层引擎和 Bird 子集保留各自原始许可，详见[第三方说明](THIRD_PARTY_NOTICES.md)。
