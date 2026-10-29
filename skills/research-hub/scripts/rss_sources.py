"""Public RSS/Atom retrieval. Standard library only; no accounts or API keys."""
from __future__ import annotations

import concurrent.futures
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

SHANGHAI = timezone(timedelta(hours=8))
MAX_BYTES = 3_000_000


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def plain(value, limit=3000):
    parser = _Text()
    parser.feed(str(value or ""))
    return re.sub(r"\s+", " ", unescape(" ".join(parser.parts))).strip()[:limit]


def valid_url(value):
    try:
        text = str(value or "").strip()
        if re.search(r'[\s<>"\\]', text):
            return False
        url = urllib.parse.urlsplit(text)
        return url.scheme in {"http", "https"} and bool(url.hostname) and not (url.username or url.password)
    except ValueError:
        return False


def canonical_url(value):
    """Identity key only; citations always retain the original URL."""
    url = urllib.parse.urlsplit(value)
    pairs = [(k, v) for k, v in urllib.parse.parse_qsl(url.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}]
    return urllib.parse.urlunsplit((url.scheme.lower(), url.netloc.lower(),
                                   url.path.rstrip("/") or "/", urllib.parse.urlencode(sorted(pairs)), ""))


def parse_date(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        result = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            result = parsedate_to_datetime(text)
        except (ValueError, TypeError, OverflowError):
            return None
    if result.tzinfo is None:
        result = result.replace(tzinfo=SHANGHAI)
    return result.astimezone(SHANGHAI)


def keywords_match(text, keywords):
    text = text.casefold()
    found = []
    for word in keywords:
        word = word.strip().casefold()
        if not word:
            continue
        if re.search(r"[\u3400-\u9fff]", word):
            matches = word in text
        else:
            matches = re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", text) is not None
        if matches:
            found.append(word)
    return found


def _local(tag):
    return tag.rsplit("}", 1)[-1].lower()


def _child(element, names):
    for name in names:
        for child in element:
            if _local(child.tag) == name:
                value = "".join(child.itertext()).strip()
                if value:
                    return value
    return ""


def load_feeds(path):
    path = Path(path).expanduser()
    if path.suffix.lower() in {".opml", ".xml"}:
        data = path.read_bytes()
        _check_xml(data)
        root = ET.fromstring(data)
        feeds = [{"name": e.get("text") or e.get("title") or e.get("xmlUrl"),
                  "url": e.get("xmlUrl"), "group": "custom"}
                 for e in root.iter("outline") if e.get("xmlUrl")]
    else:
        feeds = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(feeds, list):
        raise ValueError("RSS source file must be a JSON list or an OPML file")
    result, seen = [], set()
    for feed in feeds:
        if not isinstance(feed, dict) or not valid_url(feed.get("url")):
            raise ValueError("Each RSS source needs a public HTTP(S) URL without embedded credentials")
        key = canonical_url(feed["url"])
        if key not in seen:
            result.append({"name": str(feed.get("name") or feed["url"]),
                           "url": feed["url"], "group": str(feed.get("group") or "custom")})
            seen.add(key)
    if not result:
        raise ValueError("RSS source file is empty")
    return result


def _check_xml(data):
    if len(data) > MAX_BYTES:
        raise ValueError("Feed exceeds 3 MB limit")
    if re.search(br"<!\s*(DOCTYPE|ENTITY)\b", data, re.I):
        raise ValueError("DTD/entity declarations are not supported")


def parse_feed(data, base_url):
    _check_xml(data)
    root = ET.fromstring(data)
    if _local(root.tag) not in {"rss", "feed", "rdf"}:
        raise ValueError("Response is not RSS/Atom")
    result = []
    for entry in root.iter():
        if _local(entry.tag) not in {"item", "entry"}:
            continue
        url = ""
        for child in entry:
            if _local(child.tag) != "link":
                continue
            if child.get("href") and child.get("rel", "alternate") == "alternate":
                url = child.get("href")
                break
            if child.text and child.text.strip():
                url = child.text.strip()
                break
        if not url:
            guid = next((e for e in entry if _local(e.tag) == "guid"), None)
            if guid is not None and guid.get("isPermaLink", "true").lower() != "false":
                url = guid.text or ""
        url = urllib.parse.urljoin(base_url, url) if url else ""
        if not valid_url(url):
            continue
        published = _child(entry, ["pubdate", "published", "date", "issued"])
        updated = _child(entry, ["updated", "modified"])
        stamp = parse_date(published) or parse_date(updated)
        date_kind = "published" if parse_date(published) else ("updated" if stamp else "unknown")
        result.append({
            "title": plain(_child(entry, ["title"]), 500) or url,
            "snippet": plain(_child(entry, ["description", "summary", "encoded", "content"])),
            "url": url,
            "published_at": stamp.isoformat() if stamp else None,
            "date_kind": date_kind,
            "date_confidence": "high" if date_kind == "published" else "low",
            "author": plain(_child(entry, ["author", "creator"]), 200),
        })
    return result


def fetch_one(feed, keywords, from_date, to_date, timeout=12, limit=15):
    status = {"track": "rss", "source": feed["name"], "feed_url": feed["url"],
              "state": "error", "attempted": True, "returned": 0, "kept": 0,
              "recent": 0, "undated": 0, "outside_window": 0,
              "retrieval_methods": ["rss/atom"]}
    try:
        request = urllib.request.Request(feed["url"], headers={
            "User-Agent": "ResearchHub/1.0 (public RSS research)",
            "Accept": "application/rss+xml,application/atom+xml,application/xml,text/xml;q=0.9"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            final_url = response.url
            if not valid_url(final_url):
                raise ValueError("Invalid feed redirect")
            rows = parse_feed(response.read(MAX_BYTES + 1), final_url)
        status["returned"] = len(rows)
        kept = []
        for row in rows:
            stamp = parse_date(row["published_at"])
            if stamp and not from_date <= stamp.date() <= to_date:
                status["outside_window"] += 1
                continue
            matched = keywords_match(row["title"] + " " + row["snippet"], keywords)
            if keywords and not matched:
                continue
            row.update(track="rss", source=feed["name"], source_id=feed["url"],
                       feed_url=feed["url"], group=feed["group"], engagement={},
                       matched_keywords=matched, retrieval_method="rss/atom",
                       date_status="recent" if stamp and row["date_kind"] == "published"
                       else ("updated-only" if stamp else "unknown"))
            kept.append(row)
        kept.sort(key=lambda row: (row["published_at"] or ""), reverse=True)
        kept = kept[:limit]
        status.update(state="ok" if kept else "no-results", kept=len(kept),
                      recent=sum(r["date_status"] == "recent" for r in kept),
                      undated=sum(r["date_status"] != "recent" for r in kept))
        return kept, status
    except urllib.error.HTTPError as exc:
        status.update(state="auth-failed" if exc.code in {401, 403} else
                      ("rate-limited" if exc.code == 429 else "error"), detail=f"HTTP {exc.code}")
    except (TimeoutError, OSError, ValueError, ET.ParseError) as exc:
        status.update(state="timeout" if isinstance(exc, TimeoutError) else "error",
                      detail=plain(str(exc), 400))
    return [], status


def collect(feeds, keywords, from_date, to_date, timeout=12, limit=15):
    results, statuses = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, len(feeds))) as pool:
        tasks = [pool.submit(fetch_one, f, keywords, from_date, to_date, timeout, limit) for f in feeds]
        for task in tasks:
            items, status = task.result()
            results.extend(items)
            statuses.append(status)
    return results, statuses
