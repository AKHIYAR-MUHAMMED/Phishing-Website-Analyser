# CLAUDE.md — PhishGuard AI Implementation Briefing

> **Purpose of this file.** Context transfer for future Claude Code sessions working on this
> repository. It records what a read-only audit verified about the current code, and what the
> team has decided to aim for. It is **not** a description of working functionality.
>
> **Audit baseline:** commit `c2b3318` (branch `main`), audited 2026-09-27. If `HEAD` has moved
> since then, re-verify any fact below before relying on it.

---

## 0. How to read this document

Every statement is labelled with one of two tags:

- **[VERIFIED]** — confirmed during the audit by reading source code, inspecting committed data,
  or executing code. Sub-tags give the evidence source:
  `(code)` repository source · `(data)` committed dataset/files · `(run)` executed in a sandbox ·
  `(test)` test suite · `(cfg)` config/deployment files · `(doc)` project documentation.
- **[RECOMMENDATION]** — a proposed change. Not implemented. Requires team/guide agreement.

Anything marked **(not executed)** was verified by reading code only: PyTorch could not be
installed in the audit sandbox, so GNN/ViT forward passes were not run.

---

## 1. Project objective

**[VERIFIED] (doc)** Final-year B.Tech (AI & Data Science) project, Adi Shankara Institute of
Engineering & Technology, 2026-27.

- **Title:** PhishGuard AI — Multimodal Phishing Website Detection Using Graph Neural Networks
  (GNNs) and Large Language Models (LLMs).
- **Team:** Giridhar K A, Jose Michael A F, Shreyas M, Akhiyar Muhammed. **Guide:** Ms Aswathy.
- **Core objective:** jointly analyse webpage *structure* (DOM graph → GNN) and webpage
  *semantics* (text → language model), fuse them, classify phishing, explain the decision, and
  demonstrate a real-time prototype.
- **Documented evaluation:** Accuracy, Precision, Recall, F1, ROC-AUC, MCC, confusion matrix,
  cross-validation, comparison against conventional ML and DL baselines.
- **Documented tools:** Selenium/BeautifulSoup/Requests/Scrapy; PhishTank, OpenPhish, Tranco;
  NetworkX, PyTorch Geometric; GraphSAGE/GAT; LLaMA/Mistral/Gemma/BERT via Hugging Face;
  PyTorch fusion layer; scikit-learn; FastAPI/Flask; Docker.
- **Documented schedule:** Phase 3 (preprocessing, graph generation, trained GNN) ends
  2026-09-30; Phase 4 (LLM, fusion, training, XAI) 2026-10-01 → 10-31; Phase 5 (testing,
  evaluation, deployment, documentation) 2026-11-01 → 11-30.

**Priority rule:** a technically valid, reproducible, explainable system beats an impressive-
looking one. Do not add AI models to make the project look more advanced.

---

## 2. Intended architecture (from project documentation)

**[VERIFIED] (doc)**

```
1 Web crawling & data collection  (HTML, hyperlinks, screenshot, SSL metadata)
2 Feature extraction              (URL lexical, DOM, JavaScript, text)
3 Graph construction              (DOM tree + hyperlink network)
4 GNN structural learning         (GraphSAGE / GAT)          ┐ run in parallel
5 LLM semantic analysis           (open model via HF)        ┘
6 Multimodal feature fusion       (PyTorch fusion layer, intermediate/late)
7 Evaluation & optimisation       (CV, tuning, XAI)
8 Real-time detection prototype   (FastAPI/Flask + Docker)
```

The documents also mention screenshots, visual features (OpenCV) and SSL features as inputs.
See §15 for how that scope question should be handled.

---

## 3. Current repository architecture

**[VERIFIED] (code)** Map of what exists (not what works — see §4).

