"""
Dashboard status service. Reports the real status of every component instead of fixed
telemetry (the previous version reported a literal throughput and modality count).
"""

from typing import Any, Dict

from component_status import component_registry


class DashboardService:
    @staticmethod
    def get_telemetry() -> Dict[str, Any]:
        return {"components": component_registry()}
