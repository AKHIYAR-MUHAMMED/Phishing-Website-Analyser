"""
Model registry helper.

log_model_deployment() stores metrics passed in by a caller; it invents none. Drift detection
and automated retraining are disabled (Phase 0 honesty pass). CLAUDE.md section 13 lists this
module for removal after verification.
"""

import datetime
from typing import Dict, Any

from component_status import unavailable
from database import SessionLocal, ModelRegistryDB


class MLOpsRegistryManager:
    """Manages model versioning, registry entries, and concept drift detection."""

    @staticmethod
    def log_model_deployment(model_name: str, version: str, accuracy: float, precision: float, recall: float, f1: float, weights_path: str) -> Dict[str, Any]:
        """Logs a newly trained model version into the database registry."""
        db = SessionLocal()
        try:
            entry = ModelRegistryDB(
                model_name=model_name,
                version=version,
                accuracy=accuracy,
                precision=precision,
                recall=recall,
                f1_score=f1,
                weights_filepath=weights_path,
                deployed_at=datetime.datetime.utcnow()
            )
            db.add(entry)
            db.commit()
            db.refresh(entry)
            return {
                "id": entry.id,
                "model_name": entry.model_name,
                "version": entry.version,
                "accuracy": f"{entry.accuracy:.2f}%",
                "deployed_at": entry.deployed_at.isoformat()
            }
        except Exception as e:
            db.rollback()
            return {"error": str(e)}
        finally:
            db.close()

    @staticmethod
    def detect_concept_drift() -> Dict[str, Any]:
        """
        Disabled in the Phase 0 honesty pass: it measured the synthetic training CSV (not incoming
        scans) against a literal 50% baseline.
        """
        return unavailable("dataset")

    @staticmethod
    def execute_retraining_pipeline() -> Dict[str, Any]:
        """
        Disabled in the Phase 0 honesty pass: it retrained on the synthetic dataset and logged
        literal 100.0 metrics regardless of the training result.
        """
        return unavailable("retraining")


if __name__ == "__main__":
    print(MLOpsRegistryManager.execute_retraining_pipeline())
