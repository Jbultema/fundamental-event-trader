"""Bounded, identified public-web reads; no authentication or access-control workarounds."""

from __future__ import annotations

import hashlib
import ipaddress
import time
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import requests
from requests.auth import AuthBase

from fundamental_event_trader.sec import DataGateError

USER_AGENT = "fundamental-event-trader/0.1 (+https://github.com/Jbultema/fundamental-event-trader)"


def public_url(url, hosts):
    if not isinstance(url, str) or any(c.isspace() or ord(c) < 32 for c in url):
        raise DataGateError("Whitespace and control characters prohibited in news URLs")
    part = urlsplit(url)
    if (part.scheme != "https" or part.username or part.password or part.port not in (None, 443)
            or not part.hostname or part.hostname.lower() not in hosts):
        raise DataGateError("News URL outside the approved public HTTPS sources")
    try:
        ipaddress.ip_address(part.hostname)
    except ValueError:
        return urlunsplit(("https", part.hostname.lower(), part.path or "/", part.query, ""))
    raise DataGateError("Literal network addresses prohibited in news sources")


class NoAccountAuth(AuthBase):
    def __call__(self, request):
        return request


class Reader:
    def __init__(self, output: Path, *, budget=75., session=None, request_timeout=5.):
        if isinstance(request_timeout, bool) or not isinstance(request_timeout, (int, float)) or not 0 < request_timeout <= 60:
            raise DataGateError("Public-source request timeout must be in (0, 60] seconds")
        self.output = output
        self.request_timeout = request_timeout
        self.session = session or requests.Session()
        if session is None:
            self.session.auth = NoAccountAuth()  # Do not load account credentials from netrc.
        self.deadline = time.monotonic() + budget
        self.requests = []
        self.robots = {}
        self.last_request = {}

    def remaining(self):
        return max(0., self.deadline - time.monotonic())

    def _download(self, url, hosts):
        url = public_url(url, hosts)
        for _ in range(4):
            if self.remaining() < .25:
                raise DataGateError("News acquisition time budget exhausted")
            host = urlsplit(url).hostname
            parser = self.robots.get(host)
            delay = max(.25, parser.crawl_delay(USER_AGENT) or 0.) if parser else .25
            pause = max(0., self.last_request.get(host, 0) + delay - time.monotonic())
            if pause > self.remaining():
                raise DataGateError("Robots crawl delay exceeds remaining acquisition budget")
            time.sleep(pause)
            item = {"url": url, "http_status": None, "path": None, "sha256": None}
            self.requests.append(item)
            try:
                self.last_request[host] = time.monotonic()
                with self.session.get(url, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, text/html, application/xml, text/plain"},
                                      stream=True, allow_redirects=False, timeout=max(.1, min(self.request_timeout, self.remaining()))) as response:
                    item["http_status"] = response.status_code
                    if response.status_code in (301, 302, 303, 307, 308):
                        next_url = public_url(urljoin(url, response.headers.get("Location", "")), hosts)
                        if urlsplit(next_url).hostname != host:
                            raise DataGateError("Cross-host redirect withheld pending the destination's robots permission")
                        url = next_url
                        item["redirect_to"] = url
                        continue
                    chunks, size = [], 0
                    for chunk in response.iter_content(65536):
                        size += len(chunk)
                        if size > 2_000_000 or self.remaining() <= 0:
                            raise DataGateError("News response exceeds size or time limit")
                        chunks.append(chunk)
                    body = b"".join(chunks)
                    identity = hashlib.sha256(url.encode() + b"\0" + body).hexdigest()
                    file = self.output / "raw" / f"{identity}.bin"
                    file.parent.mkdir(parents=True, exist_ok=True)
                    file.write_bytes(body)
                    item |= {"path": str(file.relative_to(self.output)), "sha256": hashlib.sha256(body).hexdigest(),
                             "content_type": response.headers.get("Content-Type", "")}
                    return response.status_code, body, url
            except (requests.RequestException, ValueError) as exc:
                item["error"] = f"{type(exc).__name__}:{str(exc)[:180]}"
                raise DataGateError(f"Public news request failed: {str(exc)[:160]}") from exc
        raise DataGateError("Excessive public-news redirects")

    def get(self, url, hosts):
        url = public_url(url, hosts)
        host = urlsplit(url).hostname
        if host not in self.robots:
            status, body, _ = self._download(f"https://{host}/robots.txt", hosts)
            parser = RobotFileParser()
            if status == 404:
                parser.parse(["User-agent: *", "Allow: /"])
            elif status == 200:
                parser.parse(body.decode("utf-8", errors="replace").splitlines())
            else:
                raise DataGateError(f"Robots permission unavailable: HTTP {status}")
            self.robots[host] = parser
        if not self.robots[host].can_fetch(USER_AGENT, url):
            raise DataGateError("Publisher robots policy excludes this request")
        status, body, final = self._download(url, hosts)
        if status != 200:
            raise DataGateError(f"Public source returned HTTP {status}; no retry or alternate identity")
        return body, final
