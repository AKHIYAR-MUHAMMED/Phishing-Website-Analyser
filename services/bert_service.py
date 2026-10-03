"""
BERT service. Disabled in the Phase 0 honesty pass: the model was untrained and the score was
keyword-based.
"""

from typing import Any, Dict

from component_status import unavailable


class BERTService:
    @staticmethod
    def predict(url: str) -> Dict[str, Any]:
        return unavailable("bert")
