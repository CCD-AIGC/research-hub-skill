#!/usr/bin/env python3
"""One research run across the bundled China/overseas engines and public feeds."""
from __future__ import annotations

import argparse
from collections import Counter
import concurrent.futures
from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time

from rss_sources import (SHANGHAI, canonical_url, collect, keywords_match, load_feeds,
                         parse_date, plain, valid_url)

ROOT = Path(__file__).resolve().parent.parent
VERSION = "1.1.0"
CN_SOURCES = ("weibo", "xiaohongshu", "bilibili", "zhihu", "douyin", "wechat", "baidu", "toutiao")
LABELS = dict(zip(CN_SOURCES, ("微博", "小红书", "B站", "知乎", "抖音", "微信公众号", "百度", "头条")))
SUCCESS = {"ok", "no-results"}


def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def engine_path(track):
    override = os.environ.get("RESEARCH_HUB_" + track.upper() + "_ENGINE")
    if override:
        path = Path(override).expanduser().resolve()
        if path.is_dir():
            path = path / "scripts" / "last30days.py"
    else:
        path = ROOT / "engines" / track / "scripts" / "last30days.py"
    return path if path.is_file() else None


def child_environment(args, run_dir=None):
    if args.public_only:
        keep = {"PATH", "LANG", "LC_ALL", "TMPDIR", "SSL_CERT_FILE", "SSL_CERT_DIR",
                "HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "NO_PROXY", "SYSTEMROOT"}
        env = {k: v for k, v in os.environ.items() if k in keep}
        # Use a nonexistent config location for both engines, without replacing HOME.
        clean = str((run_dir or ROOT) / ".no-user-config")
        env.update(LAST30DAYS_CONFIG_DIR=clean, LAST30DAYS_CN_CONFIG_DIR=clean,
                   LAST30DAYS_SKIP_KEYCHAIN="1")
    else:
        env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE="1", LAST30DAYS_MEMORY_DIR="",
               LAST30DAYS_LIBRARY_CONTEXT="off", LAST30DAYS_DISCOVERY_QUEUE="off",
               LAST30DAYS_TRUST_PROJECT_CONFIG="0")
    if not args.allow_browser:
        env.update(LAST30DAYS_DISABLE_BROWSER="1", FROM_BROWSER="off", AGENTCOOKIE="off")
    if args.native_search:
        env["LAST30DAYS_NATIVE_SEARCH"] = "1"
    else:
        env.pop("LAST30DAYS_NATIVE_SEARCH", None)
    if run_dir:
        env["LAST30DAYS_OUTPUT_DIR"] = str(run_dir / "raw" / "cn-render")
        env["LAST30DAYS_CACHE_DIR"] = str(run_dir / "raw" / "cn-cache")
    return env


def run_child(path, arguments, env, timeout):
    """Kill this process group on timeout, including any yt-dlp subprocess."""
    command = [sys.executable, str(path), *arguments]
    started = time.monotonic()
    process = subprocess.Popen(command, cwd=path.parent, env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8", errors="replace",
                               start_new_session=(os.name == "posix"))
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        return process.returncode, stdout, stderr, round(time.monotonic() - started, 2)
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            process.kill()
        stdout, stderr = process.communicate()
        return 124, stdout, stderr, round(time.monotonic() - started, 2)


def source_diagnostic(args, track, env):
    path = engine_path(track)
    if not path:
        return {"state": "missing-engine"}
    flags = ["--diagnose"] if track == "global" else ["--diagnose", "--emit", "json"]
    if track == "global":
        flags += ["--no-browser-cookies"]
    code, stdout, _, _ = run_child(path, flags, env, 25)
    try:
        return json.loads(stdout) if code == 0 else {"state": "error", "exit_code": code}
    except json.JSONDecodeError:
        return {"state": "schema-drift"}


