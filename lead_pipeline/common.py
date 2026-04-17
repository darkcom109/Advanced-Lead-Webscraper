from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

MULTISPACE_PATTERN = re.compile(r"\s+")


def normalize_domain(url: str) -> str:
    parsed = urlparse(url)
    domain = parsed.netloc.lower().strip()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def normalize_homepage(url: str) -> str:
    parsed = urlparse(url)
    scheme = parsed.scheme or "https"
    domain = parsed.netloc.lower().strip()
    if domain.startswith("www."):
        domain = domain[4:]
    return f"{scheme}://{domain}"


def collapse_whitespace(value: str) -> str:
    return MULTISPACE_PATTERN.sub(" ", value).strip()


def normalize_text(*values: str, lowercase: bool = True) -> str:
    text = collapse_whitespace(" ".join(value for value in values if value))
    return text.lower() if lowercase else text


def is_blocked_domain(domain: str, blocked_domains: set[str]) -> bool:
    return any(domain == blocked or domain.endswith(f".{blocked}") for blocked in blocked_domains)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
