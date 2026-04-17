from __future__ import annotations

import json
import re
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .common import (
    collapse_whitespace,
    is_blocked_domain,
    normalize_domain,
    normalize_homepage,
    normalize_text,
    read_json,
    write_json,
)
from .config import (
    DEFAULT_INSPECT_INPUT_PATH,
    DEFAULT_INSPECTION_DELAY_SECONDS,
    DEFAULT_INSPECT_OUTPUT_PATH,
    DEFAULT_MAX_PAGES_PER_COMPANY,
    DEFAULT_PAGE_PATHS,
    DEFAULT_TIMEOUT_SECONDS,
    EMAIL_PAGE_HINTS,
    LEADERSHIP_TITLE_ALIASES,
    NON_COMPANY_DOMAINS,
    PUBLIC_EMAIL_PREFIXES,
)
from .models import DecisionMakerHit, EmailHit

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/135.0.0.0 Safari/537.36"
)

EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
NAME_PATTERN = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}\b")
TITLE_PATTERN = re.compile(
    "|".join(re.escape(title) for title, _ in sorted(LEADERSHIP_TITLE_ALIASES, key=lambda item: -len(item[0]))),
    re.IGNORECASE,
)
NAME_THEN_TITLE_PATTERN = re.compile(
    rf"(?P<name>{NAME_PATTERN.pattern})\s*(?:,|\||:|-|–|—)?\s*(?P<title>{TITLE_PATTERN.pattern})",
    re.IGNORECASE,
)
TITLE_THEN_NAME_PATTERN = re.compile(
    rf"(?P<title>{TITLE_PATTERN.pattern})\s*(?:,|\||:|-|–|—)?\s*(?P<name>{NAME_PATTERN.pattern})",
    re.IGNORECASE,
)
GENERIC_NAME_WORDS = {
    "about",
    "careers",
    "chief",
    "co",
    "company",
    "conference",
    "contact",
    "director",
    "founder",
    "growth",
    "head",
    "kingdom",
    "managing",
    "officer",
    "operations",
    "podcast",
    "remote",
    "revenue",
    "sales",
    "speaker",
    "states",
    "team",
    "united",
    "vice",
}


def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    return session


def load_candidates(input_path: Path) -> list[dict]:
    payload = read_json(input_path)
    return payload.get("candidates", [])


def fetch_page(session: requests.Session, url: str, timeout_seconds: float) -> tuple[str | None, str, str | None]:
    try:
        response = session.get(url, timeout=timeout_seconds)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type.lower():
            return None, response.url, f"unsupported content type: {content_type}"
        return response.text, response.url, None
    except requests.RequestException as exc:
        return None, url, str(exc)


def decode_cfemail(encoded: str) -> str | None:
    if len(encoded) < 4 or len(encoded) % 2 != 0:
        return None
    try:
        key = int(encoded[:2], 16)
        chars = [
            chr(int(encoded[index : index + 2], 16) ^ key)
            for index in range(2, len(encoded), 2)
        ]
    except ValueError:
        return None
    return "".join(chars)


def deobfuscate_text(text: str) -> str:
    replacements = (
        (" [at] ", "@"),
        (" (at) ", "@"),
        (" at ", "@"),
        (" [dot] ", "."),
        (" (dot) ", "."),
        (" dot ", "."),
    )
    clean = f" {normalize_text(text)} "
    for before, after in replacements:
        clean = clean.replace(before, after)
    return clean.strip()


def clean_email(email: str) -> str | None:
    normalized = email.strip().strip(".,;:()[]{}<>").lower()
    if "mailto:" in normalized:
        normalized = normalized.split("mailto:", 1)[1]
    if "?" in normalized:
        normalized = normalized.split("?", 1)[0]
    if not EMAIL_PATTERN.fullmatch(normalized):
        return None
    return normalized


