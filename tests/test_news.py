import json
import sqlite3

import pandas as pd
import pytest

from fundamental_event_trader.news import (
    article_text,
    canonical,
    content_kind,
    group_items,
    observe,
    parse_feed,
    refresh,
    status,
    verify,
)
from fundamental_event_trader.news_io import NoAccountAuth, Reader, public_url
from fundamental_event_trader.news_sources import Source
from fundamental_event_trader.sec import DataGateError

CLOCK = "2026-11-25T22:00:00Z"
SOURCE = Source("test", "Synthetic Test Publisher", "financial_press", "https://news.example.com/feed.xml", ("news.example.com",))


def feed(*, date="Wed, 25 Nov 2026 21:00:00 GMT", link="https://news.example.com/story?utm_source=reader", title="NVIDIA changes investment guidance"):
    return f"""<?xml version="1.0"?><rss version="2.0"><channel><title>Fixture</title>
    <item><title>{title}</title><link>{link}</link><pubDate>{date}</pubDate>
    <description>Company released revised quarterly outlook after new orders.</description></item>
    </channel></rss>""".encode()


class FixtureReader:
    requests = []

    def __init__(self, *, fail=False):
        self.fail = fail

    def get(self, url, hosts):
        if self.fail:
            raise DataGateError("fixture source unavailable")
        return (feed() if url.endswith("feed.xml") else b"<html><body>Fixture source</body></html>"), url


def test_real_feed_parsing_keeps_publication_separate_from_observation():
    rows, rejected = parse_feed(feed(), SOURCE, CLOCK)
    assert not rejected
    assert rows[0]["url"] == "https://news.example.com/story"
    assert rows[0]["published_at_utc"] == "2026-11-25T21:00:00+00:00"
    assert "available_at_utc" not in rows[0]


@pytest.mark.parametrize("date", ["", "2026-11-25T21:00:00", "Thu, 26 Nov 2026 21:00:00 GMT", "Mon, 16 Nov 2026 21:00:00 GMT"])
def test_unknown_naive_future_and_old_times_are_not_current_news(date):
    rows, excluded = parse_feed(feed(date=date), SOURCE, CLOCK)
    assert not rows and excluded


@pytest.mark.parametrize("link", ["http://news.example.com/story", "https://127.0.0.1/", "https://evil.example.com/story", "https://user:pass@news.example.com/story", "https://news.example.com:444/story"])
def test_feed_links_cannot_escape_the_source_allowlist(link):
    assert not parse_feed(feed(link=link), SOURCE, CLOCK)[0]


def test_source_url_controls_and_local_addresses_rejected():
    for link, hosts in (("https://127.0.0.1", ("127.0.0.1",)), ("https://news.example.com/a\nb", SOURCE.hosts)):
        with pytest.raises(DataGateError):
            public_url(link, hosts)


def test_tracking_is_removed_without_dropping_document_identity_query():
    assert canonical("https://NEWS.example.com/read?id=42&utm_medium=rss&fbclid=1#section") == "https://news.example.com/read?id=42"


def test_xml_entities_are_not_processed():
    with pytest.raises(DataGateError, match="Entity"):
        parse_feed(b'<!DOCTYPE rss [<!ENTITY x SYSTEM "file:///etc/passwd">]><rss/>', SOURCE, CLOCK)


