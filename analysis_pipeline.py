"""
Honest end-to-end analysis pipeline for the demo (PhishGuard AI project review).

URL -> real crawl (crawler.fetch_url) -> real URL-lexical features (dataset_loader) ->
real DOM graph (gnn_model.parse_dom_to_graph) -> real GNN forward pass (gnn_model_demo.pt,
trained on the actual small real Phase 3 dataset, NOT the synthetic template) -> disclosed
rule-based semantic heuristic (semantic_heuristic.py, since no LLM API key is configured) ->
a simple, explicit fusion over whatever components actually ran -> a result payload with the
real evidence attached.

No fabricated scores, no hard-coded verdicts, no fake confidence/latency. If a step fails or a
component is unavailable, its section says so explicitly and it is excluded from fusion.
"""

import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

import torch
from bs4 import BeautifulSoup

from crawler.fetcher import fetch_url
from dataset_loader import extract_url_lexical_features
from gnn_model import PhishingGNN, parse_dom_to_graph
from semantic_heuristic import analyze_text_heuristically

_DEMO_WEIGHTS_PATH = Path(__file__).parent / "gnn_model_demo.pt"
_gnn_demo_model = None
_gnn_demo_status = None  # "real_small_sample_model" | "template_model_fallback" | "unavailable"


def _get_demo_gnn():
    global _gnn_demo_model, _gnn_demo_status
    if _gnn_demo_model is not None:
        return _gnn_demo_model, _gnn_demo_status
    model = PhishingGNN()
    if _DEMO_WEIGHTS_PATH.exists():
        try:
            model.load_state_dict(torch.load(_DEMO_WEIGHTS_PATH, map_location="cpu"))
            _gnn_demo_status = "real_small_sample_model"
        except Exception:
            _gnn_demo_status = "unavailable"
            model = None
    else:
        _gnn_demo_status = "unavailable"
        model = None
    if model is not None:
        model.eval()
    _gnn_demo_model = model
    return _gnn_demo_model, _gnn_demo_status


_RAW_MAGNITUDE_KEYS = {"url_length"}  # informational only; not a 0/1 risk indicator, excluded from scoring


def _lexical_risk_signal(lexical: Dict[str, float]) -> Dict[str, Any]:
    """A transparent, non-learned aggregate of the real lexical features — every value here is
    read directly from extract_url_lexical_features()'s real output, nothing invented.
    Only the 0/0.5/1 risk-indicator features are averaged into the score; raw magnitude
    features (e.g. url_length, a character count) are reported separately as context, not
    treated as an equal-weight risk flag."""
    indicator_features = {
        k: v for k, v in lexical.items()
        if k not in _RAW_MAGNITUDE_KEYS and isinstance(v, (int, float))
    }
    flagged = {k: v for k, v in indicator_features.items() if v > 0}
    score = sum(indicator_features.values()) / max(1, len(indicator_features))
    return {
        "score": round(score, 4),
        "flagged_features": flagged,
        "context": {k: v for k, v in lexical.items() if k in _RAW_MAGNITUDE_KEYS},
    }


# Elements that only scaffold a document and carry no page content of their own.
_SCAFFOLD_TAGS = {"html", "head", "body"}


def _no_analysable_html_reason(fetch_result: Dict[str, Any]) -> Optional[str]:
    """Returns why a successfully fetched response has no HTML page to analyse, or None when it does.

    The GNN, the DOM graph and the semantic heuristic only mean something for a real HTML page.
    Without one (empty body, a non-HTML content type, or markup with no elements) the stages would
    run on nothing, or on parse_dom_to_graph()'s synthetic fallback graph, and the result would be
    scored as if it described a page. The crawler leaves `html` empty for non-textual content types
    and also for a body that has no Content-Type header, so those are reported here as well."""
    html = fetch_result.get("html", "") or ""
    body_bytes = fetch_result.get("html_length_bytes")
    # Only the media type is echoed back: the header is server-controlled and shown in the UI.
    media_type = (fetch_result.get("content_type") or "").split(";", 1)[0].strip().lower()[:100]

    if body_bytes == 0:
        return "The server returned an empty response, so there is no page content to analyze."
    if "html" not in media_type:
        shown = f"content type: {media_type}" if media_type else "no content type was provided"
        return (f"The response was not identified as an HTML page ({shown}), so there is no page "
                "content to analyze.")
    if not html.strip():
        return "The response contained only whitespace, so there is no page content to analyze."
    if not any(tag.name.lower() not in _SCAFFOLD_TAGS for tag in BeautifulSoup(html, "html.parser").find_all(True)):
        return "The response contained no HTML page content (no elements), so there is nothing to analyze."
    return None


