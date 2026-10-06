# PhishGuard AI — Technical Project Explanation

Describes only components that exist and run in the current `demo-sprint` implementation
(commit `c9e3340` + two bug fixes — see `PROJECT_STATUS.md`). Legacy endpoints and modules
listed in `CLAUDE.md` §3/§13 (screenshots, "10-LLM ensemble", ViT, WHOIS/DNS/SSL collectors,
etc.) are pre-existing, simulated, and explicitly out of scope for this demo.

---

## Problem statement

Phishing websites imitate legitimate login/checkout pages to steal credentials. Detection that
relies only on the URL string is cheap to evade. This project analyzes the URL, the page's real
DOM structure, and the page's real text together, and reports each signal's contribution
separately rather than a single opaque score.

## Motivation

The project's documented objective (see `CLAUDE.md` §1) is a multimodal detector combining a
Graph Neural Network (structure) and a language model (semantics), fused into one decision, with
explainability. An earlier audit (`CLAUDE.md`) found the original repository's components were
almost entirely fabricated (random data, hard-coded metrics, keyword-only "LLM" fallbacks). The
current `demo-sprint` implementation is a from-scratch honest pipeline built to actually perform
the operations it claims.

## Objectives (current demo scope)

1. Crawl a given URL for real.
2. Extract real URL-lexical features.
3. Build a real DOM graph and run a real GNN forward pass over it.
4. Run a disclosed rule-based semantic heuristic over the real page text (not an LLM — none is
   configured in this environment).
5. Fuse the components that actually ran into one score, honestly labeled.
6. Present every component's real evidence, not just a final verdict.

## Overall architecture

```
URL → Crawler → HTML + visible text
                  ├─ URL lexical features (dataset_loader.py)
                  ├─ DOM → Graph → GNN (gnn_model.py)
                  └─ Semantic heuristic (semantic_heuristic.py)
                        ↓
                 Unweighted-mean fusion (analysis_pipeline.py)
                        ↓
                 Verdict + evidence → dashboard/demo.html
```

See `TECHNICAL_ARCHITECTURE.md` for the annotated diagram.

## Crawler

`crawler/fetcher.py::fetch_url()` — a real async HTTP GET (httpx), 8-second timeout, follows up
to 5 redirects, 2 MB content cap, User-Agent set from config. Returns final URL, HTTP status,
content type, raw HTML, extracted title/visible text, redirect count, and a SHA-256 of the raw
response bytes — or an explicit error status (`timeout`, `connection_error`, `ssl_error`,
`content_too_large`, `invalid_url`, etc.) if the fetch does not succeed. Never returns a
synthetic/fake page.

## URL analysis

`dataset_loader.py::extract_url_lexical_features()` computes, from the URL string alone: IP-
address-as-host check, URL length (and a length-based score), known-shortener hostname match
(exact host or true subdomain — not a substring match), `@` symbol presence, double-slash
position, hyphen in domain, subdomain count, https-token presence, and abnormal-URL check. All
real string operations on the actual URL, no randomness.

## HTML/DOM processing and DOM-to-graph representation

`gnn_model.py::parse_dom_to_graph()` parses the real fetched HTML with BeautifulSoup. Every HTML
element becomes one graph node (capped at the first 200 elements in document order, for
real-time performance). Each node gets a 14-dimension feature vector: a 10-way one-hot tag type
(root/form/password-input/text-input/anchor/script/img/iframe/div/unknown), normalized depth in
the tree, an external-link/action flag, a hidden-element flag, and a normalized child count.
Edges connect each element to its parent (bidirectional). If the page has no HTML content, an
explicit minimal fallback graph is used and reported as such rather than silently proceeding.

## GNN (Graph Neural Network)

`gnn_model.py::PhishingGNN` — a 2-layer custom Graph Attention (GAT) network with 2 attention
heads per layer, global mean+max pooling over all nodes, and a small fully-connected classifier
head with dropout, ending in a sigmoid. Weights are loaded from `gnn_model_demo.pt`, trained by
`train_gnn_demo.py` on N=12 real webpage DOM graphs from the Phase 3 pilot dataset (8 phishing,
4 benign) — not the older synthetic 15-node template used by `train_gnn.py`/`gnn_model.pt`. The
dashboard explicitly discloses that N=12 is too small to claim generalization.