def outcome(track, source, state, **extra):
    return {"track": track, "source": source, "state": state, "attempted": False,
            "returned": 0, "kept": 0, "recent": 0, "undated": 0, **extra}


def method_names(value):
    if isinstance(value, dict):
        return [str(k) for k in value]
    if isinstance(value, list):
        return [str(k) for k in value]
    return [str(value)] if value else []


def normalize_engine(track, payload, requested, from_date, to_date):
    statuses, rows = [], []
    source_data = payload.get("items_by_source", {}) if track == "global" else {
        sid: payload.get(sid, []) for sid in CN_SOURCES if sid in requested}
    if not isinstance(source_data, dict):
        raise ValueError("Engine returned an unsupported source schema")
    candidate_map = {}
    accepted_global_items = set()
    rejected_clusters = {cid for cluster in payload.get("clusters", [])
                         if cluster.get("score", 0) <= 0
                         for cid in cluster.get("candidate_ids", [])}
    for candidate in payload.get("ranked_candidates", []):
        accepted = ((candidate.get("final_score") or 0) > 0 and
                    "entity-miss" not in (candidate.get("explanation") or "").lower() and
                    candidate.get("candidate_id") not in rejected_clusters)
        for item in candidate.get("source_items", []):
            key = (item.get("source"), item.get("item_id"))
            candidate_map[key] = candidate.get("final_score")
            if accepted:
                accepted_global_items.add(key)
    raw_states = payload.get("source_status", {}) or {}
    keys = set(source_data) | set(raw_states) | set(requested)
    for sid in sorted(keys):
        items = source_data.get(sid, []) or []
        raw = raw_states.get(sid, {}) or {}
        if isinstance(raw, str):
            raw = {"state": raw}
        state = raw.get("state") or ("not-reported" if not items else "ok")
        if state == "empty":
            state = "no-results"
        detail = raw.get("detail") or raw.get("error") or (
            payload.get("errors_by_source", {}).get(sid) if track == "global"
            else payload.get(sid + "_error"))
        if detail and state == "not-reported":
            state = "error"
        methods = method_names(raw.get("via"))
        fallback = any(re.search(r"fallback|site.search|hot|web.search|公开搜索|热榜", m, re.I) for m in methods)
        status = outcome(track, sid, "partial" if fallback and state == "ok" else state,
                         label=LABELS.get(sid, sid), attempted=raw.get("attempted", True),
                         returned=len(items), retrieval_methods=methods, detail=detail,
                         from_cache=bool(payload.get("from_cache")))
        for item in items:
            if not isinstance(item, dict) or not valid_url(item.get("url")):
                continue
            if (track == "global" and "ranked_candidates" in payload and
                    (sid, item.get("item_id")) not in accepted_global_items):
                status["rejected_by_upstream"] = status.get("rejected_by_upstream", 0) + 1
                continue
            date_text = item.get("published_at") or item.get("date")
            stamp = parse_date(date_text)
            if stamp and not from_date <= stamp.date() <= to_date:
                status["outside_window"] = status.get("outside_window", 0) + 1
                continue
            confidence = item.get("date_confidence", "low")
            observed_only = track == "cn" and bool(
                re.search(r"热榜|热搜", item.get("why_relevant") or "") or
                re.search(r"/hot/|/hot\?", item["url"]))
            dated = bool(stamp and confidence in {"high", "med"} and not observed_only)
            title = item.get("title") or item.get("text") or item.get("url")
            snippet = next((item.get(k) for k in (
                "snippet", "body", "description", "desc", "excerpt", "abstract", "text")
                            if item.get(k)), "")
            meta = item.get("metadata") or {}
            rows.append({
                "track": track, "source": sid, "source_id": item.get("item_id") or item.get("id"),
                "title": plain(title, 500), "snippet": plain(snippet),
                "url": item["url"], "published_at": stamp.isoformat() if stamp else None,
                "date_status": "recent" if dated else ("observed-only" if stamp and observed_only
                                                       else ("low-confidence" if stamp else "unknown")),
                "date_confidence": confidence,
                "date_kind": "observation" if observed_only else "engine-reported",
                "author": item.get("author") or item.get("author_name") or
                          item.get("author_handle") or item.get("channel_name") or item.get("source_name"),
                "engagement": item.get("engagement") or {},
                "retrieval_method": ", ".join(methods) or "engine",
                "limited": fallback, "from_cache": bool(payload.get("from_cache")),
                "upstream_score": candidate_map.get((sid, item.get("item_id")), item.get("score")),
                "upstream_relevance": item.get("local_relevance", item.get("relevance")),
                "why_relevant": item.get("why_relevant"),
                "comments": meta.get("top_comments") or item.get("top_comments") or [],
                "metadata": meta,
            })
            status["kept"] += 1
            status["recent" if dated else "undated"] += 1
        statuses.append(status)
    return rows, statuses


