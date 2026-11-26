"""Causal current-news observations, deliberately separate from qualified strategy evidence."""

from __future__ import annotations

import fcntl
import hashlib
import json
import math
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import UTC, datetime
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from importlib.metadata import version
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from xml.etree import ElementTree

import feedparser
import pandas as pd
import trafilatura
from lxml import html

from fundamental_event_trader.news_io import Reader, public_url
from fundamental_event_trader.news_sources import ENTITIES, SOURCES, TOPICS
from fundamental_event_trader.sec import DataGateError, sha, timestamp

REFRESH_HOURS = 1
NEWS_LIMITS = [
    "Current public-news observations, not a validated trading strategy or allocation signal.",
    "Topic and entity tags are transparent dictionary matches, not sentiment or verified security identities.",
    "Grouped coverage can be syndicated; multiple publishers are not independent confirmations.",
    "Publisher publication time is distinct from first observation and each content version's availability.",
    "Newly collected stories cannot be backfilled into historical model decisions.",
    "Issuer releases are interested-party claims, not independent confirmation.",
]


def clean_text(value):
    try:
        node = html.fromstring("<div>" + str(value or "")[:200_000] + "</div>")
        for child in node.xpath(".//script|.//style"):
            child.drop_tree()
        return " ".join(node.text_content().split())
    except (ValueError, TypeError):
        return ""


def canonical(url):
    part = urlsplit(url)
    query = [(key, value) for key, value in parse_qsl(part.query, keep_blank_values=True)
             if not key.lower().startswith(("utm_", "cmp", "ref_")) and key.lower() not in {"fbclid", "gclid", "guccounter"}]
    return urlunsplit((part.scheme.lower(), part.netloc.lower(), part.path or "/", urlencode(query), ""))


def published(value):
    if not value:
        raise DataGateError("Missing publisher publication time")
    try:
        stamp = pd.Timestamp(parsedate_to_datetime(value))
    except (ValueError, TypeError, OverflowError):
        stamp = pd.Timestamp(value)
    return timestamp(stamp)


def tags(text):
    text = text.casefold()

    def matches(terms):
        return [term for term in terms if re.search(r"(?<!\w)" + re.escape(term) + r"\w*", text)]

    return ({name: found for name, terms in TOPICS.items() if (found := matches(terms))},
            [name for name, terms in ENTITIES.items() if matches(terms)])


def content_kind(row):
    if row["source_kind"] in {"issuer_release_wire", "issuer_newsroom"}:
        if re.search(r"investor alert|shareholder alert|law firm|class action|reminds investors|securities fraud|shareholder deadline", row["title"], re.I):
            return "legal_solicitation_or_announcement"
        return "issuer_statement"
    return "official_announcement" if row["source_kind"] == "official_release" else "publisher_reporting_or_commentary"


def parse_feed(raw, source, now, *, lookback_hours=72):
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise DataGateError("Entity-bearing news feed prohibited")
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError as exc:
        raise DataGateError("News feed must be XML bytes, never a URL to fetch") from exc
    if root.tag.rsplit("}", 1)[-1].lower() not in {"rss", "feed", "rdf"}:
        raise DataGateError("Unsupported news document root")
    parsed = feedparser.parse(raw)
    if not parsed.version or not parsed.entries:
        raise DataGateError("Source is not a nonempty RSS or Atom feed")
    clock, rows, rejected = timestamp(now), [], Counter()
    for entry in parsed.entries[:100]:
        try:
            link = canonical(public_url(entry.get("link", ""), source.hosts))
            title = clean_text(entry.get("title"))
            pub = published(entry.get("published"))
            if not title:
                raise DataGateError("Missing news headline")
            if pub > clock:
                raise DataGateError("Future-dated publisher timestamp")
            if pub < clock - pd.Timedelta(hours=lookback_hours):
                rejected["outside_lookback"] += 1
                continue
            summary = clean_text(entry.get("summary"))
            rows.append({"url": link, "title": title, "feed_summary": summary,
                         "published_at_utc": pub.isoformat(), "source_id": source.id,
                         "source": source.name, "source_kind": source.kind})
        except (ValueError, TypeError, OverflowError) as exc:
            rejected[str(exc)[:100]] += 1
    return rows, dict(rejected)


