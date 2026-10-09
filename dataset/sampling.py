"""
Benign (Tranco) rank sampling (PHASE3_DATASET_PLAN.md section 9, approved decision 8).

Rank-progressive, without replacement, stratified across rank bands, so repeated runs do not
keep re-sampling the same near-static top-of-list domains (which would find them
"already_collected" and contribute nothing — see section 5/section 9), and so the benign class
is not concentrated in a handful of mega-brand domains.

Deterministic: the only randomness is a seeded shuffle within each band, so the same
(available_ranks, already_used, target_count, seed) always produces the same sample.
"""

import random
from typing import Iterable, List, Optional, Set

import config

RANK_BANDS = ((1, 100), (101, 1_000), (1_001, 10_000), (10_001, 100_000), (100_001, 1_000_000))


def stratify_bands(max_rank: int) -> List[tuple]:
    return [(lo, hi) for lo, hi in RANK_BANDS if lo <= max_rank]


def sample_benign_ranks(
    available_ranks: Iterable[int],
    already_used: Set[int],
    target_count: int,
    seed: Optional[int] = None,
) -> List[int]:
    """Returns up to `target_count` ranks drawn from `available_ranks`, excluding
    `already_used`, proportionally stratified across RANK_BANDS, deterministic given `seed`."""
    if target_count <= 0:
        return []
    seed = config.RANDOM_SEED if seed is None else seed
    rng = random.Random(seed)

    unused = sorted(set(available_ranks) - set(already_used))
    if not unused:
        return []

    banded = []
    for lo, hi in RANK_BANDS:
        members = [r for r in unused if lo <= r <= hi]
        rng.shuffle(members)
        banded.append(members)

    total_available = sum(len(b) for b in banded)
    if total_available == 0:
        return []

    targets = [round(target_count * (len(b) / total_available)) for b in banded]

    result: List[int] = []
    for band_members, take in zip(banded, targets):
        result.extend(band_members[:take])

    # Rounding can leave the result short of target_count; top up deterministically from
    # whatever unused members remain, in band order.
    if len(result) < target_count:
        taken = set(result)
        for band_members in banded:
            for rank in band_members:
                if rank in taken:
                    continue
                result.append(rank)
                taken.add(rank)
                if len(result) >= target_count:
                    break
            if len(result) >= target_count:
                break

    return sorted(result[:target_count])
