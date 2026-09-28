"""
Central configuration, read from environment variables. Every value has a safe default; none
of these are secrets. See .env.example for the full list and how to set them locally.

LLM API keys are read directly from the environment inside llm_ensemble.py (one variable per
provider); they are not duplicated here.
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional; environment variables can be set any other way.

REPO_ROOT = Path(__file__).resolve().parent


def _get_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


# --- Crawler safety limits (crawler/fetcher.py) ---
CRAWLER_TIMEOUT_SECONDS = _get_float("CRAWLER_TIMEOUT_SECONDS", 8.0)
CRAWLER_MAX_REDIRECTS = _get_int("CRAWLER_MAX_REDIRECTS", 5)
CRAWLER_MAX_CONTENT_BYTES = _get_int("CRAWLER_MAX_CONTENT_BYTES", 2_000_000)  # 2 MB
CRAWLER_USER_AGENT = os.getenv(
    "CRAWLER_USER_AGENT",
    "PhishGuardResearchCrawler/0.1 (+academic project; GET requests only, no form submission)",
)

# --- Reproducibility (seeding.py) ---
RANDOM_SEED = _get_int("RANDOM_SEED", 42)

# --- Legacy synthetic dataset generator (dataset_loader.py) ---
# Empty by default: the previous hard-coded path pointed at one developer's Windows user cache
# and made the dataset generator fail (silently fall back to 8 rows) on every other machine.
# Not used by the honest scan pipeline; kept only so dataset_loader.py stays importable. See
# CLAUDE.md section 13 for the plan to replace this generator with real collected data.
KAGGLE_CACHE_CSV = os.getenv("PHISHGUARD_KAGGLE_CACHE_CSV", "")
