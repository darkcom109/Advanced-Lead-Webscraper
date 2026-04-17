from __future__ import annotations

import os
import re
import time
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

import serpapi

from .common import is_blocked_domain, normalize_domain, normalize_homepage, normalize_text, write_json
from .config import (
    DEFAULT_MAX_QUERIES,
    DEFAULT_PAGES_PER_QUERY,
    DEFAULT_SEARCH_DELAY_SECONDS,
    DEFAULT_SEARCH_OUTPUT_PATH,
    EXISTING_REVOPS_TERMS,
    EXCLUDED_VERTICAL_TERMS,
    GOOGLE_DOMAIN,
    INDUSTRY_PRIORITY,
    NON_COMPANY_DOMAINS,
    PRIMARY_MARKETS,
    SEARCH_RESULT_TEXT_EXCLUSIONS,
    SEARCH_SIGNAL_TEMPLATES,
    SECONDARY_MARKETS,
    SERPAPI_ENGINE,
    TARGET_DECISION_MAKER_TITLES,
)
from .models import SearchCandidate, SearchJob

FILE_EXTENSION_PATTERN = re.compile(r"\.(pdf|docx?|xlsx?|pptx?)$", re.IGNORECASE)
MATURE_FUNDING_PATTERN = re.compile(
    r"(series\s+d|series\s+e|series\s+f|private\s+equity|ipo|"
    r"raised\s+(?:gbp|usd|eur|\$)\s*(?:5\d|[6-9]\d|\d{3,})m)",
    re.IGNORECASE,
)


def build_search_query(template: str, industry: str, market_label: str) -> str:
    negative_sites = " ".join(f"-site:{domain}" for domain in sorted(NON_COMPANY_DOMAINS))
    base_query = template.format(industry=industry, market=market_label)
    return f"{base_query} {negative_sites}".strip()


def build_search_jobs(include_secondary_markets: bool, max_queries: int) -> list[SearchJob]:
    markets = PRIMARY_MARKETS + (SECONDARY_MARKETS if include_secondary_markets else [])
    jobs: list[SearchJob] = []

    for signal_name, template in SEARCH_SIGNAL_TEMPLATES.items():
        for market in markets:
            for industry in INDUSTRY_PRIORITY:
                jobs.append(
                    SearchJob(
                        industry=industry,
                        market=market,
                        signal=signal_name,
                        query=build_search_query(template, industry, market.label),
                    )
                )
                if len(jobs) >= max_queries:
                    return jobs

    return jobs


def get_api_key() -> str:
    api_key = os.getenv("SERPAPI_API_KEY") or os.getenv("SERPAPI_KEY")
    if not api_key:
        raise RuntimeError("Missing SERPAPI_API_KEY or SERPAPI_KEY in your environment.")
    return api_key


def is_company_result(source_url: str, title: str, snippet: str) -> tuple[bool, str | None]:
    domain = normalize_domain(source_url)
    text = normalize_text(title, snippet)

    if not domain:
        return False, "missing domain"
    if is_blocked_domain(domain, NON_COMPANY_DOMAINS):
        return False, "excluded domain"
    if FILE_EXTENSION_PATTERN.search(source_url):
        return False, "document url"
    if any(pattern in text for pattern in SEARCH_RESULT_TEXT_EXCLUSIONS):
        return False, "low-quality third-party result"
    if any(pattern in text for pattern in EXCLUDED_VERTICAL_TERMS):
        return False, "excluded vertical"
    if any(pattern in text for pattern in EXISTING_REVOPS_TERMS):
        return False, "existing revops function"
    if MATURE_FUNDING_PATTERN.search(text):
        return False, "too mature"
    return True, None


def score_candidate(job: SearchJob, title: str, snippet: str, domain: str, source_url: str) -> int:
    text = normalize_text(title, snippet, domain, source_url)
    score = 0

    if job.industry.lower() in text:
        score += 12
    if "saas" in text or "software" in text:
        score += 8
    if job.market.label.lower() in text:
        score += 6
    if any(title_keyword.lower() in text for title_keyword in TARGET_DECISION_MAKER_TITLES):
        score += 4

    if job.signal == "funding" and any(token in text for token in ("series a", "series b", "series c", "funding", "raised")):
        score += 10
    if job.signal == "hiring" and any(token in text for token in ("hiring", "careers", "jobs", "join our team")):
        score += 10
    if job.signal == "visibility" and any(token in text for token in ("product launch", "conference", "speaker", "podcast")):
        score += 10
    if job.signal == "leadership" and any(token in text for token in ("ceo", "founder", "co-founder", "managing director")):
        score += 8

    if domain.endswith(".io") or domain.endswith(".ai") or domain.endswith(".com"):
        score += 2
    if any(path_hint in source_url.lower() for path_hint in ("/about", "/company", "/careers", "/leadership", "/team")):
        score += 3

    return score


