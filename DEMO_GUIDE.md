# PhishGuard AI — Demo Guide

Practical, step-by-step guide to run and present the live demo. Based on the verified
`demo-sprint` branch state (commit `c9e3340`, working tree with two additional bug fixes — see
`PROJECT_STATUS.md`).

---

## 1. Prerequisites

- Windows machine with Python already set up for this project (the environment used throughout
  development — no new installs needed if you have run this project before).
- Working directory: `E:\Final Project\Phishing-Website-Analyser`
- Internet connection (the demo performs a real live HTTP fetch of whatever URL you enter).
- Dependencies from `requirements.txt` already installed (torch, fastapi, uvicorn, httpx,
  beautifulsoup4, etc.) — nothing to install fresh if the environment is unchanged.

---

## 2. Start the backend/API

Open a terminal in `E:\Final Project\Phishing-Website-Analyser` and run:

```bash
python -m uvicorn api:app --host 127.0.0.1 --port 8000
```

Wait for this line before doing anything else:

```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

Leave this terminal window open for the entire presentation — closing it stops the server.

---

## 3. Open the demo

In a browser, go to:

```
http://localhost:8000/demo
```

(Not `http://localhost:8000/` — that is the older legacy dashboard, not the honest demo. Always
use `/demo`.)

---

## 4. Step-by-step demonstration flow

1. **Point out the status strip at the top** before scanning anything:
   `GNN: Active — real forward pass` / `Semantic: Heuristic engine` / `LLM: Not configured` /
   `Fusion: Unweighted, untrained`. Say this out loud — it is the project's own honesty
   disclosure, visible before any scan runs.
2. **Type a URL** into the input box, e.g. `https://github.com`, or click one of the "Quick
   demo" chips (these only fill the box — you still click Analyze to run a real scan).
3. **Click Analyze.** Point out the 7-stage pipeline timeline lighting up in order: Website
   Crawl → URL/HTML Processing → DOM Graph Construction → GNN Inference → Semantic Analysis →
   Fusion → Result. Each stage only marks complete when the real backend response for it has
   actually returned — nothing here is pre-timed or animated independently of the real request.
4. **Read the verdict card**: Benign/Phishing, risk tier, and the Fused Threat Signal percentage.
   Explicitly say this is **not** a "probability" — it is an unweighted average of three real
   component scores, and say so if asked.
5. **Walk through the three Signal Component cards**: URL Analysis, DOM/GNN, Semantic. Each
   shows its own real score and real evidence (e.g. flagged lexical features, node/edge counts,
   matched keyword terms).
6. **Show the DOM Graph Structure preview.** Explicitly say it is an *illustrative* layout
   generated deterministically from the real node/edge/density counts for this scan — not a
   literal reconstruction of the actual DOM tree, because the API returns aggregate graph
   statistics, not a full per-node structure.
7. **Show the Multimodal Fusion panel** — the per-component percentages and the fused result,
   with the "unweighted mean, not a trained fusion model" note visible.
8. **Open "Why This Result?"** — the evidence grouped by modality (URL / DOM-GNN / Semantic).
9. **Open "Model & Dataset Transparency"** (collapsible) — this states plainly that the GNN was
   trained on N=12 real samples, that this is too small to claim generalization, and that no LLM
   is configured.
10. **Open "Technical Details"** (collapsible) — the full raw JSON API response, for anyone who
    wants to see exactly what the backend actually returned.
11. **Run a second URL** (e.g. one you know locally, or `https://posototo.ink`) to show the
    output genuinely changes with real input — different node/edge counts, different scores,
    different evidence.

---

## 5. What can be demonstrated

Any real, publicly reachable URL. Two known-good examples already exercised in this project:
- `https://github.com` — real large page, low risk score
- `https://posototo.ink` — a real site from the Phase 3 pilot dataset, higher risk score

Avoid URLs that are offline or blocked by the crawler's timeout — see `TROUBLESHOOTING.md`.

---

## 6. What happens internally when Analyze is clicked

1. The browser sends the URL to `POST /api/v2/analyze`.
2. `crawler.fetcher.fetch_url()` makes a real HTTP GET request (8s timeout, 2 MB content cap,
   follows up to 5 redirects), returning the final URL, HTTP status, raw HTML, and extracted
   title/visible text — or an explicit error if the fetch fails.
3. `dataset_loader.extract_url_lexical_features()` computes real URL-string features (IP-address
   check, URL length, known-shortener hostname match, `@` symbol, hyphen in domain, subdomain
   count, https-token, etc.) from the URL string alone.
4. `gnn_model.parse_dom_to_graph()` parses the real HTML with BeautifulSoup into a graph: one
   node per HTML element (capped at 200, in document order), parent-child edges, and a 14-
   dimension feature vector per node (tag type, depth, external-link flag, hidden flag, child
   count).
5. That graph is passed through `PhishingGNN` (a 2-layer Graph Attention Network), loaded from
   `gnn_model_demo.pt` — real weights, trained on N=12 real webpage graphs from the Phase 3
   pilot dataset — producing a real forward-pass probability.
6. `semantic_heuristic.analyze_text_heuristically()` scans the page's real title and visible text
   for credential/urgency/brand keyword terms (word-boundary matched) — a disclosed rule-based
   heuristic, explicitly not an LLM, since no LLM API key is configured in this environment.
7. The three component scores (URL, GNN, semantic) that actually ran are averaged (unweighted
   mean) into a fused score; verdict is "phishing" if the fused score is ≥ 0.5, else "benign".
8. The full result (crawl info, every component's real evidence, fusion breakdown, verdict) is
   returned as JSON and rendered by `dashboard/demo.html`.

---

## 7. How to stop the server

In the terminal running uvicorn, press `Ctrl+C`. Confirm it stopped with:

```powershell
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
```

No output means the port is free.

---

## 8. Basic troubleshooting

See `TROUBLESHOOTING.md` for the full list. Quickest checks:
- Backend alive: open `http://localhost:8000/api/v1/health` — should return `{"status":"ok"}`.
- `/demo` blank or errors: check the uvicorn terminal for a traceback.
- Analyze does nothing: check the browser console (F12) for a network error; check the target
  URL is reachable from this machine.