## Semantic analysis

`semantic_heuristic.py::analyze_text_heuristically()` — a disclosed, deterministic, rule-based
keyword scanner over the page's real title and visible text. Checks for credential-related
terms, urgency terms, brand-name terms, and login-form language, using word-boundary regex
matching (not raw substring search) to avoid false positives. Always reported with
`status: "heuristic"`, never presented as an LLM output. No LLM API key is configured in this
environment, so no real language-model call is made anywhere in this pipeline.

## Multimodal/fusion stage

`analysis_pipeline.py::analyze_url()` builds a `scored` list from only the components that
actually produced a numeric score (GNN is excluded if its weights failed to load; URL and
semantic scores are always included since they never depend on external state). The fused score
is the plain unweighted mean of that list. Verdict is `"phishing"` if the fused score is ≥ 0.5,
else `"benign"`. This is explicitly documented as not a trained fusion model and not a
calibrated probability.

## Explainability/evidence

Every component's raw evidence is returned alongside its score: URL's flagged lexical features,
GNN's graph node/edge/density stats, semantic's exact matched keyword terms. The dashboard
groups this evidence under "Why This Result?" per modality, and exposes the full raw JSON API
response under "Technical Details" for full transparency.

## API

`api.py` — FastAPI app. The demo-relevant routes are `GET /demo` (serves the dashboard) and
`POST /api/v2/analyze` (runs the full pipeline above and returns the JSON result). Numerous
other routes exist in `api.py` from the pre-existing legacy system (`/api/v1/*`, `/models/*`) —
these are **not** part of this honest demo pipeline; see `CLAUDE.md` for their status.

## Dashboard

`dashboard/demo.html` — a single-page dashboard that calls only `/api/v2/analyze`. Shows a live
7-stage pipeline timeline, the verdict card with a Fused Threat Signal (explicitly not called a
"probability"), three per-modality signal cards with real evidence, an illustrative DOM-graph
visualization built from real node/edge/density counts, a fusion breakdown, grouped evidence,
crawl metadata, and collapsible transparency/raw-JSON sections.

## Dataset/data pipeline

Phase 3 real-data collection is complete: 679 eligible samples (331 phishing, 348 benign) from
PhishTank/OpenPhish (phishing) and Tranco (benign), crawled for real HTML snapshots and split by
registered domain into train 408 (199/209), validation 135 (66/69) and test 136 (66/70), with zero
cross-split domain leakage and zero label conflicts (generated dataset card, v5; the dataset itself
is stored locally in `phishguard-phase3-pilot/`, not in this repository).

**The current `gnn_model_demo.pt` checkpoint was NOT trained on this dataset.** It was trained
earlier on the small original pilot: train=12 (8 phishing/4 benign), val=14, test=1 samples (see
`gnn_model_demo_metrics.json`). This is disclosed everywhere as far too small to support a
generalization claim. No model has been retrained or formally evaluated on the 679-sample dataset
yet.

## Testing

`tests/` covers: the API contract, the GNN/model functions, the two bug-fix regressions
(`test_dataset_loader_lexical.py`, `test_semantic_heuristic.py`), and the full Phase 3 dataset-
collection pipeline (crawling, feeds, sampling, persistence, redaction, etc.) inherited from
earlier phases. Current full suite: see `PROJECT_STATUS.md` for the exact pass count.

## Current limitations

- GNN trained on only 12 real labeled samples — no generalization claim is or should be made.
- No LLM is integrated; semantic analysis is a disclosed keyword heuristic.
- Fusion is an unweighted average, not a trained/tuned fusion model.
- DOM graph capped at 200 elements per page (large pages truncated, in document order).
- No formal accuracy/precision/recall/F1/ROC-AUC evaluation is claimed for this demo build — see
  `gnn_model_demo_metrics.json` for the raw, small-sample numbers, disclosed as demo-only.

## Future work

Retrain the GNN on the completed 679-sample dataset; integrate one real language model for
semantics; train an actual fusion model on held-out validation data; run a full, honest
evaluation (accuracy, precision, recall, F1, ROC-AUC, MCC, confusion matrix) on the held-out
domain-grouped test split; add GNNExplainer-based subgraph explanations.