def is_same_company_email(email: str, company_domain: str) -> bool:
    email_domain = email.split("@", 1)[1]
    return email_domain == company_domain or email_domain.endswith(f".{company_domain}")


def is_public_company_email(email: str) -> bool:
    local_part = email.split("@", 1)[0]
    local_part = local_part.split("+", 1)[0]
    local_part = local_part.replace(".", "").replace("-", "").replace("_", "")
    return any(local_part == prefix or local_part.startswith(prefix) for prefix in PUBLIC_EMAIL_PREFIXES)


def extract_emails_from_soup(html: str, soup: BeautifulSoup, page_url: str, company_domain: str) -> list[EmailHit]:
    found: dict[str, EmailHit] = {}

    for anchor in soup.select("a[href^='mailto:']"):
        href = anchor.get("href", "")
        cleaned = clean_email(href)
        if cleaned and is_same_company_email(cleaned, company_domain) and is_public_company_email(cleaned):
            found[cleaned] = EmailHit(cleaned, page_url, "mailto")

    for node in soup.select("[data-cfemail]"):
        decoded = decode_cfemail(node.get("data-cfemail", ""))
        cleaned = clean_email(decoded or "")
        if cleaned and is_same_company_email(cleaned, company_domain) and is_public_company_email(cleaned):
            found[cleaned] = EmailHit(cleaned, page_url, "cfemail")

    for source_text, source_type in (
        (html, "html"),
        (soup.get_text(" ", strip=True), "text"),
        (deobfuscate_text(soup.get_text(" ", strip=True)), "deobfuscated_text"),
    ):
        for raw_email in EMAIL_PATTERN.findall(source_text):
            cleaned = clean_email(raw_email)
            if cleaned and is_same_company_email(cleaned, company_domain) and is_public_company_email(cleaned):
                found[cleaned] = EmailHit(cleaned, page_url, source_type)

    return sorted(found.values(), key=lambda hit: hit.email)


def canonical_title(text: str) -> str | None:
    normalized = normalize_text(text)
    for candidate, label in LEADERSHIP_TITLE_ALIASES:
        if candidate in normalized:
            return label
    return None


def clean_person_name(value: str) -> str | None:
    candidate = collapse_whitespace(value.strip(" ,|:-–—"))
    if not candidate or any(char.isdigit() for char in candidate):
        return None
    words = candidate.split()
    if not 2 <= len(words) <= 4:
        return None
    if any(word.lower() in GENERIC_NAME_WORDS for word in words):
        return None
    return candidate


def add_decision_maker(
    found: dict[tuple[str, str], DecisionMakerHit],
    name: str | None,
    title: str | None,
    page_url: str,
    source_type: str,
    confidence: int,
) -> None:
    if not name or not title:
        return

    cleaned_name = clean_person_name(name)
    if not cleaned_name:
        return

    key = (cleaned_name.lower(), title)
    existing = found.get(key)
    if existing is None or confidence > existing.confidence:
        found[key] = DecisionMakerHit(
            name=cleaned_name,
            title=title,
            source_url=page_url,
            source_type=source_type,
            confidence=confidence,
        )


def iter_json_nodes(value: object):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from iter_json_nodes(child)
    elif isinstance(value, list):
        for item in value:
            yield from iter_json_nodes(item)


def extract_decision_makers_from_json_ld(soup: BeautifulSoup, page_url: str) -> list[DecisionMakerHit]:
    found: dict[tuple[str, str], DecisionMakerHit] = {}

    for script in soup.select("script[type='application/ld+json']"):
        raw = script.string or script.get_text(strip=True)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue

        for node in iter_json_nodes(payload):
            node_type = node.get("@type")
            if isinstance(node_type, list):
                is_person = any(str(value).lower() == "person" for value in node_type)
            else:
                is_person = str(node_type).lower() == "person"
            if not is_person:
                continue

            title = canonical_title(str(node.get("jobTitle") or node.get("title") or node.get("roleName") or ""))
            name = node.get("name")
            add_decision_maker(found, str(name or ""), title, page_url, "json_ld", 95)

    return sorted(found.values(), key=lambda hit: (-hit.confidence, hit.name, hit.title))