def search_one_page(client: serpapi.Client, job: SearchJob, page_index: int) -> Iterable[SearchCandidate]:
    start = page_index * 10
    try:
        results = client.search(
            {
                "engine": SERPAPI_ENGINE,
                "q": job.query,
                "location": job.market.search_location,
                "google_domain": GOOGLE_DOMAIN,
                "hl": "en",
                "gl": job.market.gl,
                "start": start,
            }
        )
    except Exception as exc:
        print(
            f"Skipped search page {page_index + 1} for "
            f"{job.signal} | {job.industry} | {job.market.label}: {exc}"
        )
        return

    for result in results.get("organic_results", []):
        source_url = result.get("link", "")
        title = result.get("title", "")
        snippet = result.get("snippet", "")
        keep, _ = is_company_result(source_url, title, snippet)

        if not keep:
            continue

        domain = normalize_domain(source_url)
        yield SearchCandidate(
            company_url=normalize_homepage(source_url),
            source_url=source_url,
            domain=domain,
            title=title,
            snippet=snippet,
            industry=job.industry,
            market=job.market.label,
            signal=job.signal,
            query=job.query,
            score=score_candidate(job, title, snippet, domain, source_url),
            source_rank=result.get("position", 0) + start,
        )


def dedupe_candidates(candidates: Iterable[SearchCandidate]) -> list[SearchCandidate]:
    best_by_domain: dict[str, SearchCandidate] = {}

    for candidate in candidates:
        current = best_by_domain.get(candidate.domain)
        if current is None or candidate.score > current.score:
            best_by_domain[candidate.domain] = candidate

    return sorted(
        best_by_domain.values(),
        key=lambda candidate: (-candidate.score, candidate.domain),
    )


def write_output(candidates: list[SearchCandidate], output_path: Path, jobs: list[SearchJob]) -> None:
    payload = {
        "metadata": {
            "engine": SERPAPI_ENGINE,
            "query_count": len(jobs),
            "candidate_count": len(candidates),
            "notes": [
                "This file only covers search and candidate discovery.",
                "Search queries automatically exclude a large set of job boards, directories, and data vendors.",
                "Employee count, ARR, and online presence score still need later-stage validation.",
            ],
        },
        "candidates": [asdict(candidate) for candidate in candidates],
    }
    write_json(output_path, payload)


def print_summary(candidates: list[SearchCandidate]) -> None:
    print(f"Kept {len(candidates)} candidate domains.")
    print()

    for candidate in candidates[:20]:
        print(
            f"[{candidate.score:02d}] {candidate.company_url} | "
            f"{candidate.market} | {candidate.industry} | {candidate.signal}"
        )
        print(f"     {candidate.title}")


def run_search_pipeline(
    max_queries: int = DEFAULT_MAX_QUERIES,
    pages_per_query: int = DEFAULT_PAGES_PER_QUERY,
    include_secondary_markets: bool = False,
    delay_seconds: float = DEFAULT_SEARCH_DELAY_SECONDS,
    output_path: str = DEFAULT_SEARCH_OUTPUT_PATH,
) -> list[SearchCandidate]:
    client = serpapi.Client(api_key=get_api_key())
    jobs = build_search_jobs(include_secondary_markets=include_secondary_markets, max_queries=max_queries)
    collected: list[SearchCandidate] = []

    for index, job in enumerate(jobs, start=1):
        print(f"Running search {index}/{len(jobs)}: {job.signal} | {job.industry} | {job.market.label}")
        for page_index in range(pages_per_query):
            collected.extend(search_one_page(client, job, page_index))
            if delay_seconds:
                time.sleep(delay_seconds)

    deduped = dedupe_candidates(collected)
    write_output(deduped, Path(output_path), jobs)
    print_summary(deduped)
    return deduped
