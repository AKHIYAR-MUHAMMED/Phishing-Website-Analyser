# PhishGuard AI — Presentation Speaking Script

Natural, sayable sentences for tomorrow's live demonstration. Optional deeper answers are
marked "If asked further:" under each section.

---

## INTRODUCTION

"Good [morning/afternoon]. I'm going to show PhishGuard AI, a phishing website detection
system that combines webpage structure and webpage text to make a decision, and — importantly
— explains what it based that decision on."

## PROBLEM

"Phishing websites imitate real login pages to steal credentials. Most detection tools only
look at the URL string. We wanted to also look at how the page is actually built — its DOM
structure — and what it actually says, not just its address."

*If asked further:* "URL-only detection is easy to evade — attackers just change the domain
name. Looking at the page's real structure and content is harder to fake cheaply."

## PROJECT OBJECTIVE

"The objective is a multimodal system: analyze the URL itself, analyze the page's DOM structure
using a graph neural network, and analyze the page's text — then combine those signals into one
result, with evidence for each part, not just a black-box score."

## SYSTEM OVERVIEW

"When you give it a URL, the system does five things in order: it crawls the real page, it
extracts URL and structural features, it runs a graph neural network over the page's DOM tree,
it runs a keyword-based semantic scan over the page text, and it combines all three into one
result you can inspect part by part."

*If asked further:* "Right now the semantic part is a disclosed rule-based heuristic, not a
language model — no LLM API key is configured in this environment, so we show that honestly
instead of faking an LLM response."

## LIVE DEMO

**Action: start at `http://localhost:8000/demo`.**
"This is the live dashboard. Before I scan anything, notice this status strip — it tells you
exactly what's real right now: the GNN is active, the semantic engine is a heuristic not an
LLM, and fusion is an unweighted average, not a trained model. We disclose this up front."

**Action: type or select a URL, e.g. `github.com`, click Analyze.**
"I'll scan a real, live website now. Watch the pipeline stages light up — crawl, feature
extraction, DOM graph construction, GNN inference, semantic analysis, fusion, result. Each
stage only turns green when the real backend has actually finished that step."

**Action: point at the verdict card.**
"Here's the result: [Benign/Phishing], with a Fused Threat Signal of [X]%. I want to be precise
— we call this a 'threat signal,' not a probability, because it's a simple average of three real
component scores, not a calibrated statistical probability."

**Action: point at the three component cards.**
"Each component is shown separately with its own evidence: the URL analysis, the GNN structural
score with the real node and edge counts from this exact page, and the semantic heuristic with
the exact keyword terms it matched."

**Action: open the DOM graph visual.**
"This is a visual preview of the page's structure, generated from the real node and edge counts
of this scan. I want to be clear it's an illustrative layout, not a literal picture of every
element — the API gives us aggregate graph statistics, not a full per-node map."

**Action: scan a second URL.**
"Let me run one more, a different real site, so you can see the output genuinely changes with
real input — different structure, different score, different evidence."

## RESULT EXPLANATION

"The fused score is a plain average of whatever components successfully ran. If a component is
unavailable — say the page couldn't be crawled — it's excluded from the average and marked
unavailable, never silently replaced with a guess."

## TECHNICAL PIPELINE

"URL goes in. A real HTTP crawler fetches the page. We extract URL-string features and parse
the HTML into a DOM graph — one node per HTML element, edges between parent and child elements.
That graph goes through a 2-layer Graph Attention Network, which pools the whole graph into one
structural threat score. Separately, the page's visible text goes through a keyword heuristic.
The three scores are averaged into the final result."

*If asked further — "why a graph, why not just a normal neural network?":* "A webpage's HTML is
naturally a tree of nested elements, not a flat vector. A graph neural network can learn from
that structure directly — for example, where a password field sits relative to a form, or how
deeply nested a suspicious element is — instead of flattening that structure away."

## LIMITATIONS

"I want to be upfront about the current limitations, because this is a research prototype, not
a finished product:
- The GNN was trained on only 12 real labeled webpage graphs — far too small to claim it
  generalizes. We disclose this in the app itself, in the 'Model & Dataset Transparency' panel.
- There is no LLM integrated yet — the semantic component is a disclosed keyword heuristic.
- The fusion step is a simple unweighted average, not a trained fusion model.
- The DOM graph caps at 200 elements per page, so very large pages are truncated."

## FUTURE WORK

"Planned next steps: collect a much larger, real labeled dataset from PhishTank, OpenPhish and
Tranco; integrate one real language model for the semantic branch instead of the heuristic;
train an actual fusion model instead of averaging; and run a proper evaluation with accuracy,
precision, recall, F1 and ROC-AUC on held-out data, once the dataset is large enough to support
that honestly."

## CONCLUSION

"So to summarize: PhishGuard AI is a real, working, end-to-end pipeline — real crawling, real
DOM-graph GNN inference, real feature extraction, disclosed heuristic where a model isn't yet
available — built around one rule we followed throughout: never fabricate a result, and always
say clearly when something isn't real yet. Happy to answer questions."
