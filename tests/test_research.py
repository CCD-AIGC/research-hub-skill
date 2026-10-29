import contextlib
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

SKILL = Path(os.environ.get("RESEARCH_HUB_TEST_ROOT") or
             Path(__file__).resolve().parents[1] / "skills" / "research-hub")
sys.path.insert(0, str(SKILL / "scripts"))
import research
import rss_sources as rss

RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Startup &amp; marketing</title><link>https://example.com/a?utm_source=rss</link>
<description><![CDATA[<p>Tools for solo founders</p><script>do not run</script>]]></description>
<pubDate>Wed, 28 Oct 2026 23:30:00 +0000</pubDate></item>
<item><title>Startup background</title><link>https://example.com/unknown</link></item>
<item><title>Startup old</title><link>https://example.com/old</link>
<pubDate>Fri, 01 May 2026 12:00:00 GMT</pubDate></item>
</channel></rss>"""
ATOM = b"""<feed xmlns="http://www.w3.org/2005/Atom"><entry>
<title>A useful update</title><link rel="self" href="/api/item.xml"/>
<link rel="alternate" href="/article"/><summary>AI startup</summary>
<updated>2026-10-28T23:50:00Z</updated></entry></feed>"""


class ParserTests(unittest.TestCase):
    def test_rss_text_and_date(self):
        rows = rss.parse_feed(RSS, "https://example.com/feed")
        self.assertEqual(rows[0]["title"], "Startup & marketing")
        self.assertNotIn("do not run", rows[0]["snippet"])
        self.assertEqual(rss.parse_date(rows[0]["published_at"]).date(), date(2026, 10, 29))
        self.assertIsNone(rows[1]["published_at"])

    def test_atom_prefers_article_and_marks_update_only(self):
        row = rss.parse_feed(ATOM, "https://example.com/feed")[0]
        self.assertEqual(row["url"], "https://example.com/article")
        self.assertEqual(row["date_kind"], "updated")
        self.assertEqual(row["date_confidence"], "low")

    def test_bad_xml_and_entity_rejected(self):
        for payload in [b"<html><body>login</body></html>",
                        b'<!DOCTYPE rss [<!ENTITY x "text">]><rss/>']:
            with self.assertRaises(ValueError):
                rss.parse_feed(payload, "https://example.com")

    def test_missing_link_is_not_reconstructed_from_title(self):
        self.assertEqual(rss.parse_feed(b"<rss><channel><item><title>no URL</title></item></channel></rss>",
                                        "https://example.com"), [])

    def test_keyword_boundaries(self):
        self.assertFalse(rss.keywords_match("email campaign", ["AI"]))
        self.assertEqual(rss.keywords_match("AI 工具用于一人公司", ["AI", "一人公司"]), ["ai", "一人公司"])

    def test_tracking_is_ignored_only_for_identity(self):
        self.assertEqual(rss.canonical_url("https://EXAMPLE.com/a/?utm_source=rss&x=2#top"),
                         "https://example.com/a?x=2")

    def test_credentials_and_non_http_rejected(self):
        self.assertFalse(rss.valid_url("https://user:password@example.com/feed"))
        self.assertFalse(rss.valid_url("javascript:alert(1)"))


class EvidenceTests(unittest.TestCase):
    def test_dedupe_preserves_track_specific_metrics(self):
        rows = [{"title": "Article", "url": "https://example.com/a?utm_source=rss",
                 "track": "rss", "source": "Blog", "date_status": "recent",
                 "engagement": {}, "published_at": "2026-10-29"},
                {"title": "Discussion", "url": "https://example.com/a",
                 "track": "global", "source": "hackernews", "date_status": "recent",
                 "engagement": {"score": 0}, "published_at": "2026-10-29"}]
        evidence = research.merge_evidence(rows)
        self.assertEqual(len(evidence), 1)
        self.assertEqual(len(evidence[0]["appearances"]), 2)
        self.assertEqual(evidence[0]["independent_confirmation"], "not-assessed")
        self.assertEqual(evidence[0]["appearances"][0]["engagement"], {})
        self.assertEqual(evidence[0]["appearances"][1]["engagement"]["score"], 0)

    def test_unknown_dates_fallback_and_out_of_window(self):
        payload = {"bilibili": [
            {"url": "https://example.com/unknown", "title": "Unknown"},
            {"url": "https://example.com/old", "date": "2025-01-01", "title": "Old"}],
            "source_status": {"bilibili": {"state": "ok", "via": {"site-search:ddg": 2}}}}
        rows, status = research.normalize_engine("cn", payload, ["bilibili"],
                                                 date(2026, 10, 1), date(2026, 10, 29))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["date_status"], "unknown")
        self.assertEqual(status[0]["state"], "partial")
        self.assertEqual(status[0]["outside_window"], 1)

    def test_missing_status_does_not_mean_no_results(self):
        _, status = research.normalize_engine("cn", {}, ["weibo"],
                                               date(2026, 10, 1), date(2026, 10, 29))
        self.assertEqual(status[0]["state"], "not-reported")

    def test_global_error_is_not_quiet_source(self):
        _, status = research.normalize_engine("global", {
            "items_by_source": {"reddit": []},
            "source_status": {"reddit": {"state": "rate-limited", "detail": "429"}}},
            [], date(2026, 10, 1), date(2026, 10, 29))
        self.assertEqual(status[0]["state"], "rate-limited")
        self.assertEqual(research.summarize_status(status, False), "error")

    def test_failure_does_not_hide_other_success(self):
        statuses = [research.outcome("cn", "weibo", "timeout"),
                    research.outcome("rss", "Blog", "ok")]
        self.assertEqual(research.summarize_status(statuses, True), "partial")

    def test_upstream_entity_miss_cannot_become_evidence(self):
        item = {"item_id": "1", "source": "hackernews", "url": "https://example.com/wrong",
                "title": "Wrong entity", "published_at": "2026-10-29", "date_confidence": "high"}
        payload = {"items_by_source": {"hackernews": [item]}, "ranked_candidates": [
            {"candidate_id": "c1", "final_score": 50, "explanation": "entity-miss",
             "source_items": [item]}], "source_status": {"hackernews": {"state": "ok"}}}
        rows, statuses = research.normalize_engine("global", payload, [],
                                                    date(2026, 10, 1), date(2026, 10, 29))
        self.assertEqual(rows, [])
        self.assertEqual(statuses[0]["rejected_by_upstream"], 1)


class Server(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/error":
            self.send_error(403)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/rss+xml")
        self.end_headers()
        self.wfile.write(RSS)

    def log_message(self, *args):
        pass


class EndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Server)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:" + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_feed_fetch_filters_dates_but_keeps_unknown_as_background(self):
        rows, status = rss.fetch_one({"name": "Fixture", "url": self.base, "group": "test"},
                                      ["startup"], date(2026, 10, 29), date(2026, 10, 29))
        self.assertEqual(status["state"], "ok")
        self.assertEqual(status["recent"], 1)
        self.assertEqual(status["undated"], 1)
        self.assertEqual(status["outside_window"], 1)
        self.assertEqual(len(rows), 2)

    def test_blocked_feed_reported(self):
        rows, status = rss.fetch_one({"name": "Blocked", "url": self.base + "/error", "group": "test"},
                                      [], date(2026, 10, 1), date(2026, 10, 29))
        self.assertEqual(rows, [])
        self.assertEqual(status["state"], "auth-failed")

    def test_cli_all_tracks_with_isolated_engine_contracts(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            # Stubs exercise subprocess, plan handoff and JSON contracts without external services.
            common = """import json,sys
