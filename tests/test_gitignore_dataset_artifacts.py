"""
Guard: generated Phase 3 dataset artifacts must stay out of Git.

The capture manifest and everything derived from it (selection files, split lists, feed digests)
store raw feed URLs, which can embed victim identifiers (e-mail addresses, session or token
values). Committing them is suspended until URL privacy has been addressed (see the amendment at
the top of PHASE3_DATASET_PLAN.md). These tests fail if the ignore rules are weakened or if such an
artifact becomes tracked.

They ask git itself (`git check-ignore`, `git ls-files`) so the real ignore semantics are tested,
and are skipped when git is unavailable or the tests run outside a git work tree (e.g. from an
exported source archive).
"""

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is not available")


def _git(*args):
    return subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, timeout=30,
    )


@pytest.fixture(scope="module", autouse=True)
def _inside_git_work_tree():
    result = _git("rev-parse", "--is-inside-work-tree")
    if result.returncode != 0 or result.stdout.strip() != "true":
        pytest.skip("not inside a git work tree (for example an exported source archive)")


# Generated artifacts that contain raw/normalized crawled URLs, or raw page content.
MUST_BE_IGNORED = [
    "data/manifest.csv",
    "data/derived/selection_v5.csv",
    "data/splits/train.txt",
    "data/splits/val.txt",
    "data/splits/test.txt",
    "data/feed_digests/phishtank_2026-10-01.json",
    "data/raw/html/0000000000000000000000000000000000000000000000000000000000000000.html",
    "data/raw/feeds/run_2026-10-01_summary.json",
]

# Contain no crawled URLs (or are pre-existing legacy tracked files): must NOT be swept up by the
# ignore rules above.
MUST_NOT_BE_IGNORED = [
    "data/DATASET_CARD.md",
    "data/backups/run_2026-10-01_manifest.sha256",
    "data/tranco_used_ranks.json",
    "data/merged_phishing_multimodal_dataset.csv",
    "data/phishguard_x_dataset_metadata.json",
    "data/screenshots/paypal_phishing_sample.png",
]


@pytest.mark.parametrize("path", MUST_BE_IGNORED)
def test_generated_dataset_artifact_is_gitignored(path):
    result = _git("check-ignore", "-q", path)
    assert result.returncode == 0, f"{path} must be .gitignored (it can contain raw crawled URLs)"


@pytest.mark.parametrize("path", MUST_NOT_BE_IGNORED)
def test_url_free_and_legacy_files_are_not_gitignored(path):
    result = _git("check-ignore", "-q", path)
    assert result.returncode == 1, f"{path} should not be matched by the dataset-artifact ignore rules"


def test_no_generated_dataset_artifact_is_tracked():
    result = _git(
        "ls-files", "--", "data/manifest.csv", "data/derived", "data/splits",
        "data/feed_digests", "data/raw",
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "", f"generated dataset artifacts are tracked:\n{result.stdout}"


def test_no_tracked_file_matches_an_ignore_rule():
    # Files that are already tracked AND match an ignore pattern would indicate a rule that
    # silently conflicts with committed content (here: the legacy synthetic data files).
    result = _git("ls-files", "-ci", "--exclude-standard")
    assert result.returncode == 0
    assert result.stdout.strip() == "", f"tracked files match an ignore rule:\n{result.stdout}"