| Role | Files |
|---|---|
| Launcher | `run.py` → `uvicorn api:app` |
| API gateway (~40 routes) | `api.py` |
| Service wrappers (19 classes) | `services/*.py` |
| GNN | `gnn_model.py`, `train_gnn.py`, `gnn_model.pt` |
| "10-LLM" ensemble | `llm_ensemble.py` |
| Fusion | `multimodal_fusion.py` |
| Dataset | `dataset_loader.py`, `external_dataset_collector.py`, `data/*.csv`, `data/*.json`, `data/screenshots/*.png` |
| Other "models" | `vision_model.py`, `nlp_transformer.py`, `classical_ensemble.py`, `collectors.py` |
| Storage | `database.py`, `phishguard_x.db` (SQLite) |
| Auth / MLOps | `security.py`, `mlops_service.py` |
| Frontend | `dashboard/index.html`, `dashboard/app.js`, `dashboard/styles.css` |
| Tests | `tests/test_api.py`, `tests/test_models.py`, `run_tests.py` |
| Deployment | `Dockerfile`, `docker-compose.yml`, `k8s/deployment.yaml`, `prometheus.yml`, `.github/workflows/ci.yml` |
| Unrelated to this project | `generate_ppt.py`, `generate_cv_phishing_ppt.py`, `*_Presentation.pptx/.pdf` (about Jarczewski et al., MDPI 2026) |
| Duplicate | `read.me` is byte-identical to `README.md` |

### Actual execution path of a dashboard scan  **[VERIFIED] (code)**

1. `dashboard/app.js` POSTs `/api/v1/detect` with `{url, html_content: ''}` — **HTML is always empty**.
2. `services/crawler_service.py` **does not fetch the URL**. With empty HTML it returns a
   synthetic page `<html><head><title>{domain}</title></head><body><h1>Welcome to {domain}</h1></body></html>`
   and hard-coded headers (`nginx/1.18.0`).
3. `api.py::central_scan_pipeline` (L317–365) computes ~14 service outputs, then **discards them**
   and calls `FusionService.predict()`, which **recomputes everything** (LLM calls happen twice).
4. `multimodal_fusion.py::detect_url` fuses six scores with fixed weights, threshold 50.
5. On any backend error, `app.js` silently renders a client-side verdict (`renderFallbackResults`).

Endpoint inconsistency: `/models/fusion/predict` and `/api/v1/batch-scan` pass `""` directly to
fusion, which hits a *different* hard-coded fallback graph (form + password nodes,
`gnn_model.py` L36–43). `/api/v1/scan` uses the synthetic page instead.

---

## 4. Verified audit findings (summary)

**[VERIFIED]** unless stated.

- The dataset's non-URL features are random numbers drawn from **label-specific ranges** (data, code).
- The GNN is trained on a **fixed 15-node template graph**, not on webpage DOMs (code).
- The GNN's training features and inference features have **different meanings** (code).
- The crawler, WHOIS, DNS, SSL and threat-intel modules **fabricate outputs from URL keywords** (code, run).
- "ViT", "pHash/FAISS", "Phishpedia", "VisualPhishNet", "OCR", "BERT", "XGBoost/RF/CatBoost/LightGBM",
  "autoencoder/Isolation Forest" are **keyword rules or random tensors**; no real model is used (code).
- Only 5 of 10 "LLM engines" contain any API call; failures fall back **silently** to one shared
  keyword heuristic that is labelled as the model's output (code, run).
- Fusion is a **hand-weighted average**; no fusion model is trained (code).
- In practice **URL keyword matching determines the verdict**; the GNN cannot change it for typical
  keyword/non-keyword URLs (run, arithmetic from code weights).
- Reported metrics (100% accuracy/precision/recall/F1, ROC-AUC 1.000), confidence (≥95% floor),
  latency (14 ms), throughput (850 req/s), scan history and benchmark tables are **hard-coded** (code).
- Tests assert those hard-coded values; they provide **no evidence** the system works (test).
- `requirements.txt` omits `sqlalchemy`, `PyJWT` (`import jwt`), `python-multipart`, all imported
  at startup → Docker/CI will fail at import **(inference from imports; suite not executed)**.

---

## 5. GNN problems

### 5.1 Inference-time graph construction — `gnn_model.py::parse_dom_to_graph`  **[VERIFIED] (code)**

What it does (genuinely): parses HTML with BeautifulSoup, nodes = HTML elements, undirected
parent–child edges, 14-dim node features:
`[10-way tag one-hot | depth/25 | is_external | is_hidden | min(children,50)/50]`.

Problems:
- **L54–55** keeps only the first 200 elements in document order → `<head>` content crowds out body/forms.
- **L22–25, L80–83** `html` and `body` share one-hot index 0; `head`, `meta`, `span`, `button`,
  `label`, `p`, `select`, etc. all collapse to "unknown".
