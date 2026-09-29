from dataset.sampling import sample_benign_ranks, stratify_bands


def test_deterministic_given_same_seed():
    ranks = list(range(1, 2000))
    a = sample_benign_ranks(ranks, set(), target_count=50, seed=7)
    b = sample_benign_ranks(ranks, set(), target_count=50, seed=7)
    assert a == b


def test_different_seed_can_differ():
    ranks = list(range(1, 2000))
    a = sample_benign_ranks(ranks, set(), target_count=50, seed=1)
    b = sample_benign_ranks(ranks, set(), target_count=50, seed=2)
    assert a != b


def test_without_replacement_excludes_already_used():
    ranks = list(range(1, 200))
    used = set(range(1, 150))
    result = sample_benign_ranks(ranks, used, target_count=30, seed=1)
    assert set(result).isdisjoint(used)


def test_respects_target_count_when_enough_available():
    ranks = list(range(1, 2000))
    result = sample_benign_ranks(ranks, set(), target_count=100, seed=1)
    assert len(result) == 100


def test_returns_fewer_when_not_enough_available():
    ranks = list(range(1, 10))
    result = sample_benign_ranks(ranks, set(), target_count=100, seed=1)
    assert len(result) == 9


def test_zero_target_returns_empty():
    assert sample_benign_ranks([1, 2, 3], set(), target_count=0) == []


def test_stratify_bands_limits_to_max_rank():
    bands = stratify_bands(5000)
    assert bands[-1][1] <= 10_000
    assert (100_001, 1_000_000) not in bands


def test_sampling_draws_from_multiple_bands_when_available():
    ranks = list(range(1, 200_000))
    result = sample_benign_ranks(ranks, set(), target_count=500, seed=3)
    bands_hit = set()
    for r in result:
        if r <= 100:
            bands_hit.add("top")
        elif r <= 1000:
            bands_hit.add("mid")
        else:
            bands_hit.add("tail")
    assert len(bands_hit) > 1