def collect_engine(track, args, run_dir, from_date, to_date):
    path = engine_path(track)
    if not path:
        return [], [outcome(track, track, "missing-engine")]
    if track == "global" and not args.global_query:
        return [], [outcome(track, track, "needs-query", detail="Provide concise English --global-query")]
    env = child_environment(args, run_dir)
    query = args.global_query if track == "global" else args.topic
    flags = [query, "--emit", "json", "--days", str(args.days), "--as-of", to_date.isoformat()]
    requested = list(CN_SOURCES) if track == "cn" else []
    if track == "cn":
        requested = [s.strip() for s in args.cn_sources.split(",") if s.strip()]
        flags += ["--research-only", "--search", ",".join(requested), "--no-cache",
                  "--timeout", str(max(5, args.timeout - 5))]
        if not args.allow_browser:
            flags += ["--no-browser"]
    else:
        flags += ["--research-only", "--json-profile", "raw", "--save-dir", ""]
        if not args.allow_browser:
            flags += ["--no-browser-cookies"]
        if args.global_sources:
            requested = [s.strip() for s in args.global_sources.split(",") if s.strip()]
            flags += ["--search", ",".join(requested)]
        diag = source_diagnostic(args, "global", env)
        dump(run_dir / "raw" / "global-diagnostic.json", diag)
        available = diag.get("available_sources", [])
        plan_path = args.global_plan
        if plan_path:
            plan = json.loads(Path(plan_path).expanduser().read_text(encoding="utf-8"))
            # Preserve exactly the host's plan and source choices.
        else:
            chosen = requested or available
            if not chosen:
                return [], [outcome(track, track, "unavailable", detail="No available overseas source")]
            plan = {"intent": "concept", "freshness_mode": "strict_recent", "cluster_mode": "market",
                    "subqueries": [{"label": "primary", "search_query": query,
                                    "ranking_query": args.topic, "sources": chosen, "weight": 1.0}]}
        effective_plan = run_dir / "raw" / "global-plan.json"
        dump(effective_plan, plan)
        flags += ["--plan", str(effective_plan)]
        # Do not claim general web coverage unless the host will actually supplement it.
    if args.quick:
        flags += ["--quick"]
    elif args.deep:
        flags += ["--deep"]
    # Topic text cannot become an engine flag, including literal '--diagnose'.
    flags = flags[1:] + ["--", flags[0]]
    code, stdout, stderr, elapsed = run_child(path, flags, env, args.timeout)
    (run_dir / "raw" / (track + ".stdout")).write_text(stdout, encoding="utf-8")
    (run_dir / "raw" / (track + ".log")).write_text(stderr, encoding="utf-8")
    if code:
        return [], [outcome(track, sid, "timeout" if code == 124 else "error",
                           attempted=True, elapsed_seconds=elapsed, exit_code=code,
                           detail="See raw/" + track + ".log") for sid in (requested or [track])]
    try:
        payload = json.loads(stdout)
        if not isinstance(payload, dict) or (
                track == "global" and "items_by_source" not in payload):
            raise ValueError("Unsupported engine report (local Report required)")
        dump(run_dir / "raw" / (track + ".json"), payload)
        rows, states = normalize_engine(track, payload, requested, from_date, to_date)
        for state in states:
            state["elapsed_seconds"] = elapsed
        return rows, states
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        return [], [outcome(track, track, "schema-drift", attempted=True, detail=str(exc))]


