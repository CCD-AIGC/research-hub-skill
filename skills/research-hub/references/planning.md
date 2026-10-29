# 海外查询计划

统一入口复用 last30days v3 的 JSON 查询计划，实际执行引擎位于 `engines/global/scripts/last30days.py`。

先运行统一诊断，读取 `source_availability.global.available_sources`。这反映当前配置；来源仍可能在查询时受限。选择来源时考虑主题，不凭空加入不可用平台。若用户明确缩小海外来源，计划与 `--global-sources` 必须一致。

具名产品或人物先通过宿主网页搜索核实其身份、官方定位、同名对象、相关官方账号或社区。所有子查询都带必要的实体限定，查询词不附“最近30天”等时间套话。复杂主题用 1–4 个有实质差异的子查询，主要子查询涵盖预定来源；脚本另行负责日期。

用正常文件写入工具创建计划 JSON，避免把用户文本拼入 shell。传文件路径：`--global-plan /absolute/path/plan.json`。示例的来源仅为演示，执行前按实际诊断替换。

```json
{
  "intent": "product",
  "freshness_mode": "strict_recent",
  "cluster_mode": "market",
  "subqueries": [
    {
      "label": "primary",
      "search_query": "solopreneur tools",
      "ranking_query": "What problems do solo founders report with their business tools?",
      "sources": ["reddit", "hackernews", "github"],
      "weight": 1.0
    },
    {
      "label": "switching",
      "search_query": "solopreneur software alternatives",
      "ranking_query": "Which unmet needs lead solo founders to switch tools or pay for alternatives?",
      "sources": ["reddit", "hackernews"],
      "weight": 0.7
    }
  ]
}
```

常用 intent 为 product、comparison、how_to、opinion、concept；freshness_mode 可用 strict_recent、balanced_recent、evergreen_ok；cluster_mode 可用 none、story、workflow、market、debate。统一入口最终仍会按所选窗口过滤证据，较旧资料不能被当作近期事实。

用户请求依赖特定账号、subreddit 或 GitHub 仓库的深度原生模式时，可在明确其需求后调用原始 last30days 技能对应流程；不要伪称统一入口已解析并传递这些尚未提供的定向字段。