- **L94** `is_external` uses substring match (`target_domain not in link`) → `paypal.com.evil.net`
  counts as internal for `paypal.com`. Same bug in `dataset_loader.extract_dom_graph_features` L360, 367, 374.
- **L100** hidden check misses `display: none` (with a space) and CSS-class hiding.
- **L36–43** empty HTML returns a hard-coded 5-node graph containing form + password nodes.
- No hyperlink network, despite documentation requiring one.

### 5.2 GAT layer — `gnn_model.py::GraphAttentionLayer` (L131–172)  **[VERIFIED] (code)**

- Attention is exponentiated after subtracting a **global** max, but **never softmax-normalised
  per destination node** → not a valid GAT; sums scale with node degree.
- **No self-loops** → a node's own features are dropped from its update.
- Per-edge Python loop (slow; not batched).
- PyTorch Geometric is not used (documentation specifies PyG).

### 5.3 Training — `train_gnn.py`  **[VERIFIED] (code, data)**

- **L25–64** every sample → identical 15-node star: root, form, password input, text input,
  11 leaf nodes cycling `a/script/img/iframe/div`. **Every graph (phishing and legit) has a form and a password field.**
- Only three scalars vary per sample: `sfh_external`, `iframe_hidden`, `url_of_anchor_ratio` — all
  synthetic and label-conditional (see §6).
- A depth-1 decision stump on those three features scores **100% accuracy** on the full dataset,
  splitting at `url_of_anchor_ratio ≤ 0.425` (run). The GNN has no structural signal to learn.
- **L121–133** random 80/20 split (not stratified, not grouped by domain), no validation set,
  subsample 1000 train / 400 test, batch size 1, 5 epochs, no torch seed.
- 46 of 2,000 test URLs also appear in the training 80% (duplicate rows) (run).
- Metrics printed to stdout only; no evaluation artefacts committed.

### 5.4 Training vs inference mismatch  **[VERIFIED] (code)**

| Feature | Training | Inference |
|---|---|---|
| Topology | Fixed 15-node star | Real DOM tree, 1–200 nodes |
| Col 11 | Continuous anchor ratio copied onto 11 nodes | Binary per-node external flag |
| Col 12 | `iframe_hidden` on the form node | Per-node hidden flag |
| Col 10 | `n/15` | Real depth / 25 |
| Col 13 | Always 0 | Real child count / 50 |
| Form + password nodes | Always present | Present only if page has them |

### 5.5 Weights  **[VERIFIED] (code, data)**

`gnn_model.pt` (88 KB) is consistent with the model's ~21k parameters and is loaded by
`get_gnn_model()`. The weights are real but were trained on the template task above.
Because the dashboard always analyses the same synthetic page, the GNN score should be
**constant across dashboard scans** **(not executed; inferred from code)**.

---

## 6. Dataset problems

**[VERIFIED] (code: `dataset_loader.py` L408–579; data: `data/merged_phishing_multimodal_dataset.csv`; run)**

- Reads one CSV from a developer's Windows cache:
  `C:\Users\akhiy\.cache\kagglehub\datasets\taruntiwarihp\phishing-site-urls\versions\1\phishing_site_urls.csv`
  (columns `URL`, `Label` good/bad). **Not reproducible elsewhere.** If absent, generation falls
  back to 8 rows (L441–444).
- The "4 Kaggle sources" are names assigned to 4 samples of that **same** file. 118 URLs appear
  under more than one "source"; 135 duplicate rows; 9,865 unique URLs; 5,000/5,000 labels.
- **Only URL strings and labels are real.** All other columns are `np.random` from label-specific
  ranges (L472–573). Eight columns have **zero class overlap**: `url_of_anchor_ratio`,
  `request_url_ratio`, `dom_node_count`, `graph_avg_degree`, `vit_visual_threat_score`,
  `screenshot_phash_score`, `web_traffic`, `page_rank`.
- For legitimate rows, real lexical features are **overwritten with 0** (IP, shortener, @,
  double-slash, hyphen, subdomain, https-token, abnormal URL); `url_length_score` uses different
  thresholds per class.
