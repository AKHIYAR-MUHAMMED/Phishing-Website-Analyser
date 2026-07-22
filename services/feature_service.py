"""
Central Feature Store Service:
Aggregates engineered tabular, graph, lexical, and behavioral feature vectors.
"""

from typing import Dict, Any
from dataset_loader import extract_url_lexical_features, extract_dom_graph_features
from collectors import WHOISDNSCollector, SSLEvaluator, JavascriptASTParser


class FeatureService:
    @staticmethod
    def extract_feature_vector(url: str, html_content: str = "") -> Dict[str, Any]:
        lexical = extract_url_lexical_features(url)
        dom = extract_dom_graph_features(html_content, url)
        whois_dns = WHOISDNSCollector.collect(url)
        ssl_info = SSLEvaluator.evaluate(url)
        js_ast = JavascriptASTParser.parse_script("", html_content)
        
        return {
            "lexical": lexical,
            "dom": dom,
            "whois_dns": whois_dns,
            "ssl_info": ssl_info,
            "js_ast": js_ast,
            "combined_vector": {**lexical, **dom, **whois_dns, **ssl_info, **js_ast}
        }
