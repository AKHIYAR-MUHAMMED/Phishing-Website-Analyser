"""
DNS Record Intelligence Service (MX, SPF, TXT, A, CNAME).
"""

from typing import Dict, Any
from collectors import WHOISDNSCollector


class DNSService:
    """Microservice interface for inspecting DNS record structures and detecting fast-flux anomalies."""

    @staticmethod
    def analyze(url: str) -> Dict[str, Any]:
        res = WHOISDNSCollector.collect(url)
        dns_records = res.get("dns_records", {})
        
        # Calculate fast-flux risk score based on A/CNAME record counts and SPF/MX configuration
        a_records = dns_records.get("A", [])
        cname_records = dns_records.get("CNAME", [])
        has_mx = res.get("has_mx_record", False)
        has_spf = res.get("has_spf_record", False)

        fast_flux_risk = 0.0
        if len(a_records) > 3:
            fast_flux_risk += 0.35
        if not has_mx and not has_spf:
            fast_flux_risk += 0.40
        if len(cname_records) > 2:
            fast_flux_risk += 0.25

        return {
            "domain": res.get("domain", ""),
            "dns_records": dns_records,
            "has_mx_record": has_mx,
            "has_spf_record": has_spf,
            "fast_flux_risk_score": min(1.0, round(fast_flux_risk, 2)),
            "dns_security_verdict": "HIGH_RISK" if fast_flux_risk >= 0.5 else "SECURE"
        }