- `ocr_detected_text` is templated from the label; brands assigned round-robin; `phash_vector_hex`
  derived from row index; `screenshot_path` = `D:\PRO\data\screenshots\*.png` (Windows paths to
  ~7 KB placeholder images).
- **No HTML is stored.** This dataset cannot train a DOM-graph model.
- `BENCHMARK_DATASETS`, `ScreenshotDatasetConnector` (L75–221): hard-coded metadata; the
  "102,070 connected screenshots" is a sum of literals; nothing is downloaded.
- `get_experimental_benchmark_table()` (L224–240) returns numbers copied from the MDPI 2026 paper
  (per its own docstring). **These are another paper's results, not this project's.**
- `external_dataset_collector.py` fetches three dataset *homepages* (HTTP 200 recorded in
  `data/external_collected_datasets.json`) and reports hard-coded sample counts; no data acquired.
- `data/phishguard_x_published_multimodal_dataset.csv` is an export of the same synthetic data.

**Consequence:** any metric computed on this dataset is invalid. Features are functions of the label.

---

## 7. LLM problems

**[VERIFIED] (code: `llm_ensemble.py`; run with no API keys)**

| Engine class | API call present? | Model ID in code | Key env var |
|---|---|---|---|
| OpenAI "GPT-5.5" | Yes | `OPENAI_MODEL` or `gpt-5.5-preview` | `OPENAI_API_KEY` |
| Anthropic "Claude 4 Opus" | Yes | `claude-4-opus-20260301` (hard-coded) | `ANTHROPIC_API_KEY` |
| Google "Gemini 2.5 Pro" | Yes | `gemini-2.5-pro` | `GEMINI_API_KEY` |
| DeepSeek-V3 | Yes | `deepseek-chat` | `DEEPSEEK_API_KEY` |
| Mistral Large | Yes | `mistral-large-latest` | `MISTRAL_API_KEY` |
| Llama 3.3 70B | **No** (reads key, never uses it) | — | `TOGETHER_API_KEY`/`GROQ_API_KEY` |
| Qwen 3 72B | **No** | — | — |
| Command A | **No** (reads key, never uses it) | — | `COHERE_API_KEY` |
| Falcon 180B | **No** | — | — |
| Phi-4 | **No** | — | — |

Model IDs were **not verified** against provider APIs.

- Any missing key, non-200 response, timeout (8 s) or parse error hits `except Exception: pass`
  and falls back to `evaluate_phishing_heuristics()` (L456–523). No logging.
- Fallback output is returned with `confidence: "HIGH"` and reasoning prefixed
  `[GPT-5.5 Analysis]` etc. The only difference from a real call is `[... API]` vs `[... Analysis]`.
- Engine "diversity" = `(sum(ord(name)) % 7 − 3) × 0.8` added to one shared heuristic (L515–516).
  With no keys: 100% agreement on every URL tested; scores differ by fixed 0.8 steps (run).
- Prompts differ per provider; only OpenAI receives lexical + GNN features; Gemini and Mistral
  receive only the URL. The LLM receives GNN outputs → **not an independent modality**.
- "Bayesian consensus" (L559–616) = reliability-weighted mean of temperature-scaled log-odds.
  No prior, no likelihood, no calibration code. Reliabilities (L545–556) and temperature 1.2 are
  literals. Each engine's `weight` attribute is unused. Verdict is a majority vote (≥5, L595),
  independent of the pooled score.
- Documentation specifies open-source models via Hugging Face; **none are used**.

**What may currently be claimed:** "client code for five commercial LLM APIs, untested in the
repository, with a rule-based fallback." Nothing more.

---

## 8. Multimodal fusion problems

**[VERIFIED] (code: `multimodal_fusion.py`; run)**

| Modality | Weight (L82–87) | What actually enters |
|---|---|---|
| GNN | 0.25 | Template-trained GNN probability |
| "10-LLM" | 0.25 | Keyword heuristic unless an API call succeeds |
| "ViT" | 0.20 | Keyword rules + URL-seeded random vector (`vision_model.py`) |
| "Classical ML" | 0.15 | Keyword → ~97.9 or ~0.2 (`classical_ensemble.py`) |
| "BERT" | 0.10 | Keyword → 96.8 or 0.8 (`nlp_transformer.py` L57–60) |
| Intel/WHOIS/SSL | 0.05 | Fabricated by keyword (`collectors.py`) |
| Anomaly | 0 | Computed and displayed, not fused |

