# PhishGuard AI — Project Status Snapshot

Snapshot first taken 2026-09-30 for the project review; dataset and test status refreshed
2026-10-06 when this documentation pack was committed. Re-verify with `git status` if anything
changes before the presentation.

---

## Current branch

`demo-sprint`

## Current commit

`c9e3340` — "Demo sprint M1-3: honest end-to-end analyze pipeline + demo dashboard"

## Changes on top of `c9e3340` (committed together with this file)

```
dashboard/demo.html, app.js, index.html, styles.css, assets/phishguard-logo.png   (UI redesign + supplied logo)
component_status.py                    (status vocabulary; "Current Implementation & Roadmap" honesty text)
dataset_loader.py                      (bug fix: URL-shortener hostname matching)
semantic_heuristic.py                  (bug fix: word-boundary keyword matching)
tests/test_api.py                      (accepts the extended status vocabulary)
tests/test_dataset_loader_lexical.py   (regression tests for the shortener fix)
tests/test_semantic_heuristic.py       (regression tests for the word-boundary fix)
DEMO_GUIDE.md, DEMO_SCRIPT.md, PROJECT_EXPLANATION.md, TECHNICAL_ARCHITECTURE.md,
TROUBLESHOOTING.md, VIVA_QA.md, PROJECT_STATUS.md, QUICK_REFERENCE.md   (documentation pack)
```

## Dataset (Phase 3)

Collection complete (dataset version v5, stored locally in `phishguard-phase3-pilot/`, not in this
repository): 679 eligible samples (331 phishing, 348 benign); train 408 (199/209), validation 135
(66/69), test 136 (66/70); zero cross-split domain leakage, zero label conflicts. Off-machine backup
is **not** verified. **No model has been retrained or evaluated on this dataset yet.** The
snapshot-integrity fix used for the final collection run lives on the separate
`phase-3-dataset-scale` branch, not on `demo-sprint`.

## Tests

Full suite on this branch (2026-10-06): **314 passed, 1 failed**. The failure,
`tests/test_dataset_orchestrator.py::test_run_bulk_capture_does_not_delay_across_different_hosts`,
is environmental: it connects via the hostname `localhost`, which takes ~2 s on this Windows machine
(IPv6 fallback) versus ~0 s for `127.0.0.1`, pushing elapsed time to 4.8 s against the test's 4.0 s
bound. The orchestrator code and the test are unchanged from `c9e3340`, where the suite had passed
315/315. The test was not weakened.

## Demo status

Verified live and working at `http://localhost:8000/demo`:
- `github.com` → Benign, fused 7.8%, GNN 0.01%, 200 DOM nodes/398 edges (matches the original
  pre-experiment baseline exactly)
- `posototo.ink` → real, distinct output (fused 36.7%, GNN 86.66%) — confirms genuinely
  different real results for different real input
- No browser console errors

## Main implemented components

- Real async HTTP crawler (`crawler/fetcher.py`)
- Real URL-lexical feature extraction (`dataset_loader.py::extract_url_lexical_features`)
- Real DOM-to-graph construction + 2-layer GAT GNN forward pass (`gnn_model.py`), weights trained
  on N=12 real Phase 3 pilot samples (`train_gnn_demo.py` → `gnn_model_demo.pt`)
- Disclosed rule-based semantic heuristic, explicitly not an LLM (`semantic_heuristic.py`)
- Honest unweighted-mean fusion over whichever components actually ran (`analysis_pipeline.py`)
- `POST /api/v2/analyze` API endpoint and `GET /demo` dashboard (`api.py`,
  `dashboard/demo.html`)

## Known limitations

- GNN trained on only 12 real labeled samples — no generalization claim
- No LLM integrated (disclosed heuristic substitute)
- Fusion is an unweighted average, not a trained fusion model
- DOM graph capped at 200 elements per page (older, simpler cap — see next section)
- No formal accuracy/precision/recall/F1/ROC-AUC claim for this demo build

## Experimental work that is NOT part of the demo

A separate branch, `gnn-reliability-repair`, contains a completed diagnostic/repair experiment
(raising the DOM-graph node cap from 200→500 with body-content-priority selection, consolidating
a duplicated constant, and a regularized GNN retrain with early stopping). That retrain caused a
real regression — a well-known legitimate site (`amazon.com`) flipped from Benign to "Phishing"
— so it was **not adopted**. That branch's full uncommitted state is preserved as a named git
stash (`stash@{0}`, on branch `gnn-reliability-repair`) for later review — it is not merged,
not committed, not part of this demo, and not reflected in the live `/demo` server. The two
independently-verified bug fixes from that experiment (URL-shortener matching, semantic
word-boundary matching) **were** ported into this demo state, since they don't depend on the
retrain or the cap change.

## What is safe to demonstrate tomorrow

- The full live pipeline on any real, reachable URL, exactly as described in `DEMO_GUIDE.md`
- The honesty/transparency panels (status strip, "Model & Dataset Transparency", raw JSON)
- The fact that outputs genuinely change with genuinely different input

## What should NOT be claimed during the presentation

- Do not claim the GNN is validated, production-ready, or generalizes beyond its training data
- Do not present the Fused Threat Signal as a calibrated probability
- Do not claim an LLM is running — the semantic component is an explicitly disclosed heuristic
- Do not cite `gnn_model_demo_metrics.json`'s train/val accuracy as evidence of real performance
  — it reflects a 12-sample training set and is disclosed as a memorization risk, not a result
- Do not mention the `gnn-reliability-repair` experiment as if it were part of the running demo