def test_feed_parser_cannot_treat_response_body_as_another_network_url(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Non-XML data must not reach feedparser")

    monkeypatch.setattr("fundamental_event_trader.news.feedparser.parse", forbidden)
    with pytest.raises(DataGateError, match="XML bytes"):
        parse_feed(b"http://127.0.0.1/private", SOURCE, CLOCK)


def test_subscription_marker_prevents_article_extraction(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("A restricted article must not reach extraction")

    monkeypatch.setattr("fundamental_event_trader.news.trafilatura.extract", forbidden)
    raw = b'<html><script type="application/ld+json">{"@graph":[{"isAccessibleForFree":false}]}</script></html>'
    with pytest.raises(DataGateError, match="restricted"):
        article_text(raw)


def test_article_read_requires_body_not_just_headline(monkeypatch):
    monkeypatch.setattr("fundamental_event_trader.news.trafilatura.extract", lambda *a, **k: "Short heading")
    with pytest.raises(DataGateError, match="Insufficient"):
        article_text(b"<html><body>Heading</body></html>")


def test_first_seen_and_revisions_are_never_backdated_to_publication():
    conn = sqlite3.connect(":memory:")
    conn.executescript("CREATE TABLE articles(id TEXT PRIMARY KEY, first_seen TEXT); CREATE TABLE versions(id TEXT, content TEXT, first_seen TEXT, PRIMARY KEY(id,content));")
    first = {"source_id": "test", "url": "https://news.example.com/story", "content_sha256": "a" * 64, "published_at_utc": "2026-11-24T20:00:00Z"}
    observe(conn, first, pd.Timestamp(CLOCK))
    revised = first | {"content_sha256": "b" * 64}
    observe(conn, revised, pd.Timestamp("2026-11-26T22:00:00Z"))
    assert revised["first_seen_at_utc"] == first["first_seen_at_utc"]
    assert revised["available_at_utc"] == "2026-11-26T22:00:00+00:00"
    assert revised["available_at_utc"] != first["published_at_utc"]


def test_news_capture_is_source_bound_and_never_strategy_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr("fundamental_event_trader.news.article_text", lambda _: "Synthetic test article about NVIDIA guidance and revenue. " * 20)
    output = refresh(tmp_path, tmp_path / "capture", sources=(SOURCE,), max_articles=1, now=CLOCK, reader=FixtureReader())
    verify(output)
    current = status(tmp_path, now=CLOCK)
    assert current["item_count"] == current["article_bodies_read"] == 1
    assert current["historical_strategy_evidence"] is current["action_authorized"] is False
    row = current["items"][0]
    assert row["available_at_utc"] == "2026-11-25T22:00:00+00:00"
    assert "Earnings and guidance" in row["topics"]
    assert len(row["display_title"].split()) + len(row["display_excerpt"].split()) <= 24
    assert status(tmp_path, now="2026-11-25T23:00:00Z")["refresh_due"] is True
    body = output / row["body_path"]
    body.write_text("Changed source bytes")
    assert status(tmp_path, now=CLOCK)["status"] == "unavailable"
    with pytest.raises(DataGateError, match="integrity"):
        verify(output)


def test_failed_refresh_retains_but_labels_prior_news_stale(tmp_path):
    refresh(tmp_path, tmp_path / "good", sources=(SOURCE,), max_articles=0, now=CLOCK, reader=FixtureReader())
    refresh(tmp_path, tmp_path / "bad", sources=(SOURCE,), max_articles=0, now="2026-11-25T22:10Z", reader=FixtureReader(fail=True))
    current = status(tmp_path, now="2026-11-25T22:11Z")
    assert current["status"] == "stale" and current["using_last_usable_capture"]
    assert current["item_count"] == 1 and current["sources"][0]["status"] == "unavailable"
    assert current["refresh_due"] is False


def test_syndicated_duplicates_are_coverage_groups_not_independent_votes():
    rows = [{"id": name, "title": "Company publishes quarterly revenue and earnings guidance", "published_at_utc": "2026-11-25T20:00Z"} for name in ("one", "two")]
    assert group_items(rows) == 1
    assert rows[0]["coverage_group"] == rows[1]["coverage_group"]


def test_similar_boilerplate_about_different_companies_is_not_one_event():
    rows = [{"id": str(i), "title": f"{name} announces quarterly dividend and operating results for shareholders",
             "published_at_utc": "2026-11-25T20:00Z"} for i, name in enumerate(("Alpha", "Bravo"))]
    assert group_items(rows) == 2


def test_headline_revision_with_unchanged_body_has_its_own_availability(tmp_path, monkeypatch):
    monkeypatch.setattr("fundamental_event_trader.news.article_text", lambda _: "Synthetic unchanged body. " * 40)
    refresh(tmp_path, tmp_path / "first", sources=(SOURCE,), max_articles=1, now=CLOCK, reader=FixtureReader())
    first = status(tmp_path, now=CLOCK)["items"][0]

    class RevisionReader(FixtureReader):
        def get(self, url, hosts):
            if url.endswith("feed.xml"):
                return feed(title="NVIDIA cuts investment guidance"), url
            return super().get(url, hosts)

    refresh(tmp_path, tmp_path / "second", sources=(SOURCE,), max_articles=1, now="2026-11-25T22:10Z", reader=RevisionReader())
    revised = status(tmp_path, now="2026-11-25T22:10Z")["items"][0]
    assert first["body_sha256"] == revised["body_sha256"]
    assert first["content_sha256"] != revised["content_sha256"]
    assert first["first_seen_at_utc"] == revised["first_seen_at_utc"]
    assert revised["available_at_utc"] == "2026-11-25T22:10:00+00:00"


def test_law_firm_publicity_is_not_confirmed_independent_regulatory_evidence():
    assert content_kind({"source_kind": "issuer_release_wire", "title": "INVESTOR ALERT: Law firm reminds investors of deadline"}) == "legal_solicitation_or_announcement"


@pytest.mark.parametrize("budget", [0, -1, float("inf"), float("nan"), 181])
def test_news_fetches_are_time_bounded(tmp_path, budget):
    with pytest.raises(DataGateError, match="budget"):
        refresh(tmp_path, tmp_path / "capture", budget=budget)
    assert not (tmp_path / "capture").exists()


class Response:
    def __init__(self, status, body=b"", headers=None):
        self.status_code, self.body, self.headers = status, body, headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def iter_content(self, size):
        yield self.body


class Session:
    def __init__(self, responses):
        self.responses, self.calls = iter(responses), []

    def get(self, url, **kwargs):
        self.calls.append(url)
        assert kwargs["allow_redirects"] is False
        return next(self.responses)


def test_robots_and_denied_access_are_not_retried_or_evaded(tmp_path, monkeypatch):
    monkeypatch.setattr("fundamental_event_trader.news_io.time.sleep", lambda _: None)
    session = Session([Response(403, b"Denied")])
    with pytest.raises(DataGateError, match="Robots"):
        Reader(tmp_path, session=session).get(SOURCE.feed, SOURCE.hosts)
    assert len(session.calls) == 1
    session = Session([Response(200, b"User-agent: *\nAllow: /"), Response(403, b"Denied")])
    with pytest.raises(DataGateError, match="403"):
        Reader(tmp_path, session=session).get(SOURCE.feed, SOURCE.hosts)
    assert len(session.calls) == 2


def test_robots_exclusion_and_cross_host_redirect_cannot_be_bypassed(tmp_path, monkeypatch):
    monkeypatch.setattr("fundamental_event_trader.news_io.time.sleep", lambda _: None)
    session = Session([Response(200, b"User-agent: *\nDisallow: /")])
    with pytest.raises(DataGateError, match="robots"):
        Reader(tmp_path, session=session).get(SOURCE.feed, SOURCE.hosts)
    assert len(session.calls) == 1
    session = Session([Response(200, b"User-agent: *\nAllow: /"), Response(302, headers={"Location": "https://other.example.com/"})])
    with pytest.raises(DataGateError, match="Cross-host"):
        Reader(tmp_path, session=session).get(SOURCE.feed, (*SOURCE.hosts, "other.example.com"))
    assert len(session.calls) == 2


def test_news_session_does_not_implicitly_use_account_netrc(tmp_path):
    assert isinstance(Reader(tmp_path).session.auth, NoAccountAuth)


def test_whole_news_manifest_rejects_future_version(tmp_path):
    output = refresh(tmp_path, tmp_path / "capture", sources=(SOURCE,), max_articles=0, now=CLOCK, reader=FixtureReader())
    rows = json.loads((output / "items.json").read_text())
    rows[0]["available_at_utc"] = "2026-11-26T22:00Z"
    (output / "items.json").write_text(json.dumps(rows))
    meta = json.loads((output / "manifest.json").read_text())
    from fundamental_event_trader.sec import sha

    meta["artifacts"]["items.json"] = sha(output / "items.json")
    (output / "manifest.json").write_text(json.dumps(meta))
    with pytest.raises(DataGateError, match="causal"):
        verify(output)
