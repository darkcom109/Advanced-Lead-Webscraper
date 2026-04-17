from __future__ import annotations

import os

from dotenv import load_dotenv

from lead_pipeline.config import (
    DEFAULT_INSPECTION_DELAY_SECONDS,
    DEFAULT_INSPECT_INPUT_PATH,
    DEFAULT_INSPECT_OUTPUT_PATH,
    DEFAULT_MAX_PAGES_PER_COMPANY,
    DEFAULT_TIMEOUT_SECONDS,
)
from lead_pipeline.inspect_stage import run_inspection

load_dotenv()


if __name__ == "__main__":
    run_inspection(
        input_path=os.getenv("SEARCH_CANDIDATES_PATH", DEFAULT_INSPECT_INPUT_PATH),
        output_path=os.getenv("INSPECTED_OUTPUT_PATH", DEFAULT_INSPECT_OUTPUT_PATH),
        timeout_seconds=float(os.getenv("REQUEST_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)),
        delay_seconds=float(os.getenv("INSPECTION_DELAY_SECONDS", DEFAULT_INSPECTION_DELAY_SECONDS)),
        max_pages_per_company=int(os.getenv("MAX_PAGES_PER_COMPANY", DEFAULT_MAX_PAGES_PER_COMPANY)),
    )
