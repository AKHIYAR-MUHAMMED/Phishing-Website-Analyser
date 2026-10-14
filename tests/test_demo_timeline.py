"""
Regression tests for the /demo pipeline timeline.

The timeline used to mark all seven stages "done" whenever any API response arrived, so an
"unavailable" result (failed crawl, HTTP error) looked as if the GNN, semantic analysis and fusion
had run. The page now derives each stage's state from what the response actually contains
(`stageOutcomes`) and renders done / failed / skipped steps differently (`pipelineStepsHtml`).

The page's own JavaScript (the block between the `timeline-logic` markers in dashboard/demo.html)
is executed with Node, so these tests exercise the real code, not a copy. They assert no scores or
model-quality values.

Node policy: locally, the Node-dependent tests are skipped when Node is not installed. When the CI
environment variable is set (GitHub Actions sets it), a missing Node fails the tests loudly instead of
silently skipping them.
"""

import json
import os
import re
import shutil
import socket
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from api import app

client = TestClient(app)

DEMO_HTML = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard", "demo.html")
STAGE_KEYS = ["crawl", "process", "graph", "gnn", "semantic", "fusion", "result"]

NODE = shutil.which("node")
IN_CI = bool(os.environ.get("CI"))


def node_requirement(node_path, in_ci) -> str:
    """What a Node-dependent test does: "run" when Node exists, otherwise "fail" in CI and "skip" locally."""
    if node_path:
        return "run"
    return "fail" if in_ci else "skip"


needs_node = pytest.mark.skipif(node_requirement(NODE, IN_CI) == "skip", reason="Node.js is not installed (skipped outside CI)")


def _page_source() -> str:
    with open(DEMO_HTML, encoding="utf-8") as f:
        return f.read()


def _timeline_logic() -> str:
    match = re.search(r"// <timeline-logic>(.*?)// </timeline-logic>", _page_source(), re.S)
    assert match, "timeline-logic block not found in dashboard/demo.html"
    return match.group(1)


def _evaluate(payloads):
    """Runs stageOutcomes and pipelineStepsHtml from the page on each payload with Node."""
    if node_requirement(NODE, IN_CI) == "fail":
        pytest.fail("Node.js is required for the demo timeline tests in CI but was not found on PATH")
    script = (
        _timeline_logic()
        + "\nconst input = JSON.parse(require('fs').readFileSync(0, 'utf8'));"
        + "\nconsole.log(JSON.stringify(input.map(d => {"
        + " const o = stageOutcomes(d); return {outcomes: o, html: pipelineStepsHtml(7, true, o)}; })));"
    )
    run = subprocess.run(["node", "-e", script], input=json.dumps(payloads), capture_output=True, encoding="utf-8", timeout=60)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def _states(result) -> dict:
    return {k: v["state"] for k, v in result["outcomes"].items()}


GNN_OK = {"status": "real_small_sample_model", "threat_score": 0.5, "graph_stats": {"node_count": 10, "edge_count": 18}}
SUCCESS = {
    "url": "http://x.example/", "verdict": "benign",
    "crawl": {"status": "ok", "http_status": 200},
    "components": {"url_lexical": {"status": "ok"}, "gnn": GNN_OK, "semantic": {"status": "heuristic", "score": 0.0}},
    "fusion": {"fused_score": 0.3, "contributing_components": ["gnn", "url_lexical", "semantic_heuristic"]},
}
HTTP_ERROR = {  # shape returned by /api/v2/analyze for an HTTP 4xx/5xx
    "url": "http://x.example/missing", "verdict": "unavailable", "verdict_reason": "The server returned HTTP 404 ...",
    "crawl": {"status": "ok", "http_status": 404}, "components": {},
}
CRAWL_FAILED = {
    "url": "http://127.0.0.1:9/x", "verdict": "unavailable", "verdict_reason": "Crawl did not complete; ...",
    "crawl": {"status": "error", "error_type": "connection_error", "http_status": None}, "components": {},
}


# --- the page logic itself -----------------------------------------------------------------

@needs_node
def test_successful_200_analysis_marks_every_stage_done():
    [result] = _evaluate([SUCCESS])
    assert _states(result) == {k: "done" for k in STAGE_KEYS}
    assert result["html"].count("pl-step done") == 7
    assert result["html"].count("✓") == 7
    assert "pl-step failed" not in result["html"] and "pl-step skipped" not in result["html"]