- Weights are hand-set; no training; the 64-d graph embedding is returned but unused.
- Threshold fixed at 50.
- **L123** `confidence = min(100, max(95, …))` → confidence can never be below 95%.
- **L148** `scan_latency_ms: 14` is a literal.
- Keyword-driven 55% share alone: `http://paypal-account-update.com/login` → 53.8 (phishing
  regardless of GNN/ViT); `https://github.com/torvalds/linux` → 0.5 (legitimate even if GNN=ViT=100) (run).

**Conclusion:** not a learned multimodal model; manual averaging of mostly heuristic scores.

---

## 9. Dashboard / fabricated-output problems

**[VERIFIED] (code)**

Backend literals:
- `api.py` L403–412 `/api/v1/metrics`: 100.00% accuracy/precision/recall/F1, ROC-AUC 1.000, latency 14.
- `api.py` L392–401 `/dashboard/history`: literal two-row list, `total_scans: 120`.
- `api.py` L421–426 login issues a token for **any** credentials; no endpoint requires auth.
- `services/dataset_service.py` L42–48: "100.00%" metrics, "6,000/2,000/2,000" splits.
- `services/dashboard_service.py` L19: "850 req/sec"; `active_modalities: 9`.
- `mlops_service.py` L82–90: logs 100.0 for all metrics regardless of training result.
- `database.py` L103–127: seeds 8 fake scan results; real scans are never persisted.
- `security.py` L34: `verify_password` returns True for any `$2b$`-prefixed hash.
- `run.py` prints "SYSTEM HEALTH: 100% OPERATIONAL" unconditionally.

Frontend fabrication (`dashboard/app.js`):
- L108–125 + L653 `renderFallbackResults()`: on backend error, invents a verdict from
  `url.includes('paypal'|'login'|'verify'|'security')` without telling the user.
- L527 `getSample10LLMEngines()`: static fake engine results.
- L951 `renderFallbackScreenshotResults()`: fake screenshot analysis.
- L174, L178, L190, L193, L277, L936: default values (99.8, 99.1, 98.2 …) used when fields are missing.
- `index.html`: placeholder numbers (99.1%, 99.8%, 14 ms, 100.00% …) visible before any scan.
- Screenshot uploads are saved but never analysed (image path ignored downstream).

Genuinely computed (but from the heuristic pipeline): verdict, modality bars, GNN node/edge counts
of the synthetic page, LLM engine cards, `processing_latency_ms` on `/api/v1/scan` (real timing).
All nine frontend fetch URLs match existing backend routes.

---

## 10. Components to KEEP

**[RECOMMENDATION]** — preserve, possibly with minor edits.

| Component | Reason |
|---|---|
| `dataset_loader.extract_url_lexical_features` | Genuine, simple URL features (fix `abnormal_url` logic, which is effectively always 0) |
| FastAPI app skeleton in `api.py` | Working routing and static serving |
| Dashboard HTML/CSS shell | Reusable UI; content must change (see FIX) |
| `collectors.JavascriptASTParser` regex logic | Real signal from real HTML; rename honestly (not an AST) |
| OpenAI-style HTTP client pattern in `llm_ensemble.py` | Reusable request/JSON-parsing code if one API model is chosen |

---

## 11. Components to FIX

**[RECOMMENDATION]**

| Component | Required fixes |
|---|---|
| `gnn_model.parse_dom_to_graph` | Registered-domain comparison (e.g. `tldextract`); body-first or larger node cap with truncation recorded; richer tag vocabulary; attribute flags (input types, form action empty/external, `href` `#`/`javascript:`, hidden iframe); self-loops; remove the empty-HTML fake graph (return an explicit "no DOM" status) |
| `dataset_loader.extract_dom_graph_features` | Same domain-matching fix; remove invented `links_in_tags_ratio = 0.8 × request_url_ratio`; drop constant `popup_window`; drop `graph_avg_degree` (≈2 for any tree); remove constant defaults for empty HTML |
| `dashboard/app.js`, `index.html` | Remove all client-side fallback verdicts and default numbers; display backend errors and "modality unavailable" |
| `api.py` | One scan pipeline, no recomputation; remove literal endpoints |
| `requirements.txt` | Add missing deps; pin versions; add PyG, transformers, scikit-learn baselines as adopted |
| `database.py` | Remove seeded fake scans; optionally log real scans |
| `Dockerfile` | Works only once requirements are fixed |