async def analyze_url(url: str) -> Dict[str, Any]:
    started = time.perf_counter()
    result: Dict[str, Any] = {"url": url, "components": {}}

    # 1-2. Real crawl
    fetch_result = await fetch_url(url)
    result["crawl"] = {
        "status": fetch_result.get("status"),
        "final_url": fetch_result.get("final_url"),
        "http_status": fetch_result.get("http_status"),
        "content_type": fetch_result.get("content_type"),
        "error_type": fetch_result.get("error_type"),
        "error_message": fetch_result.get("error_message"),
        "elapsed_ms": fetch_result.get("elapsed_ms"),
    }
    # The crawler reports status "ok" for any HTTP response and records the code in http_status.
    # An HTTP error (4xx/5xx) is a server-generated error page, not the requested page, so it
    # must not be scored: the verdict would describe the error page, not the target.
    http_status = fetch_result.get("http_status")
    unavailable_reason = None
    if fetch_result.get("status") != "ok":
        unavailable_reason = "Crawl did not complete; no page content to analyze."
    elif isinstance(http_status, int) and http_status >= 400:
        unavailable_reason = (
            f"The server returned HTTP {http_status} (an error response), not the requested page, "
            "so there is no target page content to analyze. The error page was not scored."
        )
    else:
        unavailable_reason = _no_analysable_html_reason(fetch_result)
    if unavailable_reason:
        result["verdict"] = "unavailable"
        result["verdict_reason"] = unavailable_reason
        result["elapsed_ms_total"] = round((time.perf_counter() - started) * 1000, 1)
        return result

    html = fetch_result.get("html", "") or ""
    final_url = fetch_result.get("final_url") or url
    title = fetch_result.get("title", "")
    visible_text = fetch_result.get("visible_text", "")

    # 3. Real URL lexical features (only reached when the response has an analysable HTML page)
    lexical = extract_url_lexical_features(url)
    result["components"]["url_lexical"] = {
        "status": "ok",
        "features": lexical,
        "signal": _lexical_risk_signal(lexical),
    }

    # 4-5. Real DOM graph + real GNN forward pass
    if html.strip():
        x, edge_index, graph_stats = parse_dom_to_graph(html, final_url)
        model, gnn_status = _get_demo_gnn()
        if model is not None:
            with torch.no_grad():
                embedding, prob = model.extract_graph_embedding(x, edge_index)
            result["components"]["gnn"] = {
                "status": gnn_status,
                "note": "Model retrained (train_gnn_demo.py) on the real, small Phase 3 dataset "
                        "(N=12 training samples) — NOT the synthetic 15-node template. Too few "
                        "samples to claim generalization; shown for demonstration only.",
                "threat_score": round(float(prob.item()), 4),
                "graph_stats": graph_stats,
            }
        else:
            result["components"]["gnn"] = {
                "status": "unavailable",
                "note": "No retrained model weights found (run train_gnn_demo.py).",
            }
    else:
        result["components"]["gnn"] = {
            "status": "unavailable",
            "note": "No HTML content was returned by the crawl (empty or non-HTML response).",
        }

    # 6. Disclosed semantic heuristic (real, deterministic — NOT an LLM; see semantic_heuristic.py)
    result["components"]["semantic"] = analyze_text_heuristically(title, visible_text)

    # 7. Honest fusion: simple average over whichever components actually produced a numeric
    # score. No component is silently substituted; the list of what contributed is explicit.
    scored = []
    if result["components"]["gnn"]["status"] == "real_small_sample_model":
        scored.append(("gnn", result["components"]["gnn"]["threat_score"]))
    scored.append(("url_lexical", result["components"]["url_lexical"]["signal"]["score"]))
    scored.append(("semantic_heuristic", result["components"]["semantic"]["score"]))

    fused_score = sum(v for _, v in scored) / len(scored)
    result["fusion"] = {
        "contributing_components": [name for name, _ in scored],
        "component_scores": dict(scored),
        "fused_score": round(fused_score, 4),
        "method": "unweighted mean of contributing real component scores (no trained fusion "
                  "model yet — see limitations)",
    }
    result["verdict"] = "phishing" if fused_score >= 0.5 else "benign"
    result["verdict_confidence_caveat"] = (
        "This is a small-sample demonstration pipeline, not a validated production classifier. "
        "The fused score is an unweighted average of real component outputs, not a calibrated "
        "probability."
    )
    result["elapsed_ms_total"] = round((time.perf_counter() - started) * 1000, 1)
    return result