@needs_node
def test_http_error_shows_failed_crawl_and_no_later_stage_as_run():
    [result] = _evaluate([HTTP_ERROR])
    states = _states(result)
    assert states["crawl"] == "failed"
    assert result["outcomes"]["crawl"]["note"] == "Server returned HTTP 404"
    assert all(states[k] == "skipped" for k in STAGE_KEYS[1:])
    assert "pl-step done" not in result["html"] and "✓" not in result["html"]
    assert result["outcomes"]["result"]["note"] == "Unavailable"


@needs_node
@pytest.mark.parametrize("http_status", [400, 403, 500, 503])
def test_any_http_error_status_is_a_failed_crawl(http_status):
    payload = {**HTTP_ERROR, "crawl": {"status": "ok", "http_status": http_status}}
    [result] = _evaluate([payload])
    assert _states(result)["crawl"] == "failed"
    assert result["outcomes"]["crawl"]["note"] == f"Server returned HTTP {http_status}"
    assert all(s != "done" for s in _states(result).values())


@needs_node
def test_failed_crawl_shows_failed_then_skipped_without_http_wording():
    [result] = _evaluate([CRAWL_FAILED])
    states = _states(result)
    assert states["crawl"] == "failed"
    assert result["outcomes"]["crawl"]["note"] == "Crawl did not complete"
    assert all(states[k] == "skipped" for k in STAGE_KEYS[1:])
    assert "✓" not in result["html"]


@needs_node
def test_failed_skipped_and_done_steps_are_visually_distinct():
    partial = {**SUCCESS, "components": {"url_lexical": {"status": "ok"}}, "fusion": None, "verdict": "unavailable"}
    results = _evaluate([SUCCESS, HTTP_ERROR, partial])
    done_html, error_html, partial_html = (r["html"] for r in results)
    assert "pl-step done" in done_html and "pl-step failed" in error_html and "pl-step skipped" in error_html
    assert "✕" in error_html and "–" in error_html and "✓" not in error_html
    # a run that only produced some outputs keeps those stages done and the rest skipped
    assert _states(results[2]) == {
        "crawl": "done", "process": "done", "graph": "skipped", "gnn": "skipped",
        "semantic": "skipped", "fusion": "skipped", "result": "skipped",
    }
    assert "pl-step done" in partial_html and "pl-step skipped" in partial_html


@needs_node
def test_unavailable_gnn_is_not_shown_as_run():
    payload = {**SUCCESS, "components": {**SUCCESS["components"], "gnn": {"status": "unavailable", "note": "No HTML"}}}
    [result] = _evaluate([payload])
    states = _states(result)
    assert states["gnn"] == "skipped" and states["graph"] == "skipped"
    assert states["semantic"] == "done"


@needs_node
def test_stage_states_follow_the_outputs_in_the_response():
    """Whatever the backend returns, a stage is done exactly when its output is in the response."""
    [result] = _evaluate([SUCCESS])
    for key, present in {"process": "url_lexical", "gnn": "gnn", "semantic": "semantic"}.items():
        assert (_states(result)[key] == "done") == (present in SUCCESS["components"])
    assert (_states(result)["fusion"] == "done") == bool(SUCCESS.get("fusion"))


def test_in_flight_rendering_is_unchanged_and_final_state_uses_real_outcomes():
    source = _page_source()
    assert "renderPipelineVertical(STAGES.length, true, outcomes)" in source
    assert "renderPipelineVertical(STAGES.length, true);" not in source  # the unconditional all-done call
    assert "const allDone = STAGES.every(s => outcomes[s.key].state === 'done')" in source
    assert "Pipeline did not complete" in source
    for css in (".pl-step.failed .pl-dot", ".pl-step.skipped .pl-dot", ".pl-step.done .pl-dot"):
        assert css in source


# --- placeholders and invalid values are never "done" ---------------------------------------

def _with_component(name, value):
    return {**SUCCESS, "components": {**SUCCESS["components"], name: value}}


@needs_node
@pytest.mark.parametrize("status", ["unavailable", "error"])
@pytest.mark.parametrize("name,stage", [("url_lexical", "process"), ("semantic", "semantic")])
def test_placeholder_component_is_not_marked_done(name, stage, status):
    [result] = _evaluate([_with_component(name, {"status": status, "note": "placeholder"})])
    assert _states(result)[stage] == "skipped"
    assert _states(result)["crawl"] == "done"


