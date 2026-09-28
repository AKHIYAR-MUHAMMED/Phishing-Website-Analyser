"""
DNS record service.

Disabled in the Phase 0 honesty pass: the previous outputs were fabricated from URL keywords.
"""

from typing import Any, Dict

from component_status import unavailable


class DNSService:
    @staticmethod
    def analyze(url: str) -> Dict[str, Any]:
        return unavailable("whois_dns")