def article_text(raw):
    if len(raw) > 2_000_000:
        raise DataGateError("Oversized public article")
    node = html.fromstring(raw)

    def restricted(value):
        if isinstance(value, dict):
            flag = value.get("isAccessibleForFree")
            if flag is False or (isinstance(flag, str) and flag.lower() == "false"):
                return True
            return any(restricted(v) for v in value.values())
        return isinstance(value, list) and any(restricted(v) for v in value)

    for script in node.xpath("//script[@type='application/ld+json']"):
        try:
            if restricted(json.loads(script.text or "{}")):
                raise DataGateError("Publisher marks the article as restricted; headline only")
        except json.JSONDecodeError:
            continue
    text = trafilatura.extract(raw, include_comments=False, include_tables=False,
                               include_links=False, favor_precision=True) or ""
    if len(text.split()) < 80:
        raise DataGateError("Insufficient accessible article body; headline only")
    if any(term in text.lower() for term in ("subscribe to continue reading", "sign in to continue reading", "purchase a subscription to read")):
        raise DataGateError("Subscription boundary; no access workaround")
    return text[:150_000]


def observe(connection, item, clock):
    identity = hashlib.sha256((item["source_id"] + "\0" + item["url"]).encode()).hexdigest()
    first_observed = timestamp(item.get("feed_observed_at_utc", clock))
    connection.execute("INSERT OR IGNORE INTO articles VALUES (?, ?)", (identity, first_observed.isoformat()))
    first = connection.execute("SELECT first_seen FROM articles WHERE id=?", (identity,)).fetchone()[0]
    connection.execute("INSERT OR IGNORE INTO versions VALUES (?, ?, ?)", (identity, item["content_sha256"], clock.isoformat()))
    version = connection.execute("SELECT first_seen FROM versions WHERE id=? AND content=?", (identity, item["content_sha256"])).fetchone()[0]
    if timestamp(first) > clock or timestamp(version) > clock:
        raise DataGateError("News observation clock precedes existing archive")
    item |= {"id": identity, "first_seen_at_utc": first, "version_first_seen_at_utc": version,
             "available_at_utc": max(timestamp(item["published_at_utc"]), timestamp(version)).isoformat()}


def group_items(rows):
    groups = []
    for row in sorted(rows, key=lambda r: (r["published_at_utc"], r["id"]), reverse=True):
        words = " ".join(re.findall(r"\w+", row["title"].lower()))
        entities = set(row.get("entities", []))
        group = next((g for g in groups if (words == g["normalized_title"] or
                      (entities and entities == set(g["entities"]) and SequenceMatcher(None, words, g["normalized_title"]).ratio() >= .95))
                      and abs((timestamp(g["published_at_utc"]) - timestamp(row["published_at_utc"])).total_seconds()) <= 172800), None)
        if group is None:
            group = {"normalized_title": words, "published_at_utc": row["published_at_utc"], "ids": [], "entities": sorted(entities)}
            groups.append(group)
        group["ids"].append(row["id"])
        row["coverage_group"] = group["ids"][0]
    return len(groups)


def version_identity(row):
    value = {"title": row["title"], "feed_summary_sha256": row["feed_summary_sha256"],
             "body_sha256": row.get("body_sha256")}
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def verify(folder):
    meta = json.loads((folder / "manifest.json").read_text())
    if (meta.get("kind") != "public_news_observation" or meta.get("action_authorized") is not False
            or meta.get("historical_strategy_evidence") is not False
            or "items.json" not in meta.get("artifacts", {})):
        raise DataGateError("Invalid news observation authority")
    clock = timestamp(meta["captured_at_utc"])
    for name, expected in meta["artifacts"].items():
        file = (folder / name).resolve()
        if not file.is_relative_to(folder.resolve()) or not file.is_file() or sha(file) != expected:
            raise DataGateError("News source artifact integrity failure")
    for row in json.loads((folder / "items.json").read_text()):
        if not (timestamp(row["published_at_utc"]) <= timestamp(row["available_at_utc"]) <= clock
                and timestamp(row["first_seen_at_utc"]) <= timestamp(row["version_first_seen_at_utc"]) <= timestamp(row["available_at_utc"])):
            raise DataGateError("News availability or version timestamps are not causal")
        if meta["artifacts"].get(row["feed_path"]) != row["feed_sha256"]:
            raise DataGateError("News story lacks bound feed evidence")
        if row["coverage"] == "article_read":
            file = folder / row["body_path"]
            if row["body_path"] not in meta["artifacts"] or sha(file) != row.get("body_sha256", row["content_sha256"]):
                raise DataGateError("Read article lacks bound body evidence")
        if row.get("content_signature_version") == 2 and version_identity(row) != row["content_sha256"]:
            raise DataGateError("News version omits a headline or summary revision")
    return meta