def extract_decision_makers_from_blocks(soup: BeautifulSoup, page_url: str) -> list[DecisionMakerHit]:
    found: dict[tuple[str, str], DecisionMakerHit] = {}

    for element in soup.select("article, section, li, div, p, h1, h2, h3, h4"):
        text = collapse_whitespace(element.get_text(" ", strip=True))
        if len(text) < 8 or len(text) > 260:
            continue
        if not canonical_title(text):
            continue

        for match in NAME_THEN_TITLE_PATTERN.finditer(text):
            add_decision_maker(
                found,
                match.group("name"),
                canonical_title(match.group("title")),
                page_url,
                "dom_block",
                75,
            )
        for match in TITLE_THEN_NAME_PATTERN.finditer(text):
            add_decision_maker(
                found,
                match.group("name"),
                canonical_title(match.group("title")),
                page_url,
                "dom_block",
                70,
            )

        parent = element.parent
        if parent is not None:
            parent_text = collapse_whitespace(parent.get_text(" ", strip=True))
            if parent_text != text and len(parent_text) <= 260:
                for match in NAME_THEN_TITLE_PATTERN.finditer(parent_text):
                    add_decision_maker(
                        found,
                        match.group("name"),
                        canonical_title(match.group("title")),
                        page_url,
                        "dom_parent",
                        72,
                    )

    return sorted(found.values(), key=lambda hit: (-hit.confidence, hit.name, hit.title))


def extract_decision_makers(soup: BeautifulSoup, page_url: str) -> list[DecisionMakerHit]:
    found: dict[tuple[str, str], DecisionMakerHit] = {}

    for hit in extract_decision_makers_from_json_ld(soup, page_url):
        found[(hit.name.lower(), hit.title)] = hit
    for hit in extract_decision_makers_from_blocks(soup, page_url):
        found.setdefault((hit.name.lower(), hit.title), hit)

    return sorted(found.values(), key=lambda hit: (-hit.confidence, hit.name, hit.title))


def is_same_site(url: str, company_domain: str) -> bool:
    domain = normalize_domain(url)
    return domain == company_domain or domain.endswith(f".{company_domain}")


def build_candidate_pages(homepage_url: str, soup: BeautifulSoup, company_domain: str, max_pages: int) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()

    for path in DEFAULT_PAGE_PATHS:
        candidate = normalize_homepage(urljoin(homepage_url, path)) if not path else urljoin(homepage_url, path)
        if candidate not in seen and is_same_site(candidate, company_domain):
            urls.append(candidate)
            seen.add(candidate)

    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "")
        text = normalize_text(anchor.get_text(" ", strip=True))
        absolute = urljoin(homepage_url, href)
        if absolute in seen:
            continue
        if not is_same_site(absolute, company_domain):
            continue
        if any(hint in href.lower() or hint in text for hint in EMAIL_PAGE_HINTS):
            urls.append(absolute)
            seen.add(absolute)
        if len(urls) >= max_pages:
            break

    return urls[:max_pages]


