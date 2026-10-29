# Research Hub Skill

[简体中文](README.zh-CN.md)

A Codex skill for cross-platform market research, startup validation, competitor analysis, and creator-content experiments. It searches Chinese platforms, global communities, and RSS feeds in one run, then turns the collected evidence into source-linked findings and testable hypotheses.

**Bundled engines and RSS collector.** Install one skill; no separate research skills are required. Python 3.12+ is required. RSS uses the standard library. Some global sources need optional CLIs, API keys, or existing login configuration.

## Quick Start

Install with the Agent Skills CLI:

```bash
npx skills add CCD-AIGC/research-hub-skill --skill research-hub -g -a codex
```

Ask Codex:

```text
Use $research-hub to research the last 30 days of pain points, competitor feedback,
and creator-content opportunities for tools used by solo founders. Search Chinese
platforms, global communities, and RSS. Cite original sources and separate facts,
interpretations, and hypotheses.
```

You can also install the `skills/research-hub` directory with Codex skill-installer.

## Research Coverage

| Track | Sources | Notes |
|---|---|---|
| Chinese platforms | Bundled `last30days-cn` 4.0.0-cn snapshot | Weibo, Xiaohongshu, Bilibili, Zhihu, Douyin, WeChat, Baidu, and Toutiao |
| Global communities | Bundled `mvanhorn/last30days-skill` 3.31.0 snapshot | Reddit, Hacker News, GitHub, YouTube, X, and others depending on configured backends |
| RSS / Atom | Built-in collector and 14 default feeds | Chinese product, startup, market, and content sources; replaceable with JSON or OPML |

The adapter list does not mean every platform works without login. Each run preserves source status, including public-search fallback, login failure, and timeout. Undated results are not presented as recent posts, and missing engagement values are not filled with zero.

## Business and Creator Workflows

Version 1.1.0 adds evidence-led Chinese business and creator-content guidance. It helps the host model:

- Separate source observations from model interpretations and untested hypotheses.
- Evaluate user context, existing alternatives, observable payment signals, competitor friction, and counterevidence.
- Turn recurring user problems into audience-specific content angles and small, measurable content experiments.
- Preserve source coverage, publication-date confidence, original links, and platform-specific metrics.

Read the [business and content workflow](skills/research-hub/references/business-content-workflow.md) and [method source notes](skills/research-hub/references/method-sources.md). Business and content guidance uses the existing `evidence.json`; it does not change the collection pipeline.

The method review covered [dbskill](https://github.com/dontbesilent2025/dbskill) and [baoyu-skills](https://github.com/JimLiu/baoyu-skills). dbskill is licensed CC BY-NC 4.0, so its skill text and knowledge assets are not included or adapted in this MIT package. The new workflow is written for Research Hub's evidence schema. Baoyu is MIT; the referenced scope is documented in the source notes. No image generator or automated publishing workflow is bundled.

## Run Locally

From the repository root:

```bash
python3 skills/research-hub/scripts/research.py --diagnose

python3 skills/research-hub/scripts/research.py "solo founder tools" \
  --global-query "solopreneur tools" \
  --rss-query "一人公司" --rss-query "solopreneur" --rss-query "bootstrapping" \
  --quick
```

All three tracks run by default. Use `--scope cn`, `--scope global`, or `--scope rss` to limit collection. The date window is 1–30 days; for example, `--days 7 --as-of 2026-10-29`.

For complex topics, have Codex prepare a multi-angle global query plan and pass `--global-plan /absolute/path/plan.json`. See the [query planning format](skills/research-hub/references/planning.md). Without a plan, the script uses a clearly labeled single-query search.

To replace the RSS feeds:

```bash
python3 skills/research-hub/scripts/research.py "creator business" \
  --scope rss --feeds /absolute/path/feeds.opml \
  --rss-query "creator" --rss-query "创作者"
```

## Evidence and Limitations

Each run writes to a new `work/research-hub/<run>/` directory by default. Use `--out /absolute/new/directory` to select another path; existing runs are not overwritten.

- `evidence.json`: normalized records with deduplicated URLs and per-source dates, metrics, retrieval methods, and source record IDs.
- `evidence.md`: readable evidence excerpts and source coverage status.
- `raw/`: engine output, diagnostics, and logs.

The host Codex model performs the final analysis. Reposts are not independent confirmation; engagement metrics from different platforms are not added together; discussion volume does not establish market size or willingness to pay. RSS covers only entries currently returned by each feed.

## Configuration and Privacy

Existing configuration can be stored in `~/.config/last30days/.env`, `~/.config/last30days-cn/.env`, or process environment variables. See the [source configuration guide](skills/research-hub/references/sources.md).

Browser and cookie extraction are disabled by default. The skill does not create accounts or purchase services. Use `--allow-browser` only with explicit user authorization. `--public-only` ignores saved API configuration for a public-only run; configured paid backends may consume quota during normal use.

The repository contains code, public feed URLs, tests, and license files. It does not contain user API keys, cookies, login state, or research run results.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

Tests cover RSS/Atom parsing, date windows, unknown dates, cross-track deduplication, missing metrics, failure states, entity disambiguation, all three tracks, and output preservation. They use local HTTP fixtures and isolated engines; no external platform or API key is required. GitHub Actions runs the same checks.

## License and Attribution

The Research Hub code is MIT licensed. The bundled research engines and Bird subset retain their respective licenses and notices. See [third-party notices](THIRD_PARTY_NOTICES.md) and [Chinese documentation](README.zh-CN.md).
