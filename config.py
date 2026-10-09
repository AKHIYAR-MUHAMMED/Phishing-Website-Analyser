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

# --- Phase 3 dataset collection (dataset/*.py) ---
DATASET_CRAWL_CONCURRENCY = _get_int("DATASET_CRAWL_CONCURRENCY", 5)
DATASET_CRAWL_HOST_DELAY_SECONDS = _get_float("DATASET_CRAWL_HOST_DELAY_SECONDS", 2.0)
DATASET_TLS_PROBE_TIMEOUT_SECONDS = _get_float("DATASET_TLS_PROBE_TIMEOUT_SECONDS", 5.0)
DATASET_RAW_DIR = REPO_ROOT / "data" / "raw"
DATASET_RAW_HTML_DIR = DATASET_RAW_DIR / "html"
DATASET_RAW_FEEDS_DIR = DATASET_RAW_DIR / "feeds"
DATASET_MANIFEST_PATH = REPO_ROOT / "data" / "manifest.csv"
DATASET_DERIVED_DIR = REPO_ROOT / "data" / "derived"
DATASET_SPLITS_DIR = REPO_ROOT / "data" / "splits"
DATASET_FEED_DIGESTS_DIR = REPO_ROOT / "data" / "feed_digests"
DATASET_BACKUPS_DIR = REPO_ROOT / "data" / "backups"
DATASET_CARD_PATH = REPO_ROOT / "data" / "DATASET_CARD.md"
# Committed (NOT under data/raw/, which is .gitignore'd): section 9's cumulative used-rank state
# must be recoverable/versioned so a lost/reset local raw directory can't silently re-permit
# resampling ranks already consumed by a committed dataset version.
DATASET_TRANCO_USED_RANKS_PATH = REPO_ROOT / "data" / "tranco_used_ranks.json"

# PhishTank bulk-feed application key. Empty by default: initial collection runs proceed
# anonymously (rate-limited); a key can be added later with no other code change (see
# PHASE3_DATASET_PLAN.md section 1, approved decision 11). Never logged or committed in plain
# text anywhere (see dataset/redaction.py and section 18).
PHISHTANK_APP_KEY = os.getenv("PHISHTANK_APP_KEY", "")

# --- Legacy synthetic dataset generator (dataset_loader.py) ---
# Empty by default: the previous hard-coded path pointed at one developer's Windows user cache
# and made the dataset generator fail (silently fall back to 8 rows) on every other machine.
# Not used by the honest scan pipeline; kept only so dataset_loader.py stays importable. See
# CLAUDE.md section 13 for the plan to replace this generator with real collected data.
KAGGLE_CACHE_CSV = os.getenv("PHISHGUARD_KAGGLE_CACHE_CSV", "")
