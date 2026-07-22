"""
DNS Record Intelligence Service (MX, SPF, TXT, A, CNAME).
"""

from typing import Dict, Any
from collectors import WHOISDNSCollector


class DNSService:
    @staticmethod
    def analyze(url: str) -> Dict[str, Any]:
        res = WHOISDNSCollector.collect(url)
        return {
            "domain": res["domain"],
            "dns_records": res["dns_records"],
            "has_mx_record": res["has_mx_record"],
            "has_spf_record": res["has_spf_record"]
        }
