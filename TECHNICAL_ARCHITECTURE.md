# PhishGuard AI — Technical Architecture

Reflects the actual current `demo-sprint` implementation only (see `PROJECT_STATUS.md`).

---

## Diagram

```
                              URL (user input)
                                    |
                                    v
                    ┌───────────────────────────────┐
                    │  crawler.fetcher.fetch_url()   │
                    │  real async HTTP GET (httpx)   │
                    │  8s timeout, 5 redirects max,  │
                    │  2MB content cap               │
                    └───────────────┬────────────────┘
                                    |
                 status != "ok"?  --+--  status == "ok"
                     |                        |
                     v                        v
              verdict: "unavailable"   HTML + title + visible_text
              (crawl failed; stop)             |
                                                v
              ┌─────────────────────────────────────────────────────────┐
              │                    PARALLEL FEATURE PATHS                │
              │                                                          │
              │  ┌─────────────────────┐   ┌───────────────────────┐    │
              │  │ URL lexical features │   │  DOM -> Graph -> GNN   │    │
              │  │ dataset_loader.py    │   │  gnn_model.py          │    │
              │  │ (URL string only)    │   │  parse_dom_to_graph()  │    │
              │  └──────────┬───────────┘   │  -> PhishingGNN (GAT)  │    │
              │             |               │  gnn_model_demo.pt     │    │
              │             |               │  (trained on N=12 real │    │
              │             |               │   samples)             │    │
              │             |               └───────────┬────────────┘    │
              │             |                            |                │
              │             |          ┌─────────────────────────────┐   │
              │             |          │  Semantic heuristic          │   │
              │             |          │  semantic_heuristic.py       │   │
              │             |          │  keyword scan over real text │   │
              │             |          │  (NOT an LLM — none          │   │
              │             |          │   configured)                │   │
              │             |          └───────────────┬───────────────┘   │
              └─────────────┼──────────────────────────┼───────────────────┘
                             |                          |
                             v                          v
                    ┌─────────────────────────────────────────┐
                    │   Fusion (analysis_pipeline.py)          │
                    │   unweighted mean of whichever            │
                    │   components actually produced a score    │
                    │   (never a trained fusion model)           │
                    └───────────────────┬───────────────────────┘
                                        |
                                        v
                          Verdict: "phishing" if fused >= 0.5
                                   else "benign"
                                        |
                                        v
                    ┌─────────────────────────────────────────┐
                    │  Response JSON (POST /api/v2/analyze)    │
                    │  crawl info + every component's real     │
                    │  evidence + fusion breakdown + verdict    │
                    └───────────────────┬───────────────────────┘
                                        |
                                        v
                    ┌─────────────────────────────────────────┐
                    │  dashboard/demo.html  (GET /demo)         │
                    │  pipeline timeline, verdict card,         │
                    │  3 signal cards, DOM graph preview,        │
                    │  fusion panel, evidence panel,             │
                    │  transparency + raw JSON sections          │
                    └─────────────────────────────────────────┘
```

---

## Stage-by-stage explanation

**1. URL input.** Entered by the user in the dashboard, or via `POST /api/v2/analyze`
directly (`{"url": "..."}`).

**2. Crawl (`crawler/fetcher.py`).** A real, single HTTP GET request. On any transport-level
failure (timeout, connection error, TLS error, too-many-redirects, oversized body, invalid URL),
the pipeline stops immediately and reports `verdict: "unavailable"` with the specific
`error_type` — it never substitutes a fake page.

**3a. URL lexical features (`dataset_loader.py`).** Computed from the URL string alone, so this
path runs even if the crawl fails a later step but not this one; in practice it always runs once
`fetch_url` returns "ok". Includes IP-as-host check, URL length, shortener-hostname match,
`@`-symbol, double-slash position, hyphen-in-domain, subdomain count, https-token, abnormal-URL
check.

**3b. DOM graph construction + GNN inference (`gnn_model.py`).** The real HTML is parsed into a
graph (one node per HTML element, capped at 200 in document order; 14-dim features per node;
parent-child edges). That graph is passed through a 2-layer Graph Attention Network
(`PhishingGNN`), which pools node embeddings (mean + max) into a single graph embedding, then a
small classifier head produces a sigmoid probability. If the GNN weights file is missing or
fails to load, this component reports `status: "unavailable"` and is excluded from fusion.

**3c. Semantic heuristic (`semantic_heuristic.py`).** The real extracted page title and visible
text are scanned for credential/urgency/brand keyword terms and login-form language, using
word-boundary regex matching. Always returns `status: "heuristic"` — never mislabeled as an LLM
result, since no LLM API key is configured in this environment.

**4. Fusion (`analysis_pipeline.py`).** Builds a list of only the components that actually
produced a score, and takes their plain unweighted mean. No trained fusion model exists yet;
this is explicitly disclosed in both the API response and the dashboard.

**5. Verdict.** `"phishing"` if the fused score is ≥ 0.5, otherwise `"benign"`. Always
accompanied by `verdict_confidence_caveat` explaining this is not a calibrated probability.

**6. Response / Dashboard.** The full JSON — crawl metadata, every component's real evidence,
the fusion breakdown, and the verdict — is returned to the client and rendered by
`dashboard/demo.html`, including a collapsible raw-JSON view for full transparency.

---

## Explicit non-goals of this diagram

Legacy routes/services described in `CLAUDE.md` (`/api/v1/*`, `/models/*`, the "10-LLM
ensemble", ViT/screenshot/WHOIS/DNS/SSL modules) are **not** part of this pipeline and are not
shown above — they belong to the earlier, pre-honesty-pass system and are out of scope for this
demo.