def merge_evidence(rows):
    merged = {}
    for row in rows:
        key = canonical_url(row["url"])
        if key not in merged:
            merged[key] = {"id": "E" + hashlib.sha256(key.encode()).hexdigest()[:10],
                           "title": row["title"], "url": row["url"],
                           "snippet": row.get("snippet", ""), "appearances": []}
        entry = merged[key]
        entry["appearances"].append({k: v for k, v in row.items() if k not in {"title", "snippet", "url"}})
        if len(row.get("snippet", "")) > len(entry["snippet"]):
            entry["snippet"] = row["snippet"]
    result = list(merged.values())
    for item in result:
        item["tracks"] = sorted({x["track"] for x in item["appearances"]})
        item["sources"] = sorted({x["source"] for x in item["appearances"]})
        item["has_recent_evidence"] = any(x["date_status"] == "recent" for x in item["appearances"])
        item["independent_confirmation"] = "not-assessed"
    # A selection order, never a popularity/sentiment/market-size score.
    result.sort(key=lambda x: (x["has_recent_evidence"], len(x["tracks"]),
                              max((a.get("published_at") or "" for a in x["appearances"]), default="")),
                reverse=True)
    return result


def summarize_status(statuses, has_items):
    if not statuses:
        return "error"
    good = sum(s["state"] in SUCCESS for s in statuses)
    bad = len(statuses) - good
    if bad:
        return "partial" if good or has_items else "error"
    return "ok" if has_items else "no-results"


def markdown(report, limit=80):
    lines = ["# 全域调研证据", "", "主题：" + report["topic"],
             "时间窗口：" + report["window"]["from"] + " 至 " + report["window"]["to"] + "（北京时间，含首尾日期）",
             "整体状态：" + report["status"], "",
             "这是待分析的证据包；同链接多次出现仅表示被不同来源收录，不代表独立证实。", "",
             "## 来源覆盖", "", "| 渠道 | 来源 | 状态 | 保留 / 返回 | 可靠日期 / 日期待核 | 获取方式 |",
             "|---|---|---|---:|---:|---|"]
    def cell(value):
        return plain(value, 500).replace("|", "\\|").replace("\n", " ")
    for status in report["source_status"]:
        lines.append("| " + " | ".join(map(cell, [
            status["track"], status.get("label") or status["source"], status["state"],
            f'{status["kept"]} / {status["returned"]}', f'{status["recent"]} / {status["undated"]}',
            ", ".join(status.get("retrieval_methods", [])) or status.get("detail") or "engine"])) + " |")
    lines += ["", "## 证据条目", ""]
    for item in report["evidence"][:limit]:
        title = cell(item["title"]).replace("[", "\\[").replace("]", "\\]")
        lines += [f'### [{item["id"]}] [{title}](<{item["url"]}>)', "",
                  cell(item["snippet"]), ""]
        for appearance in item["appearances"]:
            metrics = json.dumps(appearance.get("engagement", {}), ensure_ascii=False)
            lines.append("- " + cell(
                f'{appearance["track"]}/{appearance["source"]} · '
                f'{appearance.get("published_at") or "日期未知"} · {appearance["date_status"]} · '
                f'{appearance.get("retrieval_method", "engine")} · 互动数据 {metrics}'))
        lines.append("")
    if len(report["evidence"]) > limit:
        lines.append(f'其余 {len(report["evidence"]) - limit} 条见 evidence.json。')
    if report["warnings"]:
        lines += ["", "## 资料限制", ""] + ["- " + cell(x) for x in report["warnings"]]
    return "\n".join(lines) + "\n"


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("topic", nargs="?", default="")
    p.add_argument("--scope", choices=["all", "cn", "global", "rss"], default="all")
    p.add_argument("--global-query", default="")
    p.add_argument("--global-plan", help="Host-authored overseas query-plan JSON file")
    p.add_argument("--global-sources", help="Comma-separated exact overseas source selection")
    p.add_argument("--cn-sources", default=",".join(CN_SOURCES))
    p.add_argument("--rss-query", action="append", default=[], help="Repeat concise bilingual keyword phrases (OR)")
    p.add_argument("--feeds", default=str(ROOT / "references" / "rss-feeds.json"), help="JSON or OPML feed list")
    p.add_argument("--days", type=int, choices=range(1, 31), default=30, metavar="1-30")
    p.add_argument("--as-of", help="YYYY-MM-DD, interpreted in Asia/Shanghai")
    depth = p.add_mutually_exclusive_group()
    depth.add_argument("--quick", action="store_true")
    depth.add_argument("--deep", action="store_true")
    p.add_argument("--timeout", type=int, default=180, help="Per-engine seconds; a failed engine does not stop others")
    p.add_argument("--rss-timeout", type=int, default=12)
    p.add_argument("--out", help="New run directory; defaults to a unique directory under ./work/research-hub")
    p.add_argument("--diagnose", action="store_true", help="Inspect bundled runtimes and engine source availability")
    p.add_argument("--public-only", action="store_true", help="Ignore saved API/config credentials for this run")
    p.add_argument("--allow-browser", action="store_true", help="Only after explicit user authorization")
    p.add_argument("--native-search", action="store_true", help="Host will separately fetch web supplements")
    p.add_argument("--emit", choices=["compact", "json"], default="compact")
    return p


