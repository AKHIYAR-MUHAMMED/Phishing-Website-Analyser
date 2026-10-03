"""
Deterministic seeding utility.

No component built so far trains a model or samples random data at runtime, so nothing calls
this yet. It exists ahead of Phase 5 (GNN training) and Phase 7 (baselines), per the academic
integrity rule that every reported number must be reproducible from a committed script and seed
(CLAUDE.md section 14, rule 1). Call set_seed() at the start of any future training or data
generation script, before creating models, splits or samples.
"""

import os
import random
from typing import Optional

from config import RANDOM_SEED


def set_seed(seed: Optional[int] = None) -> int:
    """Seeds Python's random, NumPy and PyTorch (whichever are installed). Returns the seed used."""
    if seed is None:
        seed = RANDOM_SEED

    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)

    try:
        import numpy as np
        np.random.seed(seed)
    except ImportError:
        pass

    try:
        import torch
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    except ImportError:
        pass

    return seed