def refresh(root: Path, output: Path, *, sources=SOURCES, max_articles=12, budget=75., now=None, reader=None):
    if isinstance(max_articles, bool) or not isinstance(max_articles, int) or not 0 <= max_articles <= 40:
        raise DataGateError("Bound article reads between zero and forty")
    if isinstance(budget, bool) or not math.isfinite(budget) or not 1 <= budget <= 180:
        raise DataGateError("News time budget must be between one and 180 seconds")
    if len({s.id for s in sources}) != len(sources) or any(not re.fullmatch(r"[a-z0-9_]{1,64}", s.id) for s in sources):
        raise DataGateError("Unique safe public-source identities required")
    clock = timestamp(now or datetime.now(UTC))
    output.mkdir(parents=True, exist_ok=False)
    client = reader or Reader(output, budget=budget)
    rows, health, source_by_id = [], [], {s.id: s for s in sources}
    for source in sources:
        record = {"source_id": source.id, "source": source.name, "kind": source.kind,
                  "feed": source.feed, "status": "unavailable", "items": 0}
        try:
            raw, _ = client.get(source.feed, source.hosts)
            feed_file = output / "feeds" / f"{source.id}.xml"
            feed_file.parent.mkdir(exist_ok=True)
            feed_file.write_bytes(raw)
            observed = timestamp(now or datetime.now(UTC))
            found, rejected = parse_feed(raw, source, observed)
            for row in found:
                row |= {"feed_path": str(feed_file.relative_to(output)), "feed_sha256": sha(feed_file),
                        "feed_observed_at_utc": observed.isoformat()}
            rows.extend(found)
            record |= {"status": "available" if found else "no_recent_items", "items": len(found), "excluded": rejected}
        except (OSError, ValueError, TypeError) as exc:
            record["error"] = str(exc)[:220]
        health.append(record)
    rows = list({(row["source_id"], row["url"]): row for row in rows}.values())
    candidates = defaultdict(list)
    for row in rows:
        row["topics"], row["entities"] = tags(row["title"] + " " + row["feed_summary"])
        row["coverage"] = "headline_and_feed_summary"
        if source_by_id[row["source_id"]].read_articles:
            candidates[row["source_id"]].append(row)
    for values in candidates.values():
        values.sort(key=lambda r: (bool(r["topics"]), r["published_at_utc"]), reverse=True)
    selected = []
    while len(selected) < max_articles and any(candidates.values()):
        for values in candidates.values():
            if values and len(selected) < max_articles:
                selected.append(values.pop(0))
    for row in selected:
        try:
            raw, _ = client.get(row["url"], source_by_id[row["source_id"]].hosts)
            text = article_text(raw)
            digest = hashlib.sha256(text.encode()).hexdigest()
            file = output / "articles" / f"{digest}.txt"
            file.parent.mkdir(exist_ok=True)
            file.write_text(text)
            row |= {"coverage": "article_read", "body_path": str(file.relative_to(output)),
                    "body_sha256": digest, "body_words": len(text.split()),
                    "version_observed_at_utc": timestamp(now or datetime.now(UTC)).isoformat()}
            row["topics"], row["entities"] = tags(row["title"] + " " + text)
        except (OSError, ValueError, TypeError) as exc:
            row["article_read_error"] = str(exc)[:180]
    database = root / "data/news/observations.sqlite3"
    database.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS articles(id TEXT PRIMARY KEY, first_seen TEXT NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS versions(id TEXT NOT NULL, content TEXT NOT NULL, first_seen TEXT NOT NULL, PRIMARY KEY(id,content))")
        for row in rows:
            row["feed_summary_sha256"] = hashlib.sha256(row["feed_summary"].encode()).hexdigest()
            row["content_signature_version"] = 2
            row["content_sha256"] = version_identity(row)
            observe(conn, row, timestamp(row.get("version_observed_at_utc", row["feed_observed_at_utc"])))
    groups = group_items(rows)
    # Display bounded attributed extracts; keep complete read bodies in the local archive only.
    for row in rows:
        title = row["title"].split()[:24]
        row["display_title"] = " ".join(title)
        row["display_excerpt"] = " ".join(row["feed_summary"].split()[:max(0, 24 - len(title))])
        row["content_kind"] = content_kind(row)
        row.pop("feed_summary")
    rows.sort(key=lambda r: (bool(r["topics"]), r["published_at_utc"]), reverse=True)
    (output / "items.json").write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n")
    (output / "sources.json").write_text(json.dumps(health, indent=2, sort_keys=True) + "\n")
    (output / "requests.json").write_text(json.dumps(client.requests, indent=2, sort_keys=True) + "\n")
    captured = timestamp(now or datetime.now(UTC))
    meta = {"schema_version": 1, "kind": "public_news_observation", "started_at_utc": clock.isoformat(),
            "captured_at_utc": captured.isoformat(), "authority": "observation_only", "action_authorized": False,
            "historical_strategy_evidence": False, "item_count": len(rows), "coverage_groups": groups,
            "extractors": {name: version(name) for name in ("feedparser", "trafilatura")},
            "sources": [s.specification() for s in sources],
            "artifacts": {str(p.relative_to(output)): sha(p) for p in sorted(output.rglob("*")) if p.is_file()}}
    (output / "manifest.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
    verify(output)
    pointer = {"report": str(output.resolve()), "manifest_sha256": sha(output / "manifest.json")}
    base = root / "data/news"
    temporary = base / "latest.tmp"
    temporary.write_text(json.dumps(pointer, indent=2) + "\n")
    temporary.replace(base / "latest.json")
    if rows:
        temporary = base / "latest-usable.tmp"
        temporary.write_text(json.dumps(pointer, indent=2) + "\n")
        temporary.replace(base / "latest-usable.json")
    return output


def status(root: Path, *, now=None):
    clock = timestamp(now or datetime.now(UTC))
    result = {"schema_version": 1, "status": "not_collected", "refresh_due": True,
              "authority": "observation_only", "action_authorized": False, "historical_strategy_evidence": False,
              "items": [], "sources": [], "article_bodies_read": 0, "limits": NEWS_LIMITS}
    pointer = root / "data/news/latest.json"
    if not pointer.is_file():
        return result
    try:
        spec = json.loads(pointer.read_text())
        folder = Path(spec["report"])
        if sha(folder / "manifest.json") != spec["manifest_sha256"]:
            raise DataGateError("News pointer integrity mismatch")
        meta = verify(folder)
        capture_time = timestamp(meta["captured_at_utc"])
        if capture_time > clock:
            raise DataGateError("News capture is in the future")
        due = clock - capture_time >= pd.Timedelta(hours=REFRESH_HOURS)
        rows = json.loads((folder / "items.json").read_text())
        health = json.loads((folder / "sources.json").read_text())
        attempt_sha, attempt_time = spec["manifest_sha256"], meta["captured_at_utc"]
        fallback = False
        usable = root / "data/news/latest-usable.json"
        if not rows and usable.is_file():
            old = json.loads(usable.read_text())
            previous = Path(old["report"])
            if sha(previous / "manifest.json") != old["manifest_sha256"]:
                raise DataGateError("Last usable news pointer integrity mismatch")
            old_meta = verify(previous)
            if timestamp(old_meta["captured_at_utc"]) > clock:
                raise DataGateError("Last usable news capture is in the future")
            rows = [row for row in json.loads((previous / "items.json").read_text())
                    if timestamp(row["published_at_utc"]) >= clock - pd.Timedelta(hours=72)]
            if rows:
                folder, meta, spec, fallback = previous, old_meta, old, True
        availability = "partial" if rows and any(s["status"] == "unavailable" for s in health) else "available" if rows else "unavailable"
        for row in rows:
            row.setdefault("content_kind", content_kind(row))
        rows.sort(key=lambda r: (r["content_kind"] != "legal_solicitation_or_announcement", bool(r["topics"]), r["published_at_utc"]), reverse=True)
        result |= {"status": "stale" if rows and (due or fallback) else availability, "refresh_due": due,
                   "captured_at_utc": meta["captured_at_utc"], "manifest_sha256": spec["manifest_sha256"],
                   "latest_attempt_manifest_sha256": attempt_sha, "latest_attempt_at_utc": attempt_time,
                   "archive_report": str(folder.resolve()), "using_last_usable_capture": fallback,
                   "coverage_groups": meta["coverage_groups"], "sources": health,
                   "item_count": len(rows), "article_bodies_read": sum(row["coverage"] == "article_read" for row in rows),
                   "items": rows[:80]}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result |= {"status": "unavailable", "error": str(exc)[:180]}
    return result


def refresh_if_due(root: Path):
    folder = root / "data/news"
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / ".refresh.lock").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        try:
            if status(root)["refresh_due"]:
                stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
                refresh(root, folder / "captures" / stamp)
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
