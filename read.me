# PhishGuard AI: Multimodal Phishing Website Detection (GNN + Language Models) — work in progress

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100.0%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0%2B-EE4C2C.svg)](https://pytorch.org/)

> **Project status: research prototype under active rebuild — not a working detector.**
> A code audit (see [`CLAUDE.md`](CLAUDE.md)) found that most components described in the original
> README were simulated: keyword rules, random tensors, hard-coded metrics and fabricated lookups.
> Those components have been disabled and now report an explicit `unavailable` status (HTTP 501 on
> their endpoints). **No model is trained or evaluated in this branch, so no accuracy, precision,
> recall, F1, ROC-AUC or any other performance figure is claimed, and scans return no verdict.**
> Nothing below should be read as a description of working detection capability.

## Project goal

Final-year B.Tech (AI & Data Science) project, Adi Shankara Institute of Engineering & Technology,
2026-27. The target design is to analyse a webpage's **structure** (DOM graph → graph neural network)
and **semantics** (page text → one language model), fuse the two, classify the page as phishing or
not, and explain the decision, served through a real-time FastAPI prototype. This is the *intended*
architecture; most of it is not built yet. See [`CLAUDE.md`](CLAUDE.md) for the audit findings, the
integrity rules the project follows, and the phase-by-phase roadmap.

## What is actually implemented in this branch (Phases 0–2)

| Component | Status | What it really does |
| :--- | :--- | :--- |
| Web crawler (`crawler/`) | **Implemented** | Real asynchronous HTTP **GET-only** fetch of the requested URL. Defaults: 8 s timeout, at most 5 redirects, 2 MB response cap (`config.py`, overridable by environment variables). Every outcome has an explicit status (`ok`, `timeout`, `connection_error`, `ssl_error`, `too_many_redirects`, `content_too_large`, `invalid_url`, ...). Never submits forms or credentials. |
| URL lexical features | **Implemented** | Simple deterministic features computed from the URL string. |
| DOM graph construction | **Implemented (statistics only)** | Parses crawled HTML with BeautifulSoup into a graph and reports node/edge/density statistics. Capped at the first 200 elements; known limitations are listed in `CLAUDE.md` section 5.1. |
| JavaScript regex indicators | **Heuristic** | Regex pattern counts over the HTML. Not an AST parser and not a classifier. |
| Component status registry (`component_status.py`) | **Implemented** | Single source of truth for the honest status of every component, shown by the API and the dashboard. |
| FastAPI service + dashboard | **Implemented** | Serves the endpoints below and a status/diagnostics dashboard. Shows only values returned by the backend; backend errors are displayed, never replaced by a fabricated result. |

### Crawler scope — what it does *not* do

The scan crawler (`crawler/fetcher.py`, used by `/api/v1/scan`) is intended for a single,
human-initiated, on-demand scan of one URL. It **does not read or honour `robots.txt`**, applies
**no crawl-delay or rate limiting**, does not render JavaScript, and does not collect screenshots or
SSL certificate metadata. It would need robots handling and rate limiting before any unattended or
bulk use.

The Phase 3 dataset collector (`dataset/`, run separately from the scan API) behaves differently,
within these stated limits:

- It checks `robots.txt` for the **source host** of each URL before fetching (`dataset/robots.py`).
  Redirect-target hosts are not checked, a `Crawl-delay` directive is not honoured, and if
  `robots.txt` cannot be retrieved (timeout or an HTTP error) the fetch proceeds ("fail-open").
- It rate-limits per hostname, not per hosting provider (`dataset/orchestrator.py`; defaults: 5
  concurrent requests and a 2.0 s minimum gap between request starts to the same host, configurable
  in `config.py`).
- It records TLS certificate metadata through a separate probe (`dataset/tls_probe.py`) that
  deliberately does not validate certificates.
- It issues GET requests only, and does not render JavaScript or collect screenshots.

## What is NOT implemented (reported as `unavailable` / HTTP 501)

- **GNN inference.** `gnn_model.pt` was trained on a fixed synthetic template graph, not on real
  webpage DOMs, so its output is not a valid phishing probability and is not used. Retraining on
  real data is future work.
- **LLM / language-model semantic analysis in the scan pipeline.** No language model takes part in
  a scan. `llm_ensemble.py` lists 10 engines, but only 5 (OpenAI, Anthropic, Google, DeepSeek,
  Mistral) have any client code, and that code needs the matching API key, is untested in this
  repository, and uses unverified model IDs. The other 5 (Llama, Qwen, Cohere Command A, Falcon,
  Phi-4) have no implementation. The `/models/llm/*` endpoints query each engine individually and
  report that engine's own result or an explicit `unavailable` / not-implemented status. **No
  consensus is computed** (the aggregate is reported as `unavailable`), and the previous "10-LLM
  Bayesian consensus" — a shared keyword heuristic with a plain weighted mean — has been removed.
- **Multimodal fusion.** No fusion model exists, so no verdict or probability is produced.
- **Visual analysis** (screenshots, ViT, Phishpedia, VisualPhishNet, pHash/FAISS, OCR), **BERT**,
  **classical ML baselines**, **anomaly detection**, **WHOIS/DNS**, **SSL/TLS inspection** and
  **threat-intelligence** lookups: the old implementations were simulated and are disabled.
- **Explainability, scan history, authentication** and **dataset export/benchmark** endpoints.
- **Evaluation.** No model has been evaluated on real held-out data.
- **Dataset.** The committed CSV files under `data/` contain label-conditional random features and
  **must not be used for training or evaluation** (`CLAUDE.md` section 6). The Phase 3 collection
  pipeline exists in `dataset/` (code only; design in `PHASE3_DATASET_PLAN.md`), but **no collected
  data is stored in this repository**: the capture manifest, HTML snapshots, selection files, split
  lists and feed digests are generated locally and are kept out of Git (see `.gitignore`).

The legacy simulated modules (`vision_model.py`, `nlp_transformer.py`, `classical_ensemble.py`,
`collectors.py`, `mlops_service.py`, `security.py`, ...) are still present in the repository pending
a reviewed removal (`CLAUDE.md` section 13); they are not part of the working pipeline.

## Target architecture (design intent, not current behaviour)

```
URL -> crawler -> HTML + visible text
        |-> DOM graph -> GNN ----------\
        |-> URL / HTML features --------+-> fusion (to be trained) -> verdict + explanation
        '-> page text -> language model /
```

Only the crawler and the feature/graph-construction steps exist today. The GNN, language-model,
fusion and explanation stages are future work.

## Repository structure

```
api.py                  FastAPI gateway (real scan route; disabled components return HTTP 501)
run.py                  Launcher: prints the real component status, then starts the API
component_status.py     Honest status registry for every component
config.py               Environment-driven configuration (crawler limits, paths)
crawler/                Real GET-only HTTP crawler
services/               Thin service wrappers around the modules above
dashboard/              Status / diagnostics web interface
tests/                  Behaviour tests incl. no-fabrication and crawler tests (local test server)
data/                   Legacy SYNTHETIC CSV/JSON files — do not use for training or evaluation
CLAUDE.md               Audit findings, integrity rules, roadmap
```

## Quick start

Prerequisites: Python 3.10–3.12.

```bash
python -m venv venv
# Windows: venv\Scripts\activate      Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
python run.py
```

`run.py` prints the status of every component, then starts the server on the first free port from
8000 upward (it prints the exact URLs):

- Dashboard: `http://127.0.0.1:8000`
- API docs (Swagger): `http://127.0.0.1:8000/docs`

## API overview

| Method | Endpoint | Behaviour in this branch |
| :--- | :--- | :--- |
| `POST` | `/api/v1/scan` (aliases `/api/v1/detect`, `/models/fusion/predict`) | Runs the scan pipeline once. With no `html_content` supplied it **live-crawls** the URL. Returns the crawl result, URL features, DOM statistics and per-component statuses. **Returns no verdict.** |
| `POST` | `/api/v1/batch-scan` | Same pipeline for up to 10 URLs. No verdicts. |
| `POST` | `/models/gnn/predict` | DOM graph statistics only; the GNN output itself is unavailable. |
| `GET`/`POST` | `/models/llm/*` | Lists the engines and their real configuration state; POST queries each engine that has a client and an API key and returns that engine's own status/result. No consensus is computed and the output is not part of a scan. |
| `GET` | `/api/v1/dashboard`, `/api/v1/model_info`, ... | Component status registry. |
| `GET` | `/api/v1/metrics` | `not_evaluated` — no metrics exist. |
| `GET` | `/api/v1/health` | Reports only that the API process is running. |
| any | vision / BERT / ensemble / autoencoder / XAI / benchmark / dataset-export / screenshot / auth routes | **HTTP 501** with the reason the component is disabled. |

Example request:

```json
POST /api/v1/scan
Content-Type: application/json

{ "url": "https://example.com" }
```

## Testing

```bash
pytest tests/ --doctest-modules
```

The suite includes behaviour tests, crawler tests that run only against a local test server (an
autouse fixture blocks all other hosts), and `tests/test_no_fabrication.py`, which checks that
fabricated metrics, confidence floors and literal latencies do not reach any API output. Passing
tests show that the application imports and behaves as documented; they are **not** evidence of
detection accuracy.

## Deployment files

A `Dockerfile`, `docker-compose.yml` and Kubernetes manifest are included but are unreviewed
carry-overs: `docker-compose.yml` lists PostgreSQL, MongoDB, Redis and Prometheus services that the
current code does not use, and the Kubernetes manifest is untested. Treat deployment as not yet
supported.

## Background literature

The visual-phishing and target-recognition approaches mentioned in earlier drafts come from
Jarczewski, Białczak and Mazurczyk, *Phishing Website Impersonation: Comparative Analysis of
Detection and Target Recognition Methods*, MDPI Applied Sciences, 2026. Those are **that paper's
results**, not this project's, and none are reproduced or claimed here.

## License

The repository includes an MIT `LICENSE` file; its copyright holders, year and wording are still
pending confirmation by the team. The licence covers this project's code. Third-party data collected
by the Phase 3 pipeline (PhishTank, OpenPhish, Tranco) remains subject to its sources' own terms and
is not redistributed here.