if '--diagnose' in sys.argv:
 print(json.dumps({'available_sources':['hackernews']}));raise SystemExit
assert '--' in sys.argv
query=sys.argv[sys.argv.index('--')+1]
print(json.dumps(PAYLOAD))
"""
            cn = root / "cn.py"
            cn.write_text(common.replace("PAYLOAD", repr({
                "bilibili": [{"url": "https://example.com/a", "title": "Startup tool",
                              "date": "2026-10-29", "date_confidence": "high"}],
                "source_status": {"bilibili": {"state": "ok"}}})))
            global_engine = root / "global.py"
            global_engine.write_text(common.replace("PAYLOAD", repr({
                "items_by_source": {"hackernews": [{"item_id": "hn1", "source": "hackernews",
                    "url": "https://example.com/a", "title": "Startup tool",
                    "published_at": "2026-10-29", "date_confidence": "high", "engagement": {"score": 5}}]},
                "source_status": {"hackernews": {"state": "ok"}}})))
            feeds = root / "feeds.json"
            feeds.write_text(json.dumps([{"name": "Fixture", "url": self.base, "group": "test"}]))
            env = os.environ.copy()
            env.update(RESEARCH_HUB_CN_ENGINE=str(cn), RESEARCH_HUB_GLOBAL_ENGINE=str(global_engine))
            command = [sys.executable, str(SKILL / "scripts/research.py"), "startup",
                       "--global-query", "startup", "--cn-sources", "bilibili",
                       "--global-sources", "hackernews", "--feeds", str(feeds),
                       "--rss-query", "startup", "--as-of", "2026-10-29",
                       "--public-only", "--out", str(root / "run")]
            result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((root / "run/evidence.json").read_text())
            self.assertEqual(report["requested_tracks"], ["cn", "global", "rss"])
            self.assertEqual(set(x["track"] for x in report["source_status"]), {"cn", "global", "rss"})
            self.assertEqual(len([x for x in report["evidence"] if len(x["tracks"]) == 3]), 1)
            # Running with the same directory must preserve the first run.
            repeat = subprocess.run(command, env=env, capture_output=True, text=True, timeout=15)
            self.assertEqual(repeat.returncode, 2)
            self.assertIn("not be overwritten", repeat.stderr)

    def test_empty_opml_is_an_input_error(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "empty.opml"
            p.write_text("<opml><body/></opml>")
            with self.assertRaises(ValueError):
                rss.load_feeds(p)

    def test_domestic_reserved_words_remain_research_text(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            entry = SKILL / "engines/cn/scripts/last30days.py"
            code = """import runpy,sys
sys.path.insert(0,sys.argv[1])
from lib import pipeline,setup_wizard
def forbidden(*a,**k):raise RuntimeError('unexpected setup')
setup_wizard.run_auto_setup=forbidden
pipeline.run_sources=lambda *a,**k:{'bilibili':{'items':[],'state':'ok','via':{}}}
entry=sys.argv[2];topic=sys.argv[3]
sys.argv=[entry,'--research-only','--search','bilibili','--no-cache','--no-browser','--emit','json','--',topic]
runpy.run_path(entry,run_name='__main__')
"""
            env = os.environ.copy()
            env.update(LAST30DAYS_CN_CONFIG_DIR=str(root / "no-config"),
                       LAST30DAYS_CONFIG_DIR=str(root / "no-config"),
                       LAST30DAYS_OUTPUT_DIR=str(root / "out"), LAST30DAYS_DISABLE_BROWSER="1")
            for topic in ["setup", "login", "hot"]:
                result = subprocess.run([sys.executable, "-c", code, str(entry.parent), str(entry), topic],
                                        env=env, capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)["topic"], topic)


if __name__ == "__main__":
    unittest.main()
