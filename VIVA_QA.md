# PhishGuard AI — Viva / Examiner Q&A

Concise answers grounded in the actual current implementation. Where a number is genuinely
small or weak, the answer says so — do not upgrade these answers with invented confidence.

---

**Q: Why phishing detection?**
A: Phishing sites imitate real login/payment pages to steal credentials, and URL-only detection
is cheap to evade. Combining URL, page structure, and page text raises the cost of evasion and
gives explainable evidence, not just a verdict.

**Q: Why multimodal?**
A: Each signal alone is weak on its own — a clean URL can host a phishing page, and structure
alone can't read intent. Combining URL, DOM-graph structure, and semantic text gives independent
evidence; the current fusion is a simple average, but the architecture supports adding a trained
fusion model over these same components later.

**Q: Why GNN?**
A: An HTML page is naturally a tree/graph, not a flat feature vector. A GNN can learn from
relationships between elements (e.g. a password field's position relative to a form) that a
plain feed-forward network flattening the page into a vector would lose.

**Q: Why represent HTML as a graph?**
A: Every HTML element is a node; parent-child DOM relationships are edges. This preserves the
page's real nested structure instead of discarding it into an unordered feature list.

**Q: What are nodes and edges?**
A: Nodes = individual HTML elements (tag type, depth, external-link flag, hidden flag, child
count encoded as a 14-dim feature vector). Edges = bidirectional parent-child relationships
between elements, exactly as they appear in the real parsed DOM.

**Q: Why not use a normal neural network?**
A: A standard feed-forward network needs a fixed-size input vector, which forces you to
flatten or summarize the DOM's tree structure, losing structural information. A GNN operates
directly on the graph, preserving relationships between elements.

**Q: What does the semantic component do?**
A: It's a disclosed, deterministic rule-based keyword scanner (`semantic_heuristic.py`) over the
page's real visible text and title — checking for credential terms, urgency terms, brand names,
and login-form language, with word-boundary matching. It is explicitly not an LLM; no LLM API
key is configured in this environment, so we disclose the heuristic honestly instead of faking
a language-model response.

**Q: How does URL analysis work?**
A: Pure string analysis of the URL itself — IP-as-hostname check, URL length, known-shortener
hostname match, `@` symbol, double-slash position, hyphen-in-domain, subdomain count,
https-token presence, abnormal-URL check. No network request needed for this part.

**Q: What is fusion?**
A: Combining the scores from the components that actually ran into one result. Currently an
unweighted mean — explicitly not a trained fusion model, and explicitly not a calibrated
probability. This is disclosed in both the API response and the dashboard.

**Q: How is the website crawled?**
A: A real single async HTTP GET request (`crawler/fetcher.py`, using httpx), with an 8-second
timeout, up to 5 redirects followed, and a 2 MB content cap. Any transport-level failure returns
an explicit error status; nothing is faked if the crawl fails.

**Q: What dataset is used?**
A: A real Phase 3 dataset collected from PhishTank and OpenPhish (phishing URLs) and Tranco
(benign URLs), with real crawled HTML snapshots: 679 eligible samples recorded on the generated
card (331 phishing / 348 benign; 678 integrity-verified after a later re-check), split by registered domain into train 408 / validation 135 / test 136, with zero
cross-split domain leakage and zero label conflicts (per the generated dataset card, v5). The GNN
checkpoint currently in use was NOT trained on this dataset — it was trained earlier on the small
original pilot: 12 samples for training (8 phishing / 4 benign), 14 for validation, 1 for test.

**Q: How were phishing and benign samples obtained?**
A: Phishing URLs from PhishTank/OpenPhish live feeds; benign URLs from the Tranco top-sites
list. Each was crawled for real with the same fetcher used at inference time, so training and
inference use identical feature extraction.

**Q: What are the evaluation metrics?**
A: No formal accuracy/precision/recall/F1/ROC-AUC claim is made for this demo. The raw
train/val/test metrics for the current tiny sample are recorded in
`gnn_model_demo_metrics.json` and explicitly labeled as too small to be a generalization claim —
train accuracy reached 100% on only 12 samples, which is a memorization/overfitting warning
sign, not evidence of a working classifier.

**Q: What are the limitations?**
A: Training set of only 12 real samples; no LLM integrated (heuristic substitute, disclosed);
fusion is an unweighted average, not trained; DOM graph capped at 200 elements per page; no
statistically meaningful accuracy claim.

**Q: If the dataset has hundreds of samples, why was the GNN trained on only 12?**
A: The 12-sample GNN checkpoint comes from the earlier controlled pilot, run to validate the
collection pipeline itself (feeds, crawling, snapshot integrity, dedup). Phase 3 collection has
since been completed (679 eligible samples recorded, 678 integrity-verified), but no model has been retrained or evaluated on it
yet. An earlier retrain attempt on a still-tiny sample made live behaviour worse and was
deliberately not adopted, so the retrain is deferred until it can be done properly on the larger
dataset.

**Q: What would you do with the completed dataset?**
A: Retrain the GNN with proper regularization and validation-based early stopping, train a real
fusion model, and run a full accuracy/precision/recall/F1/ROC-AUC/MCC evaluation on the held-out,
domain-grouped test split. None of this has been done yet.

**Q: Why isn't the current GNN claimed as production-ready?**
A: 12 training samples cannot support a generalization claim by any reasonable statistical
standard. The dashboard and this documentation say so explicitly rather than presenting a
polished-looking but unjustified accuracy number.

**Q: How does the system avoid fabricated results?**
A: Every component either returns a real, computed value or an explicit `unavailable`/`error`
status — never a substituted guess presented as a real result. This was an explicit design rule
throughout development (see `CLAUDE.md` §14, "Academic integrity rules").

**Q: What happens if a website cannot be crawled?**
A: The pipeline stops at the crawl step and returns `verdict: "unavailable"` with the specific
failure reason (timeout, connection error, TLS error, content too large, invalid URL, etc.). No
downstream component runs on fake data.

**Q: What happens with redirects?**
A: The crawler follows up to 5 redirects automatically (via httpx) and records the final
resolved URL and the redirect count; analysis runs on the final destination page.

**Q: What is explainability in this project?**
A: Every component returns its own real evidence alongside its score — the URL's flagged
features, the GNN's exact node/edge/density counts, the semantic heuristic's exact matched
keyword terms — all shown in the dashboard's "Why This Result?" panel, plus the full raw JSON
response for complete transparency.

**Q: What is the role of FastAPI?**
A: FastAPI (`api.py`) is the web framework serving the dashboard (`GET /demo`) and the analysis
endpoint (`POST /api/v2/analyze`), which runs the full pipeline and returns JSON.

**Q: Why use BeautifulSoup?**
A: A well-established, real HTML parser used to build the actual DOM tree from the crawled HTML
— the basis for both the graph-construction step and the visible-text extraction used by the
semantic heuristic.

**Q: What is the difference between phishing and benign in this dataset?**
A: Phishing = URLs sourced from PhishTank/OpenPhish live threat feeds. Benign = URLs sourced
from the Tranco top-sites list. Labels come from the source feed, not from any model prediction.

**Q: What future improvements are planned?**
A: Larger real dataset; one real integrated language model for semantics; a trained fusion
model; a full, honest evaluation once the dataset justifies it; GNNExplainer-based structural
explanations.