---

## 12. Components to REBUILD

**[RECOMMENDATION]**

| Component | Rebuild as |
|---|---|
| `services/crawler_service.py` | Real fetcher: `requests` (+ optional Playwright/Selenium for rendering), timeouts, redirect handling, final URL, status code, crawl timestamp; explicit failure, never synthetic HTML |
| Dataset pipeline | Real crawled snapshots (see §15); manifest CSV; dedup; domain-grouped splits |
| `gnn_model.PhishingGNN` + layer | PyTorch Geometric `GATConv` or `SAGEConv`, 2–3 layers, global mean+max pooling, mini-batched |
| `train_gnn.py` | Train on real DOM graphs produced by the **same** featuriser used at inference; validation-based early stopping; seeds; saved metrics JSON |
| `llm_ensemble.py` | **One** semantic language-model component with explicit `status` (`ok`/`unavailable`/`error`) |
| `multimodal_fusion.py` | Trained fusion model; threshold tuned on validation |
| `classical_ensemble.py` | Honest baselines (e.g. Logistic Regression, Random Forest, XGBoost) trained on handcrafted features — required for the documented comparison |
| Explainability | GNNExplainer (PyG) subgraphs, feature importance for tabular features, LLM rationale explicitly labelled as generated text |
| `tests/` | Behavioural and evaluation tests (§17) |

---

## 13. Components to REMOVE — only after verification

**[RECOMMENDATION]** Removal requires, for each item: (1) `grep -rn` shows all references;
(2) references are replaced or removed in the same branch; (3) the app starts and tests pass;
(4) the team confirms. **Never delete in the same step as other refactors.** Prefer moving to
`legacy/` first if the team wants a record.

| Component | Why |
|---|---|
| `vision_model.py`, `services/vit_service.py`, `services/ocr_service.py`, `services/screenshot_service.py`, related `/models/vit`, `/phishpedia`, `/visualphishnet`, `/phash`, `/visual-hybrid`, `/eer-optimize`, `/screenshot/*` routes | Entirely simulated |
| `nlp_transformer.py`, `services/bert_service.py` | Untrained; output discarded; score is keyword-based |
| `AnomalyDetector` in `classical_ensemble.py` | Fabricated |
| `collectors.WHOISDNSCollector`, `SSLEvaluator`, `ThreatIntelAggregator`; `services/whois_service.py`, `dns_service.py`, `ssl_service.py` | Fabricated. Live lookups on historical URLs would also leak labels (dead phishing domains); blocklists would be a label oracle |
| `external_dataset_collector.py`, `ScreenshotDatasetConnector`, `BENCHMARK_DATASETS`, `get_experimental_benchmark_table`, `get_stratified_split` | Metadata theatre; another paper's numbers |
| `data/merged_phishing_multimodal_dataset.csv`, `data/phishguard_x_published_multimodal_dataset.csv`, `data/phishguard_x_dataset_metadata.json`, `data/external_collected_datasets.json`, `data/screenshots/*` | Synthetic/placeholder data (keep only if clearly archived as "synthetic, not used") |
| `gnn_model.pt` | Trained on template graphs; replace with new weights |
| `mlops_service.py`, `security.py`, auth route | No academic value; misleading |
| `k8s/`, `prometheus.yml`, Mongo/Redis/Postgres services in `docker-compose.yml`, `MockRedisCache` | Unused infrastructure |
| `generate_ppt.py`, `generate_cv_phishing_ppt.py`, `*_Presentation.pptx/.pdf` | Unrelated paper |
| `read.me` | Duplicate of README |
| `phishguard_x.db` | Seeded fake data; regenerate |

**Scope note:** the documents list screenshots/visual features. Removing the *simulated* vision code
is not the same as dropping visual scope. Raise with the guide; see §15.

---

## 14. Academic integrity rules

These rules are **mandatory** for all future work.

1. **No fabricated numbers.** Never write metrics, confidences, latencies, throughputs, dataset
   sizes or benchmark results as literals. Every reported number must be produced by code run on
   data, and be reproducible from a committed script + config + seed.
