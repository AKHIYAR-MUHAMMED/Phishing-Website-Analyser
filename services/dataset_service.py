"""
Dataset service.

Phase 0 honesty pass: the committed dataset is synthetic (label-conditional random features),
so statistics, benchmark tables, screenshot connectors, external "fetches" and the publishing
export are disabled. validate_dataset() still runs its genuine file checks on the committed CSV.
"""

from typing import Any, Dict

from component_status import unavailable
from dataset_loader import validate_dataset_integrity


class DatasetService:
    @staticmethod
    def get_dataset_statistics() -> Dict[str, Any]:
        return unavailable("dataset")

    @staticmethod
    def get_screenshot_datasets() -> Dict[str, Any]:
        return unavailable("screenshot_datasets")

    @staticmethod
    def connect_screenshot_dataset(dataset_key: str = "all") -> Dict[str, Any]:
        return unavailable("screenshot_datasets")

    @staticmethod
    def fetch_external_datasets() -> Dict[str, Any]:
        return unavailable("screenshot_datasets")

    @staticmethod
    def regenerate_dataset(num_samples: int = 0) -> Dict[str, Any]:
        return unavailable("dataset")

    @staticmethod
    def export_publishing_package(output_csv: str = None, output_json: str = None) -> Dict[str, Any]:
        return unavailable("dataset")

    @staticmethod
    def validate_dataset(csv_path: str = None) -> Dict[str, Any]:
        result = validate_dataset_integrity(csv_path)
        result["note"] = "File integrity check only. " + unavailable("dataset")["reason"]
        return result