@needs_node
@pytest.mark.parametrize("status", ["unavailable", "error"])
def test_placeholder_gnn_is_not_marked_done_even_with_a_score_and_graph_stats(status):
    [result] = _evaluate([_with_component("gnn", {**GNN_OK, "status": status})])
    states = _states(result)
    assert states["gnn"] == "skipped" and states["graph"] == "skipped"
    assert states["process"] == "done" and states["semantic"] == "done"


@needs_node
@pytest.mark.parametrize("status", ["unavailable", "error"])
def test_placeholder_fusion_is_not_marked_done(status):
    [result] = _evaluate([{**SUCCESS, "fusion": {"status": status}}])
    assert _states(result)["fusion"] == "skipped"


@needs_node
@pytest.mark.parametrize("score", [None, "0.9", True, [0.5], {"v": 1}])
def test_gnn_with_an_invalid_score_is_not_marked_done(score):
    [result] = _evaluate([_with_component("gnn", {**GNN_OK, "threat_score": score})])
    states = _states(result)
    assert states["gnn"] == "skipped"
    assert states["graph"] == "done"  # the graph statistics are present and valid


@needs_node
def test_gnn_without_a_score_field_is_not_marked_done():
    gnn = {k: v for k, v in GNN_OK.items() if k != "threat_score"}
    [result] = _evaluate([_with_component("gnn", gnn)])
    assert _states(result)["gnn"] == "skipped"


@needs_node
@pytest.mark.parametrize("score", [0, 0.0, 1, 0.9905])
def test_gnn_with_any_numeric_score_including_zero_is_done(score):
    [result] = _evaluate([_with_component("gnn", {**GNN_OK, "threat_score": score})])
    assert _states(result)["gnn"] == "done"


@needs_node
@pytest.mark.parametrize("component", [
    {"status": "ok"},                      # url_lexical as the backend sends it
    {"status": "heuristic", "score": 0.0},  # semantic as the backend sends it
    {"score": 0.0},                         # no status field at all
])
def test_legitimate_component_shapes_are_still_done(component):
    [result] = _evaluate([_with_component("semantic", component)])
    assert _states(result)["semantic"] == "done"


# --- Node requirement policy (local skip, CI fail) -------------------------------------------

@pytest.mark.parametrize("node_path,in_ci,expected", [
    ("/usr/bin/node", False, "run"),
    ("/usr/bin/node", True, "run"),
    (None, False, "skip"),
    (None, True, "fail"),
])
def test_node_requirement_policy(node_path, in_ci, expected):
    assert node_requirement(node_path, in_ci) == expected


def test_missing_node_fails_loudly_in_ci_instead_of_skipping(monkeypatch):
    this_module = sys.modules[__name__]
    monkeypatch.setattr(this_module, "NODE", None)
    monkeypatch.setattr(this_module, "IN_CI", True)
    with pytest.raises(pytest.fail.Exception, match="Node.js is required"):
        _evaluate([SUCCESS])


def test_when_ci_is_set_node_must_be_present():
    if IN_CI:
        assert NODE, "Node.js is required for the demo timeline tests in CI but was not found on PATH"


# --- API <-> timeline consistency ----------------------------------------------------------

def _closed_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@needs_node
def test_live_200_response_drives_an_all_done_timeline(http_server):
    body = client.post("/api/v2/analyze", json={"url": http_server.url("/ok")}).json()
    [result] = _evaluate([body])
    assert body["verdict"] in ("benign", "phishing")
    assert _states(result) == {k: "done" for k in STAGE_KEYS}


@needs_node
@pytest.mark.parametrize("url_factory", [lambda s: "not a url", lambda s: f"http://127.0.0.1:{_closed_local_port()}/x"])
def test_live_invalid_and_unreachable_responses_drive_a_failed_crawl_timeline(http_server, url_factory):
    body = client.post("/api/v2/analyze", json={"url": url_factory(http_server)}).json()
    [result] = _evaluate([body])
    assert body["verdict"] == "unavailable"
    states = _states(result)
    assert states["crawl"] == "failed"
    assert all(states[k] == "skipped" for k in STAGE_KEYS[1:])
    assert "✓" not in result["html"]
