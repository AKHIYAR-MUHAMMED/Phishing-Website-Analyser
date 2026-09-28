"""
PhishGuard scan pipeline (Phase 0 honesty pass + Phase 2 real crawler).

This module runs ONE scan pipeline and reports only genuine observations:
- a live HTTP fetch of the URL (crawler/fetcher.py) when the request supplies no HTML,
- URL lexical features computed from the URL string,
- DOM graph statistics built from the HTML (crawled or request-supplied),
- regex-based JavaScript indicator counts (labelled heuristic),
- results from LLM API clients that actually returned a valid answer.

It does NOT produce a verdict or phishing probability: no trained fusion model exists yet,
and the GNN weights were trained on synthetic template graphs (see component_status.REASONS).
The previous hand-weighted average of simulated modality scores has been removed.
"""

import time
import asyncio
from typing import Any, Dict, Tuple

from bs4 import BeautifulSoup

from component_status import AVAILABLE, HEURISTIC, UNAVAILABLE, REASONS, unavailable
from crawler import fetch_url
from dataset_loader import extract_url_lexical_features
from gnn_model import parse_dom_to_graph
from collectors import JavascriptASTParser
from llm_ensemble import get_llm_orchestrator

# Must match the truncation inside gnn_model.parse_dom_to_graph.
GNN_MAX_NODES = 200

DISABLED_MODALITIES = ("visual", "bert", "classical_ml", "anomaly", "whois_dns", "ssl", "threat_intel")


async def describe_crawl(url: str, html_content: str) -> Tuple[Dict[str, Any], str]:
    """
    Returns (crawl_status, effective_html). If the request supplied HTML, it is used unchanged
    and no network request is made. Otherwise the URL is fetched live (crawler/fetcher.py).
    """
    if html_content and html_content.strip():
        return ({"status": AVAILABLE, "source": "request_html_content",
                 "html_length_bytes": len(html_content.encode("utf-8"))}, html_content)

    raw = await fetch_url(url)
    if raw["status"] != "ok":
        return ({"component": "crawler", "status": UNAVAILABLE, "source": "live_crawl",
                  "error_type": raw["error_type"], "reason": raw["error_message"],
                  "elapsed_ms": raw["elapsed_ms"]}, "")

    crawl_status = {k: v for k, v in raw.items() if k != "html"}
    crawl_status["status"] = AVAILABLE
    crawl_status["source"] = "live_crawl"
    return crawl_status, raw["html"]


def analyse_dom(url: str, html_content: str) -> Dict[str, Any]:
    """DOM graph statistics from the same parser the GNN uses. No model output."""
    if not html_content or not html_content.strip():
        return unavailable("dom_graph", "No HTML available: the crawl did not return usable HTML and none was supplied.")

    total_elements = len(BeautifulSoup(html_content, "html.parser").find_all(True))
    if total_elements == 0:
        return unavailable("dom_graph", "The supplied HTML contains no elements.")

    x, edge_index, _ = parse_dom_to_graph(html_content, url)
    node_count = int(x.shape[0])
    # Columns follow gnn_model.parse_dom_to_graph: 1 form, 2 password input, 11 external, 12 hidden.
    return {
        "status": AVAILABLE,
        "kind": "observed_structure",
        "total_html_elements": total_elements,
        "graph_node_count": node_count,
        "truncated_to_first_n_elements": GNN_MAX_NODES if total_elements > GNN_MAX_NODES else None,
        "parent_child_edge_count": int(edge_index.shape[1]) // 2,
        "form_nodes": int((x[:, 1] > 0).sum().item()),
        "password_input_nodes": int((x[:, 2] > 0).sum().item()),
        "external_reference_nodes": int((x[:, 11] > 0).sum().item()),
        "hidden_nodes": int((x[:, 12] > 0).sum().item()),
        "known_limitations": (
            "External detection uses a substring match on the domain and hidden detection misses "
            "'display: none' with a space and CSS classes (CLAUDE.md section 5.1). Fix planned in Phase 4."
        ),
    }


def analyse_javascript(html_content: str) -> Dict[str, Any]:
    if not html_content or not html_content.strip():
        return unavailable("js_indicators", "No HTML available.")
    counts = JavascriptASTParser.parse_script("", html_content)
    counts.pop("js_ast_risk_score", None)  # hand-weighted score; not reported
    return {"status": HEURISTIC, "kind": "regex_pattern_counts",
            "note": "Regex counts over the raw HTML; not an AST parser and not a classifier.",
            "counts": counts}


class MultimodalPhishingDetector:
    """Runs the scan pipeline once. Name kept for compatibility with existing callers."""

    def __init__(self):
        self.llm_orchestrator = get_llm_orchestrator()

    async def detect_url(self, target_url: str, html_content: str = "", image_path: str = "") -> Dict[str, Any]:
        start = time.perf_counter()
        crawl_status, effective_html = await describe_crawl(target_url, html_content or "")

        modalities: Dict[str, Any] = {
            "url_features": {"status": AVAILABLE, "kind": "observed_url_features",
                             "features": extract_url_lexical_features(target_url)},
            "dom_graph": analyse_dom(target_url, effective_html),
            "js_indicators": analyse_javascript(effective_html),
            "gnn": unavailable("gnn"),
            "llm": await self.llm_orchestrator.run_ensemble(target_url, effective_html[:1000]),
        }
        for name in DISABLED_MODALITIES:
            modalities[name] = unavailable(name)

        return {
            "target_url": target_url,
            "verdict": None,
            "phishing_probability": None,
            "decision": {"status": UNAVAILABLE, "reason": REASONS["fusion"]},
            "crawl": crawl_status,
            "modalities": modalities,
            "explanation": unavailable("explanation"),
            "processing_latency_ms": round((time.perf_counter() - start) * 1000.0, 1),
        }


_detector_instance = None


def get_detector() -> MultimodalPhishingDetector:
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = MultimodalPhishingDetector()
    return _detector_instance


if __name__ == "__main__":
    import json
    html = "<html><body><form action='http://other.example/post'><input type='password'></form></body></html>"
    report = asyncio.run(get_detector().detect_url("http://example.com/login", html))
    print(json.dumps(report, indent=2))