2. **No silent substitution.** If a model, API or data source is unavailable, return an explicit
   status (`unavailable`/`error`) and exclude it from fusion. Never replace it with a heuristic
   while labelling the output as the model's.
3. **Name things for what they are.** A regex is not an AST parser; a keyword rule is not a
   classifier; a weighted average is not Bayesian inference; one model is not an ensemble.
4. **Heuristics are allowed only if labelled as heuristics** in code, API output, UI and report.
5. **Other papers' results stay in the literature review**, cited, never in the system's output.
6. **Evaluation on held-out data only.** Test data is never used for training, threshold tuning,
   or model selection. Splits grouped by registered domain; duplicates removed first.
7. **No label leakage.** No feature may be derived from the label, from post-hoc blocklist
   membership, or from live lookups performed long after the URL was labelled.
8. **Report negative and weak results honestly**, including baselines that match or beat the fusion model.
9. **Document limitations**: dataset size/source/date, crawl failures, class balance, excluded modalities.
10. **Every team member must be able to explain every module that remains in the repo.**

---

## 15. Proposed final architecture

**[RECOMMENDATION]** — not implemented.

```
URL
 └─ Crawler (requests / optional headless browser; timeout; final URL; crawl timestamp)
     └─ Snapshot: HTML + visible text (+ SSL metadata, + optional screenshot for display)
         ├─ Shared featuriser (ONE module, used identically in training and inference)
         │   ├─ DOM graph ──► GNN (PyG GAT or GraphSAGE) ──► graph embedding (+ aux head)
         │   └─ URL lexical + HTML handcrafted features ──► tabular vector
         └─ Page text (title, visible text, form labels, URL)
               ──► ONE Hugging Face language model ──► text embedding (+ optional structured flags)
 Fusion MLP over [graph emb ‖ projected text emb ‖ tabular]  (trained; threshold tuned on validation)
   └─ Probability + explanations (GNNExplainer subgraph, feature importance, LLM rationale labelled as generated)
       └─ FastAPI /scan + dashboard (real values only, measured latency, explicit missing-modality states)
```

Design decisions to confirm with the guide:

- **Semantic branch.** Preferred: a frozen (optionally fine-tuned) transformer encoder producing a
  text embedding — reproducible, cheap, learnable in fusion; documentation permits BERT.
  Alternative: **one** open instruction LLM producing cached structured features (claimed brand,
  credential request, urgency cues, brand/domain mismatch) plus a rationale, with standalone
  zero-shot evaluation. Either way: one model, honestly described.
- **Data.** Phishing URLs from PhishTank/OpenPhish (crawled promptly, as they go offline fast);
  benign from Tranco **including login pages**, not only homepages, so the model can't learn
  "login page vs homepage". Deduplicate by HTML hash/phishing kit; split by registered domain.
- **Visual/SSL scope.** Capture SSL metadata and a screenshot at crawl time (cheap, genuine).
  Treat visual *modelling* as documented future work unless the guide requires it.
- **Crawling safety.** Isolated environment; never submit forms or credentials; timeouts; no
  execution of downloads; respect rate limits.

---

## 16. Phase-by-phase implementation roadmap

**[RECOMMENDATION]** Each phase: own branch → incremental commits → tests → **stop and report**.