def main(argv=None):
    p = parser()
    args = p.parse_args(argv)
    if sys.version_info < (3, 12):
        p.error("Bundled overseas engine requires Python 3.12+")
    if not 5 <= args.timeout <= 1800 or not 1 <= args.rss_timeout <= 60:
        p.error("timeout must be 5..1800; rss-timeout must be 1..60")
    if args.public_only and args.allow_browser:
        p.error("--public-only cannot be combined with --allow-browser")
    unknown = set(args.cn_sources.split(",")) - set(CN_SOURCES)
    if unknown:
        p.error("Unknown domestic sources: " + ", ".join(sorted(unknown)))
    try:
        to_date = datetime.strptime(args.as_of, "%Y-%m-%d").date() if args.as_of else datetime.now(SHANGHAI).date()
        feeds = load_feeds(args.feeds) if args.scope in {"all", "rss"} or args.diagnose else []
        if args.global_plan:
            plan = json.loads(Path(args.global_plan).expanduser().read_text(encoding="utf-8"))
            if not isinstance(plan, dict) or not plan.get("subqueries"):
                raise ValueError("Global plan needs a nonempty subqueries array")
    except (ValueError, OSError) as exc:
        p.error(str(exc))
    if args.diagnose:
        env = child_environment(args)
        result = {"version": VERSION, "python": sys.version.split()[0],
                  "engines": {t: {"path": str(engine_path(t) or ""), "bundled": not bool(
                      os.environ.get("RESEARCH_HUB_" + t.upper() + "_ENGINE"))} for t in ["cn", "global"]},
                  "rss_feeds": len(feeds), "browser_access": args.allow_browser}
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = {t: pool.submit(source_diagnostic, args, t, env) for t in ["cn", "global"]}
            result["source_availability"] = {t: f.result() for t, f in futures.items()}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if not args.topic.strip():
        p.error("A research topic is required")
    if not args.global_query and not re.search(r"[\u3400-\u9fff]", args.topic):
        args.global_query = args.topic
    from_date = to_date - timedelta(days=args.days - 1)
    if args.out:
        run_dir = Path(args.out).expanduser().resolve()
        try:
            run_dir.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            p.error("--out must name a new directory; existing research will not be overwritten")
    else:
        base = Path.cwd() / "work" / "research-hub"
        base.mkdir(parents=True, exist_ok=True)
        run_dir = Path(tempfile.mkdtemp(prefix=datetime.now(SHANGHAI).strftime("%Y%m%d-%H%M%S-"), dir=base))
    (run_dir / "raw").mkdir()
    keywords = args.rss_query or [args.topic, *([args.global_query] if args.global_query else [])]
    tracks = ["cn", "global", "rss"] if args.scope == "all" else [args.scope]
    rows, statuses, warnings = [], [], []
    started = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        tasks = {}
        for track in tracks:
            if track == "rss":
                tasks[track] = pool.submit(collect, feeds, keywords, from_date, to_date, args.rss_timeout,
                                          8 if args.quick else (30 if args.deep else 15))
            else:
                tasks[track] = pool.submit(collect_engine, track, args, run_dir, from_date, to_date)
        for track, task in tasks.items():
            try:
                items, states = task.result()
            except Exception as exc:
                items, states = [], [outcome(track, track, "error", detail=plain(str(exc), 500))]
            rows.extend(items)
            statuses.extend(states)
            print(f'[{track}] {len(items)} items; ' + ", ".join(
                f'{s}:{n}' for s, n in Counter(x["state"] for x in states).items()), file=sys.stderr, flush=True)
            if track == "rss":
                dump(run_dir / "raw" / "rss.json", {"items": items, "source_status": states})
    evidence = merge_evidence(rows)
    if any(s["state"] not in SUCCESS for s in statuses):
        warnings.append("存在受限、降级、超时或未配置来源；失败不代表该平台无人讨论。详见 source_status。")
    if any(s.get("undated", 0) for s in statuses):
        warnings.append("日期未知、低置信日期、热榜观察日期和仅更新时间的条目作为背景线索，不能计作近期发文。")
    if args.scope in {"all", "rss"}:
        warnings.append("RSS 仅覆盖各订阅当前返回的文章，不能保证完整的历史时间窗口；互动数据为空不代表互动为零。")
    if args.scope in {"all", "global"} and not args.global_plan:
        warnings.append("海外采用单关键词查询计划；复杂实体应由主持模型补充消歧和多角度 --global-plan。")
    report = {"schema_version": "research-hub/v1", "version": VERSION, "topic": args.topic,
              "global_query": args.global_query, "rss_queries": keywords,
              "generated_at": datetime.now(SHANGHAI).isoformat(),
              "window": {"from": from_date.isoformat(), "to": to_date.isoformat(), "days": args.days,
                         "timezone": "Asia/Shanghai"},
              "status": summarize_status(statuses, bool(evidence)), "requested_tracks": tracks,
              "source_status": statuses, "evidence": evidence, "warnings": warnings,
              "stats": {"raw_appearances": len(rows), "unique_urls": len(evidence),
                        "recent_evidence": sum(x["has_recent_evidence"] for x in evidence),
                        "elapsed_seconds": round(time.monotonic() - started, 2)},
              "artifacts": {"directory": str(run_dir), "json": str(run_dir / "evidence.json"),
                            "markdown": str(run_dir / "evidence.md")}}
    dump(run_dir / "evidence.json", report)
    (run_dir / "evidence.md").write_text(markdown(report), encoding="utf-8")
    if args.emit == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f'Research Hub {VERSION} | {report["status"]} | {len(evidence)} unique URLs')
        print("JSON: " + report["artifacts"]["json"])
        print("Evidence: " + report["artifacts"]["markdown"])
        for warning in warnings:
            print("- " + warning)
    return 1 if report["status"] == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
