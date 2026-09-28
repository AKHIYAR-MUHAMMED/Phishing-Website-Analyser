"""
Visual model service (ViT, Phishpedia, VisualPhishNet, pHash, EER search).

Disabled in the Phase 0 honesty pass: every output was simulated with keyword rules or random
vectors, and the EER and benchmark figures came from another paper.
"""

from typing import Any, Dict

from component_status import unavailable


class ViTService:
    @staticmethod
    def predict(url: str, image_path: str = "") -> Dict[str, Any]:
        return unavailable("visual")

    @staticmethod
    def predict_phash(url: str) -> Dict[str, Any]:
        return unavailable("visual")

    @staticmethod
    def predict_phishpedia(url: str) -> Dict[str, Any]:
        return unavailable("visual")

    @staticmethod
    def predict_visualphishnet(url: str) -> Dict[str, Any]:
        return unavailable("visual")

    @staticmethod
    def predict_hybrid_visual(url: str) -> Dict[str, Any]:
        return unavailable("visual")

    @staticmethod
    def optimize_eer(dataset_name: str = "") -> Dict[str, Any]:
        return unavailable("benchmark")