| Phase | Goal | Key files | Exit criteria |
|---|---|---|---|
| **0. Reproducibility** | Environment runs anywhere | `requirements.txt`, `dataset_loader.py` (paths), seeds | Clean install on Linux; app imports; existing tests run (failures documented, not hidden) |
| **1. Honesty pass** | No fabricated values reach any output | `api.py`, `services/*`, `multimodal_fusion.py`, `mlops_service.py`, `database.py`, `dashboard/*` | `grep` finds no literal metrics/confidence/latency; UI shows errors/unavailable states; no client fallback verdicts |
| **2. Crawler + data collection** | Real HTML snapshots with manifest | new `crawler/`, `data/raw/`, manifest CSV | N phishing + N benign snapshots collected; failures logged; dataset card written (source, date, counts) |
| **3. Shared featuriser** | One graph + tabular featuriser | `features/` (from `parse_dom_to_graph`, `extract_*`) | Unit tests on fixture HTML; identical output in train/infer code paths |
| **4. Splits + baselines** | Honest reference numbers | `splits/`, `baselines/` | Domain-grouped train/val/test; dedup verified; LR/RF/XGBoost metrics saved as JSON |
| **5. GNN** | PyG GNN on real DOM graphs | `gnn/`, `train_gnn.py` | Val-based early stopping; ≥3 seeds; metrics JSON; weights versioned |
| **6. Semantic branch** | One language model | `semantic/` | Standalone evaluation; explicit status handling; cached outputs |
| **7. Fusion** | Learned fusion | `fusion/` | Trained on train, tuned on val, tested once on test; ablations (each branch alone, pairs, all) |
| **8. Explainability** | Real explanations | `explain/` | GNNExplainer subgraphs + feature importance + labelled rationale for sample cases |
| **9. Prototype integration** | API + dashboard on new pipeline | `api.py`, `dashboard/` | Single pipeline; measured latency; real scan logging; Docker builds |
| **10. Evaluation + documentation** | Report-ready results | `eval/`, `README.md`, `docs/` | Accuracy/Precision/Recall/F1/ROC-AUC/MCC/confusion matrix, mean ± std over seeds; error analysis; limitations; README matches reality |

Timeline mapping (from documentation): Phases 0–3 ≈ late Sep–mid Oct; 4–7 ≈ October (Phase 4 of
the academic plan); 8–10 ≈ November (Phase 5).

---

## 17. Testing requirements

**[RECOMMENDATION]** The current test suite asserts hard-coded values and must not be treated
as evidence. New tests should cover:

1. **Featuriser unit tests** on committed fixture HTML: node count, edge count, tag mapping,
   external-link detection (including `paypal.com.evil.net`), hidden-element detection.
2. **Train/inference consistency:** the same HTML yields identical tensors via the training path
   and the inference path.
3. **Leakage tests:** no URL, registered domain or HTML hash appears in more than one split;
   no feature column is a deterministic function of the label.
4. **No-literal-outputs test:** assert API responses never contain fixed metric/confidence/latency
   values (e.g. patch the model and confirm outputs change accordingly).
5. **Unavailable-modality tests:** with API keys removed / model missing, the response reports
   `status: unavailable` and fusion excludes it; no heuristic is labelled as a model.
6. **Crawler tests** with a local test server: timeouts, redirects, non-HTML, 404, empty body.
7. **API contract tests** for `/scan`: schema, error codes, latency field is measured.
8. **Evaluation reproducibility:** `eval` script regenerates committed metrics JSON within tolerance from saved weights + seed.
9. Tests must not write into `data/` or other tracked directories (use temp dirs).

Run the full suite after every phase and include the result in the phase report.

---

## 18. Rules for Claude Code

1. **Never modify `main` directly.** Create a branch per phase (e.g. `phase-1-honesty-pass`).
   Never force-push. Never commit or push unless the user explicitly asks.
2. **Never fabricate metrics.** No literal accuracy, precision, recall, F1, ROC-AUC, MCC,
   confidence, latency, throughput or dataset counts — in code, UI, tests, docs or commit messages.
   If a number isn't produced by a run, write "not yet evaluated".
3. **Never silently substitute heuristics for model outputs.** Unavailable → explicit status.
4. **Preserve useful existing code** (§10, §11). Refactor before rewriting; justify any rewrite.
5. **Work incrementally.** Small, reviewable commits; one concern per commit.
6. **Test after each phase** (§17). Do not proceed on a failing suite without reporting it.
7. **Stop and report after each major phase** with: what changed (files), what was verified and
   how, test results, open problems, and what the next phase needs. Wait for approval.
8. **Deletions** follow §13 verification steps and require explicit user approval.
9. **Distinguish facts from assumptions** in every report, as this file does.
10. **Do not add new AI models or services** beyond §15 without explicit approval.
11. **Secrets:** never commit API keys; read from environment; document required variables.
12. **Crawling safety:** isolated environment, no form submission, timeouts, polite rate limits.
13. **Re-verify before relying on this file** if `git log` shows commits after `c2b3318`.

---

*This is a context-transfer document. The roadmap has not been started. Update the audit
baseline and the relevant sections whenever a phase is completed.*
