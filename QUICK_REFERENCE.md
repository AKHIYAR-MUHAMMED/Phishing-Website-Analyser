# PhishGuard AI — Quick Reference (keep open during presentation)

### START COMMAND
```bash
python -m uvicorn api:app --host 127.0.0.1 --port 8000
```
Wait for `Application startup complete.`

### DEMO URL
```
http://localhost:8000/demo
```
(not `/` — that's the old legacy dashboard)

### MAIN PIPELINE
URL → real crawl → URL features + DOM→graph→GNN + semantic heuristic → unweighted-mean fusion
→ verdict + evidence → dashboard

### KEY TERMS
- **Fused Threat Signal** — not a probability. Unweighted average of 3 real component scores.
- **GNN** — 2-layer Graph Attention Network, trained on 12 real samples.
- **Semantic heuristic** — disclosed keyword scanner, NOT an LLM (none configured).
- **Fusion** — plain average, not a trained model.

### WHAT GNN DOES
Parses real HTML into a graph (element = node, parent-child = edge, capped at 200 nodes), runs
a 2-layer GAT network, outputs a real structural threat score.

### WHAT SEMANTIC ANALYSIS DOES
Scans the page's real visible text/title for credential/urgency/brand keywords with
word-boundary matching. Rule-based, deterministic, disclosed as a heuristic.

### WHAT FUSION DOES
Averages whatever components actually produced a score. Verdict = "phishing" if average ≥ 0.5.

### KEY LIMITATIONS
- Only 12 real training samples — no generalization claim
- No LLM integrated
- Fusion not trained
- DOM graph capped at 200 elements/page

### COMMON VIVA ANSWERS
- *Why GNN?* → HTML is a tree; GNN preserves structure a flat vector would lose.
- *Why not claim high accuracy?* → 12 samples is statistically too small; we disclose this
  everywhere rather than inflate it.
- *Is this production-ready?* → No — explicitly a research prototype, disclosed as such in the
  UI itself.
- *What dataset?* → Real PhishTank/OpenPhish (phishing) + Tranco (benign), real crawled HTML.

### TROUBLESHOOTING COMMANDS
```powershell
# is backend alive?
# open in browser: http://localhost:8000/api/v1/health

# is port 8000 busy?
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue

# reinstall deps if an import fails
pip install -r requirements.txt
```
Full detail: `TROUBLESHOOTING.md`. Full walkthrough: `DEMO_GUIDE.md`. Full script:
`DEMO_SCRIPT.md`. Full Q&A: `VIVA_QA.md`.
