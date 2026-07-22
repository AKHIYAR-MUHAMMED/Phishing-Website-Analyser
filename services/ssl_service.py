"""
SSL & TLS Certificate Evaluation Service.
"""

from typing import Dict, Any
from collectors import SSLEvaluator


class SSLService:
    @staticmethod
    def analyze(url: str) -> Dict[str, Any]:
        return SSLEvaluator.evaluate(url)
