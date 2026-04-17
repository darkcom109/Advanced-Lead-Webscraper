from __future__ import annotations

import os

from dotenv import load_dotenv

from lead_pipeline.config import (
    DEFAULT_MAX_QUERIES,
    DEFAULT_PAGES_PER_QUERY,
    DEFAULT_SEARCH_DELAY_SECONDS,
    DEFAULT_SEARCH_OUTPUT_PATH,
)
from lead_pipeline.search_stage import run_search_pipeline

load_dotenv()


if __name__ == "__main__":
    run_search_pipeline(
        max_queries=int(os.getenv("MAX_QUERIES", DEFAULT_MAX_QUERIES)),
        pages_per_query=int(os.getenv("PAGES_PER_QUERY", DEFAULT_PAGES_PER_QUERY)),
        include_secondary_markets=os.getenv("INCLUDE_SECONDARY_LOCATIONS", "").lower() in {"1", "true", "yes"},
        delay_seconds=float(os.getenv("SEARCH_DELAY_SECONDS", DEFAULT_SEARCH_DELAY_SECONDS)),
        output_path=os.getenv("SEARCH_OUTPUT_PATH", DEFAULT_SEARCH_OUTPUT_PATH),
    )
