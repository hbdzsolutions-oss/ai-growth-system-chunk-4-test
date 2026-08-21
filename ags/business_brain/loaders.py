from __future__ import annotations

import ipaddress
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

from .models import LoadedDocument
from .ports import KnowledgeLoader


class ManualTextLoader(KnowledgeLoader):
    source_type = "manual"

    def load(self, value: str, title: str | None = None) -> LoadedDocument:
        text = value.strip()
        if not text:
            raise ValueError("Manual knowledge cannot be empty.")
        return LoadedDocument(title=(title or "Manual knowledge").strip(), text=text)


class _VisibleTextParser(HTMLParser):
    _ignored = {"script", "style", "noscript", "svg", "canvas"}

    def __init__(self) -> None:
        super().__init__()
        self.depth = 0
        self.parts: list[str] = []
        self.page_title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs) -> None:
        lower = tag.lower()
        if lower in self._ignored:
            self.depth += 1
        if lower == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        lower = tag.lower()
        if lower in self._ignored and self.depth:
            self.depth -= 1
        if lower == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if not text:
            return
        if self._in_title and not self.page_title:
            self.page_title = text
        if not self.depth:
            self.parts.append(text)


class WebsiteLoader(KnowledgeLoader):
    source_type = "website"
    max_bytes = 2_000_000

    def __init__(self, client_factory=None) -> None:
        self.client_factory = client_factory or (lambda: httpx.Client(timeout=12.0, follow_redirects=False))

    @staticmethod
    def _validate_url(url: str) -> str:
        parsed = urlparse(url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Website URL must use http:// or https:// and include a hostname.")
        host = parsed.hostname.lower()
        if host == "localhost" or host.endswith(".local"):
            raise ValueError("Local/private website addresses are not allowed.")
        try:
            addresses = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
        except socket.gaierror as exc:
            raise ValueError("Website hostname could not be resolved.") from exc
        for address in addresses:
            ip = ipaddress.ip_address(address[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                raise ValueError("Local/private website addresses are not allowed.")
        return parsed.geturl()

    def load(self, value: str, title: str | None = None) -> LoadedDocument:
        url = self._validate_url(value)
        with self.client_factory() as client:
            current_url = url
            for _ in range(6):
                response = client.get(
                    current_url,
                    headers={"User-Agent": "AI-Growth-System-Knowledge-Ingest/1.0"},
                )
                if response.status_code not in {301, 302, 303, 307, 308}:
                    break
                location = response.headers.get("location")
                if not location:
                    break
                current_url = self._validate_url(urljoin(current_url, location))
            else:
                raise ValueError("Website redirected too many times.")
        response.raise_for_status()
        url = str(response.url) if getattr(response, "url", None) else current_url
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type and "text/plain" not in content_type:
            raise ValueError("Website source must return HTML or plain text.")
        raw = response.content
        if len(raw) > self.max_bytes:
            raise ValueError("Website response is too large for this MVP ingestion path.")
        text = response.text
        if "text/html" in content_type:
            parser = _VisibleTextParser()
            parser.feed(text)
            normalized = "\n".join(parser.parts)
            source_title = (title or parser.page_title or url).strip()
        else:
            normalized = text.strip()
            source_title = (title or url).strip()
        if not normalized.strip():
            raise ValueError("Website did not contain readable text.")
        return LoadedDocument(
            title=source_title,
            text=normalized.strip(),
            source_uri=url,
            metadata={"content_type": content_type.split(";")[0]},
        )