def inspect_company(
    session: requests.Session,
    candidate: dict,
    timeout_seconds: float,
    max_pages_per_company: int,
    delay_seconds: float,
) -> dict:
    homepage_url = candidate.get("company_url", "")
    company_domain = normalize_domain(homepage_url)

    result = {
        "company_url": homepage_url,
        "domain": company_domain,
        "title": candidate.get("title", ""),
        "market": candidate.get("market", ""),
        "industry": candidate.get("industry", ""),
        "signal": candidate.get("signal", ""),
        "query": candidate.get("query", ""),
        "score": candidate.get("score", 0),
        "status": "ok",
        "reason": None,
        "pages_scanned": [],
        "public_emails": [],
        "decision_makers": [],
    }

    if not homepage_url or not company_domain:
        result["status"] = "skipped"
        result["reason"] = "missing company url"
        return result

    if is_blocked_domain(company_domain, NON_COMPANY_DOMAINS):
        result["status"] = "skipped"
        result["reason"] = "excluded non-company domain"
        return result

    homepage_html, final_homepage_url, error = fetch_page(session, homepage_url, timeout_seconds)
    if error or not homepage_html:
        result["status"] = "error"
        result["reason"] = error or "empty homepage response"
        return result

    result["company_url"] = normalize_homepage(final_homepage_url)
    company_domain = normalize_domain(result["company_url"])
    if is_blocked_domain(company_domain, NON_COMPANY_DOMAINS):
        result["status"] = "skipped"
        result["reason"] = "redirected to excluded non-company domain"
        return result

    homepage_soup = BeautifulSoup(homepage_html, "html.parser")
    candidate_pages = build_candidate_pages(result["company_url"], homepage_soup, company_domain, max_pages_per_company)

    email_hits: dict[str, EmailHit] = {}
    decision_makers: dict[tuple[str, str], DecisionMakerHit] = {}

    for page_url in candidate_pages:
        html, final_url, page_error = fetch_page(session, page_url, timeout_seconds)
        result["pages_scanned"].append({"requested_url": page_url, "final_url": final_url, "error": page_error})
        if html:
            soup = BeautifulSoup(html, "html.parser")
            for hit in extract_emails_from_soup(html, soup, final_url, company_domain):
                email_hits.setdefault(hit.email, hit)
            for hit in extract_decision_makers(soup, final_url):
                decision_makers.setdefault((hit.name.lower(), hit.title), hit)
        if delay_seconds:
            time.sleep(delay_seconds)

    result["public_emails"] = [asdict(hit) for hit in sorted(email_hits.values(), key=lambda hit: hit.email)]
    result["decision_makers"] = [
        asdict(hit)
        for hit in sorted(decision_makers.values(), key=lambda hit: (-hit.confidence, hit.name, hit.title))
    ]
    if not result["public_emails"]:
        result["reason"] = "no public company contact emails found"
    return result


def write_output(results: list[dict], output_path: Path, input_path: Path) -> None:
    saved_results = [item for item in results if item.get("public_emails")]
    payload = {
        "metadata": {
            "generated_at": datetime.now(UTC).isoformat(),
            "input_path": str(input_path),
            "inspected_company_count": len(results),
            "saved_company_count": len(saved_results),
            "notes": [
                "This stage only extracts publicly listed company contact emails from company-controlled pages.",
                "Decision-maker names and titles are heuristic and should be reviewed before use.",
                "Only companies with at least one extracted email are saved in the output file.",
            ],
        },
        "companies": saved_results,
    }
    write_json(output_path, payload)


def run_inspection(
    input_path: str = DEFAULT_INSPECT_INPUT_PATH,
    output_path: str = DEFAULT_INSPECT_OUTPUT_PATH,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    delay_seconds: float = DEFAULT_INSPECTION_DELAY_SECONDS,
    max_pages_per_company: int = DEFAULT_MAX_PAGES_PER_COMPANY,
) -> list[dict]:
    input_file = Path(input_path)
    candidates = load_candidates(input_file)
    session = build_session()
    results: list[dict] = []

    for index, candidate in enumerate(candidates, start=1):
        print(f"Inspecting {index}/{len(candidates)}: {candidate.get('company_url', '')}")
        results.append(
            inspect_company(
                session=session,
                candidate=candidate,
                timeout_seconds=timeout_seconds,
                max_pages_per_company=max_pages_per_company,
                delay_seconds=delay_seconds,
            )
        )

    write_output(results, Path(output_path), input_file)
    return [item for item in results if item.get("public_emails")]
