"""
Feature service: genuine observations only (URL lexical features, DOM graph statistics,
JavaScript regex counts). Fabricated WHOIS/DNS/SSL features are no longer included.
"""

from typing import Any, Dict

from dataset_loader import extract_url_lexical_features
from multimodal_fusion import analyse_dom, analyse_javascript


class FeatureService:
    @staticmethod
    def extract_feature_vector(url: str, html_content: str = "") -> Dict[str, Any]:
        return {
            "url_features": extract_url_lexical_features(url),
            "dom_graph": analyse_dom(url, html_content),
            "js_indicators": analyse_javascript(html_content),
        }
