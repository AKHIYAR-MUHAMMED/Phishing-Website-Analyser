"""
Classical ML and anomaly-detection service.

Disabled in the Phase 0 honesty pass: no classical model or autoencoder is trained; previous
scores were keyword rules. Honest baselines are planned (Phase 7).
"""

from typing import Any, Dict

from component_status import unavailable


class EnsembleService:
    def predict(self, feature_vector: Dict[str, Any], url: str) -> Dict[str, Any]:
        return unavailable("classical_ml")

    def predict_rf(self, feature_vector: Dict[str, Any], url: str) -> Dict[str, Any]:
        return unavailable("classical_ml")

    def predict_catboost(self, feature_vector: Dict[str, Any], url: str) -> Dict[str, Any]:
        return unavailable("classical_ml")

    def predict_autoencoder(self, feature_vector: Dict[str, Any], url: str) -> Dict[str, Any]:
        return unavailable("anomaly")
