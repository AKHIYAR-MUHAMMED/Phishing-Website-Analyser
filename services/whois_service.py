"""
WHOIS Registration & Domain Intelligence Service.
"""

from typing import Dict, Any
from collectors import WHOISDNSCollector


class WHOISService:
    @staticmethod
    def analyze(url: str) -> Dict[str, Any]:
        return WHOISDNSCollector.collect(url)
