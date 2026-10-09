"""
Explainability service. No genuine explanation method is implemented yet (planned: Phase 9).
"""

from typing import Any, Dict

from component_status import unavailable


class ExplainabilityService:
    @staticmethod
    def generate_xai_report(fusion_report: Dict[str, Any]) -> Dict[str, Any]:
        return unavailable("explanation")
