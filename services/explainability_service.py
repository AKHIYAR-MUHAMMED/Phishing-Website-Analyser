"""
Explainable AI (XAI) Matrix & Saliency Feature Importance Service.
"""

from typing import Dict, Any, List


class ExplainabilityService:
    @staticmethod
    def generate_xai_report(fusion_report: Dict[str, Any]) -> List[Dict[str, Any]]:
        return fusion_report.get("xai_evidence_matrix", [])
