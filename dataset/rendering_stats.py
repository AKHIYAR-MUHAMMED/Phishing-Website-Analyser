"""
Cheap rendering-gap measurement statistics, computed at collection time
(PHASE3_DATASET_PLAN.md section 16 / section 14 item 8).

Records DOM node count, script tag count and visible-text length so the "benign pages are more
often thin, JS-rendered SPAs than phishing kits are" asymmetry is measurable in the dataset
card rather than an unstated assumption a model could exploit unnoticed. Does not render
JavaScript; this measures the served, static HTML only (see section 16's stated limitation).
"""

from bs4 import BeautifulSoup

from crawler.extract import extract_title_and_text


def compute_rendering_stats(html: str) -> dict:
    if not html or not html.strip():
        return {"dom_node_count": 0, "script_count": 0, "visible_text_length": 0}

    try:
        soup = BeautifulSoup(html, "html.parser")
        dom_node_count = len(soup.find_all(True))
        script_count = len(soup.find_all("script"))
    except Exception:
        dom_node_count = 0
        script_count = 0

    try:
        _, visible_text = extract_title_and_text(html)
    except Exception:
        visible_text = ""

    return {
        "dom_node_count": dom_node_count,
        "script_count": script_count,
        "visible_text_length": len(visible_text),
    }
