# Phase 3 — Dataset Collection Plan

> **Status: PLAN ONLY. Nothing in this document has been executed.** No URL has been fetched,
> no dataset has been downloaded, no file under `data/raw/` exists yet. This is the design to
> be reviewed and approved before any collection code runs, per `CLAUDE.md` §16 and the
> Master Implementation Prompt's Phase 3 boundary ("do not start dataset collection").

Branch: `phase-3-dataset`, created from `phase-2-crawler` at commit `98cefb8` (no code changed
on this branch yet). Base for integration: `crawler/fetcher.py`'s `fetch_url()` — see §1.4 for
exactly how this plan reuses it.

---

## 0. What Phase 2 already gives us (inspected, not assumed)

- `crawler.fetch_url(url, *, timeout=None, max_redirects=None, max_content_bytes=None) -> dict`
  — async, GET-only, returns `{"status": "ok", "final_url", "http_status", "content_type",
  "headers", "html", "html_length_bytes", "title", "visible_text", "redirect_count",
  "crawled_at", "elapsed_ms", ...}` or `{"status": "error", "error_type", "error_message", ...}`.
  Explicit error types: `invalid_url`, `timeout`, `connection_error`, `ssl_error`,
  `too_many_redirects`, `content_too_large`, `error`. Never raises; never invents content.
- `crawler/fetcher.py`'s own docstring already flags the gap this plan must close: *"does not
  read robots.txt and applies no crawl-delay/rate-limiting of its own — appropriate for single
  interactive requests, not for unattended bulk crawling. Add both before any future
  bulk-collection use (Phase 3 dataset collection) of this module."* §3 below is that addition.
- `dataset_loader.extract_url_lexical_features(url)` — genuine URL-string features (`CLAUDE.md`
  §10, kept). Reusable as-is for whatever feature stage comes after Phase 3; not re-implemented
  here, since Phase 3 only collects snapshots, it does not featurise them (that is Phase 4).
- `config.py` — the place new `DATASET_*` / `CRAWL_*` environment variables from this plan would
  live, with the same "safe default, override via `.env`" pattern already established.
- `seeding.py` — `set_seed()`, to be called before any random sampling step this plan performs
  (e.g. sampling benign URLs from Tranco, choosing which duplicates to keep).
- **Not present yet:** `tldextract` (or equivalent) for registered-domain extraction — §7 needs
  it; not currently in `requirements.txt`. Would be added when this plan is implemented, not now.
- **Network reachability, observed from this development sandbox just now (informational only,
  not a design input):** `data.phishtank.com` answered with HTTP 403 (host reachable, request
  blocked/needs a different client), `openphish.com` answered with an HTTP redirect (host
  reachable), but `tranco-list.eu`, `raw.githubusercontent.com` and `api.github.com` did not
  respond within 8s from here. This sandbox's outbound network is evidently restricted or
  inconsistent. **This means Phase 3 execution should be assumed to require a different
  environment (a GitHub Actions job, or a team member's machine) than this chat sandbox, and
  reachability of every source below must be re-verified at execution time — it is not assumed
  by this plan.**

---

## 1. Exact data sources and acquisition method

| Label | Source | Acquisition |
|---|---|---|
| Phishing | **PhishTank** | Bulk feed download: `http://data.phishtank.com/data/online-valid.csv` (or `.json`), refreshed hourly by PhishTank. Requires a registered "application key" appended as `?app_key=...` for reliable, non-rate-limited access (PhishTank throttles anonymous requests). The key is a secret → read from `PHISHTANK_APP_KEY` env var, never committed (see §2). |
| Phishing | **OpenPhish** | Free community feed: `https://openphish.com/feed.txt`, one URL per line, updated continuously, **no API key**, but the free feed is capped at the most recent ~500 URLs (OpenPhish's paid tier gives more). This caps how many *fresh* phishing URLs are available at any one collection run — see §9 on class balance. |
| Benign | **Tranco** | A *generated, timestamped, citable* top-1M list via `https://tranco-list.eu/api/lists/date/YYYYMMDD` (or the "create a list" API), downloaded as `top-1m.csv.zip`. Tranco is specifically designed for research reproducibility (each list has a permanent ID you can cite — see §2). |

Acquisition method for all three: a **new, separate module** `dataset/sources.py` (not part of
`crawler/`, which stays a generic one-URL-at-a-time fetcher) that:
1. Downloads each feed with `httpx` (already a dependency), with its own timeout — reuses
   `config.CRAWLER_TIMEOUT_SECONDS` as a default but this is a bulk metadata download, not a
   page crawl, so it is a distinct code path, not a call to `crawler.fetch_url`.
2. Parses each feed into a common in-memory shape: `{url, source, label, source_metadata}`
   where `source_metadata` keeps source-specific fields (PhishTank's `phish_id`,
   `verification_time`; Tranco's rank and list ID) for the manifest and the dataset card.
3. Writes the raw, unmodified feed response to `data/raw/feeds/<source>_<date>.{csv,txt}`
   before any parsing, so the exact input is itself reproducible and auditable (not just the
   parsed output) — this is the acquisition-time equivalent of the HTML snapshot idea in §11.

**Why not use the legacy `dataset_loader.py`/`external_dataset_collector.py` machinery:**
per `CLAUDE.md` §6 and §13 those are synthetic/metadata-only and slated for removal; Phase 3
is new code in a new `dataset/` package, not a modification of that legacy module.

---

## 2. Licensing / terms and reproducibility considerations

- **PhishTank:** free for research/non-commercial use; the terms require attribution and
  prohibit redistributing the raw feed as a commercial product. We keep our **derived** dataset
  (crawled HTML + manifest) out of the *committed synthetic-CSV-replacement* until the team
  confirms redistribution is fine for a public repo; the **raw feed snapshot** goes under
  `data/raw/feeds/`, `.gitignore`d by default (see §11), not committed, unless the team
  explicitly approves committing PhishTank-derived content. Attribution line added to the
  dataset card (§14) and README regardless.
- **OpenPhish:** the free feed's terms permit use for research; no redistribution of their
  commercial feed data. Same treatment as PhishTank: raw feed not committed by default.
- **Tranco:** explicitly built for citable research reuse (CC BY 4.0 on the list itself); each
  downloaded list has a stable **List ID** (e.g. `Y2N9`) that must be recorded in the dataset
  card so the exact benign-domain list is independently reproducible by re-downloading that
  same ID later, even though the "current" top-1M changes daily.
- **The websites themselves:** crawling any live URL (phishing or benign) means fetching content
  from third-party servers we don't own. §3's rate limits and `robots.txt` handling exist partly
  for this reason — being a good network citizen, not just avoiding IP bans.
- **This repo has no committed `LICENSE` file** despite the README's MIT badge (checked: absent
  from the working tree). That's a pre-existing gap unrelated to Phase 3, but relevant here
  since it means the *project's own* licensing terms for redistributing any collected dataset
  are currently undefined. Flagging for the team; not fixing as part of this plan.
- **Reproducibility:** every source's acquisition timestamp, the exact URL/endpoint used, and
  (for Tranco) the List ID are recorded in the dataset card (§14) and in `data/raw/feeds/`
  filenames, so a re-run months later can document *what changed* rather than silently drifting.

---

## 3. Crawl rate, timeout and safety limits

Adds a **bulk-crawl policy layer** on top of the existing per-request `crawler.fetch_url`
limits (timeout/redirects/size, unchanged, still enforced per-URL):

- **Rate limiting:** a global `asyncio.Semaphore` capping concurrent in-flight crawls (default
  `DATASET_CRAWL_CONCURRENCY = 5`, env-overridable) plus a minimum per-*host* delay (default
  `DATASET_CRAWL_HOST_DELAY_SECONDS = 2.0`) tracked in a `{host: last_request_time}` map, so we
  never hit any single site faster than once every 2 seconds even if several of its URLs appear
  in the same batch (this matters most for benign Tranco domains, where multiple URLs can share
  a host). Phishing URLs are typically one-per-host anyway.
- **robots.txt:** fetch and cache each host's `/robots.txt` once (short-lived in-memory cache
  per run), parse with Python's standard-library `urllib.robotparser`, and **skip** (log as
  `robots_disallowed` in the manifest, not silently drop) any URL that the site disallows for
  our user agent. This directly closes the gap `crawler/fetcher.py`'s own docstring names.
  Known tension: a phishing site's `robots.txt` is not a meaningful signal (attackers rarely
  publish one, and honoring it does not affect detection validity) but we apply it uniformly to
  both classes for consistency and to avoid the appearance of treating phishing sites specially.
- **Timeout:** same `CRAWLER_TIMEOUT_SECONDS` (8s default) as Phase 2, not loosened — a bulk run
  should not wait longer per-URL than an interactive scan does; slow sites are logged as
  `timeout` failures (§10), not retried indefinitely.
- **Retries:** **one** retry for `timeout`/`connection_error` only (not for `http_error`,
  `invalid_url`, or `content_too_large`, which will not resolve on retry), with a 5-second
  backoff. Phishing URLs go offline fast (`CLAUDE.md` §15), so a failed phishing-URL crawl is
  expected and logged, not treated as a bug to retry aggressively.
- **User agent:** the existing `CRAWLER_USER_AGENT` from `config.py`, unchanged — it already
  self-identifies as a research crawler.
- **Safety (unchanged from Phase 2, restated because bulk collection is exactly the scenario
  `CLAUDE.md` §18.12 warns about):** GET requests only, no form submission, no execution of any
  downloaded file, isolated dev/CI environment only.

---

## 4. How phishing and benign labels are assigned

- **Phishing (label = 1):** every URL present in the PhishTank "verified valid" feed or the
  OpenPhish feed at collection time. PhishTank's feed is itself community-verified (each entry
  has a `verified` flag and `verification_time`); we only take `verified == "yes"` rows.
  OpenPhish's feed is pre-filtered to their own confirmed list (no additional verification
  field to check). The label is the source's label; we do not re-verify by inspecting page
  content, since doing so would risk exactly the kind of "feature derived from the label"
  leakage `CLAUDE.md` §14 rule 7 forbids (e.g. flagging a page as "actually legitimate" based on
  the same content that will become a training feature).
- **Benign (label = 0):** every URL taken from the Tranco top-N domains, **not just each
  domain's homepage** — `CLAUDE.md` §15 explicitly requires this ("benign from Tranco including
  login pages, not only homepages, so the model can't learn 'login page vs homepage'"). Concrete
  approach: for each sampled Tranco domain, attempt `https://{domain}/` and, where discoverable
  cheaply, one additional "interesting" page (e.g. a `/login`, `/signin`, or `/account` path
  found via a same-domain link during the homepage crawl — not a separate paid API). Domains
  where no second page is found contribute only their homepage; this is logged, not hidden.
- **No manual review labels in Phase 3.** A human-verification/spot-check step is worth adding
  later (would sit naturally in the dataset card as a documented limitation either way) but is
  out of scope for this plan — flagging it as a future improvement, not silently skipping it.
- **Mislabelling risk both directions is documented as a limitation** in the dataset card (§14):
  Tranco domains can themselves be compromised or host phishing kits on subdomains; PhishTank/
  OpenPhish can contain stale or disputed entries. We do not attempt to resolve this beyond
  taking each source's own verification status at face value, and we say so explicitly.

---

## 5. Deduplication strategy

Two layers, applied in this order:

1. **URL-level, before crawling:** normalize every URL (lowercase scheme+host, strip default
   ports, strip fragment, sort query parameters) and drop exact duplicates *within* a single
   collection run and *across* the three sources (a URL appearing in both PhishTank and
   OpenPhish is kept once, with `source` recording both — see §12's manifest schema). This
   avoids wasting a crawl on a URL we already fetched this run.
2. **Cross-run, before appending to the manifest:** check the URL's normalized form against
   every prior run's manifest (loaded from `data/manifest.csv`, see §12) before adding a new
   row, so re-running collection on a later date does not duplicate a URL already collected
   (a URL that reappears gets logged as `already_collected`, not re-crawled) — this keeps the
   crawl polite (§3) and keeps `data/raw/` from growing with redundant snapshots.

Deliberately **not** deduplicating by "similar" URL (e.g. same domain, different path) at this
stage — that would conflate URL-level dedup with domain-grouping, which is §7's separate,
explicit step so it stays auditable.

---

## 6. HTML/content hashing

- After a successful crawl, compute `sha256(html.encode("utf-8"))` over the **exact HTML
  returned by `crawler.fetch_url`** (before any parsing) and store it as `html_sha256` in the
  manifest (§12).
- **Purpose 1 — near-duplicate detection:** many phishing kits are reused verbatim across
  hundreds of URLs (same HTML, different domain). Any two manifest rows with the same
  `html_sha256` are flagged as `duplicate_content_of: <first_url_with_this_hash>` and **only the
  first is eligible for the modelling dataset**; duplicates are kept in the manifest (for
  transparency about how much repetition exists in the raw collection) but excluded before
  splitting (§8) so the same phishing kit cannot appear in both train and test.
- **Purpose 2 — snapshot integrity:** the hash lets us verify later that a stored snapshot file
  under `data/raw/html/` was not corrupted or modified after collection, without re-crawling.
- A whitespace-normalized secondary hash (strip all whitespace runs before hashing) is *not*
  computed in Phase 3 — flagged as a possible Phase 4 refinement if exact-hash dedup proves too
  strict (e.g. two crawls of the same page 1 second apart differing only in a timestamp in the
  HTML), not built speculatively now.

---

## 7. Registered-domain grouping

- Add `tldextract` (new dependency; not yet in `requirements.txt` — would be added when this
  plan is implemented) to compute each URL's **registered domain** (a.k.a. eTLD+1, e.g.
  `login.example.co.uk` → `example.co.uk`), stored as `registered_domain` in the manifest.
- This directly fixes the bug `CLAUDE.md` §5.1/§11 already flags in the *existing* GNN/feature
  code (`target_domain not in link`, a naive substring match that treats `paypal.com.evil.net`
  as internal to `paypal.com`) — Phase 3 does not touch that code, but uses the *correct* method
  from the start for its own grouping, and this plan explicitly recommends `tldextract` be the
  fix adopted in the Phase 4 shared featuriser too, for consistency.
- Used exclusively for §8's split (grouping), not as a modelling feature at this stage.

---

## 8. Train/validation/test split strategy

- **Grouped, not random:** split **by `registered_domain`**, not by individual URL row — every
  URL sharing a registered domain goes into the same split. This directly satisfies `CLAUDE.md`
  §14 rule 6 and §17.3 ("no ... registered domain ... appears in more than one split").
- **Ratio:** 60/20/20 (train/val/test), matching the ratio already named in the project's
  documented evaluation plan (`CLAUDE.md` §1) — computed on **domain groups**, not raw row
  counts, so the realized row-level ratio will differ slightly (a domain group can contain
  several rows, e.g. Tranco homepage + login page).
- **Stratified by label within the grouping constraint:** domain groups are assigned to splits
  via a seeded (see `seeding.py`) greedy bin-packing that balances (a) each split's target row
  count and (b) each split's phishing/benign ratio, since phishing and benign URLs are disjoint
  by construction (a phishing-source domain never also appears in the Tranco benign sample) —
  so this is really two independent grouped splits (one over phishing domains, one over benign
  domains) combined, not a single mixed pool.
- **Determinism:** the split is written to `data/splits/{train,val,test}.txt` (one normalized
  URL per line) as its own versioned artifact (§13), generated by a script that takes only the
  manifest + a seed as input — so it is regenerable and diffable, not baked silently into the
  manifest itself.
- **No held-out test contamination:** per `CLAUDE.md` §14 rule 6, once written, `test.txt` is
  not inspected again until final evaluation (Phase 10) — this plan only *creates* the split,
  it does not consume it.

---

## 9. Class balance

- **Target:** as close to 50/50 phishing/benign as the sources allow, but **not forced** by
  discarding real data — `CLAUDE.md` §14 rule 8 requires reporting weak/negative results
  honestly, and an artificially balanced-by-truncation dataset would itself misrepresent
  collection reality.
- **Known constraint (from §1):** OpenPhish's free feed caps live phishing URLs at roughly 500
  at any moment; PhishTank's feed is larger but many entries go offline before we crawl them
  (expected — see §10), so the number of *successfully crawled* phishing snapshots per run will
  likely be in the low hundreds unless collection is repeated over several days/weeks and
  accumulated into the manifest (§12 is designed to append across runs precisely for this).
  Benign collection from Tranco has no comparable ceiling.
- **Plan:** sample benign URLs from Tranco to roughly match the count of *successfully crawled*
  phishing URLs each run (not the other way around — we don't truncate the smaller, harder-to-
  get phishing class to match an arbitrary benign target). The realized class balance is
  computed and reported after each run, not assumed in advance, and recorded in the dataset
  card (§14) alongside the raw counts.
- **Over multiple runs**, the manifest accumulates phishing snapshots faster relative to
  effort than benign ones are needed, since PhishTank/OpenPhish are re-crawled periodically
  (catching newly-listed URLs) while the benign sample only needs periodic top-up.

---

## 10. Failed/invalid URL handling

Every URL attempted gets exactly one manifest row (§12), success or failure — **nothing is
silently dropped**, per `CLAUDE.md` §14 rule 2's "no silent substitution" principle extended to
collection, not just live inference:

| Outcome | Manifest `crawl_status` | Notes |
|---|---|---|
| Fetched successfully | `ok` | Snapshot stored (§11); eligible for splitting unless a content-hash duplicate (§6) |
| `crawler.fetch_url` returned `status: error` | the exact `error_type` (`timeout`, `connection_error`, `ssl_error`, `too_many_redirects`, `content_too_large`, `invalid_url`, `error`) | Retried once for `timeout`/`connection_error` per §3; final outcome recorded |
| Blocked by `robots.txt` | `robots_disallowed` | Not retried; not crawled at all |
| Already in a prior manifest | `already_collected` | Not re-crawled (§5); prior row's outcome stands |
| Malformed/unparseable source-feed row | `source_parse_error` | Logged with the raw offending line saved to the run's log, so a feed-format change is visible, not silently ignored |

A per-run **collection summary** (attempted / succeeded / failed by `error_type` / skipped by
`robots_disallowed` / already-collected) is written to `data/raw/feeds/run_<date>_summary.json`
and rolled into the dataset card (§14) — this is what "document ... failures" (the user's
explicit Phase 3 scope item) refers to concretely.

---

## 11. Snapshot storage structure

```
data/
  raw/
    feeds/
      phishtank_2026-10-01.csv          # exact bulk feed response, timestamped
      openphish_2026-10-01.txt
      tranco_2026-10-01_<listid>.csv
      run_2026-10-01_summary.json       # counts described in §10
    html/
      <sha256-of-normalized-url>.html   # exactly what crawler.fetch_url returned; content-addressed by URL, not by row number, so re-crawling the same URL overwrites deterministically
  manifest.csv                          # append-only across runs; see §12
  splits/
    train.txt / val.txt / test.txt      # generated from manifest.csv, see §8
  DATASET_CARD.md                       # see §14
```

- **Naming by `sha256(normalized_url)`** (not by row index or timestamp) so the filename itself
  is a stable, reproducible function of the URL — two different runs crawling the same URL
  produce the same filename (the later one overwrites, which is correct: we want the manifest's
  `crawled_at` for that URL to reflect the most recent snapshot on disk).
- **Only HTML is stored**, not screenshots — consistent with `CLAUDE.md` §15's scope note that
  visual capture is deferred, and with this Phase 3 scope explicitly listing "reproducible HTML
  snapshots" only.
- **`.gitignore`:** `data/raw/` is added to `.gitignore` (the collected dataset is regenerable
  from the manifest + re-crawling, and per §2's licensing caution, raw third-party feed content
  should not be committed by default). `data/manifest.csv`, `data/splits/`, and
  `data/DATASET_CARD.md` **are** committed — they're small, are exactly the reproducibility
  artifacts `CLAUDE.md` §14 rule 1 requires, and contain no redistribution-restricted raw feed
  content (URLs and metadata, not the sources' original file). This is a plan recommendation
  for the team to confirm, not yet applied to `.gitignore`.

---

## 12. Manifest schema

`data/manifest.csv`, one row per **collection attempt** (append-only across runs, never
rewritten in place, so history is preserved):

| Column | Type | Description |
|---|---|---|
| `url` | str | Original URL as given by the source |
| `normalized_url` | str | Normalized form used for dedup (§5) |
| `registered_domain` | str | From `tldextract` (§7) |
| `label` | int (0/1) | 1 = phishing, 0 = benign (§4) |
| `source` | str | `phishtank`, `openphish`, or `tranco`; a URL seen in >1 phishing source lists both, `;`-joined |
| `source_metadata` | JSON str | Source-specific fields (PhishTank `phish_id`/`verification_time`; Tranco `rank`/`list_id`) |
| `collection_run_date` | date (ISO 8601) | Which run attempted this URL |
| `crawl_status` | str | `ok` or one of §10's failure/skip codes |
| `crawled_at` | ISO 8601 datetime or empty | From `crawler.fetch_url`'s `crawled_at`, empty if not attempted |
| `final_url` | str or empty | Post-redirect URL, from `fetch_url` |
| `http_status` | int or empty | From `fetch_url` |
| `redirect_count` | int or empty | From `fetch_url` |
| `content_type` | str or empty | From `fetch_url` |
| `html_length_bytes` | int or empty | From `fetch_url` |
| `html_sha256` | str or empty | §6 |
| `duplicate_content_of` | str (URL) or empty | §6, set only when this row is a detected duplicate |
| `html_snapshot_path` | str or empty | Relative path under `data/raw/html/`, empty if not `ok` |
| `error_type` / `error_message` | str or empty | From `fetch_url`'s error dict, when applicable |
| `robots_txt_checked` | bool | Whether §3's robots check ran for this host this run |
| `split` | str or empty | `train`/`val`/`test`, filled in only after §8 runs; empty immediately after collection |

Every field name matches (or is a direct pass-through of) a key `crawler.fetch_url` already
returns, so building this manifest is mostly "take the dict `fetch_url` gives us and flatten
it" — deliberately not inventing a parallel schema.

---

## 13. Dataset versioning

- **Manifest is append-only**, each row stamped with `collection_run_date` (§12) — this alone
  gives a full history without a separate versioning scheme bolted on.
- **A dataset "version"** is defined as a **git tag** on the commit that updates
  `data/manifest.csv` + `data/DATASET_CARD.md` together (e.g. `dataset-v1-2026-10-01`), same
  pattern already used for the audit baseline tag (`baseline-pre-phase0`) created in Phase 0.
- **`data/splits/{train,val,test}.txt` are regenerated, not hand-edited**, whenever the manifest
  changes meaningfully (new run appended) — each regeneration is its own commit, so `git diff`
  shows exactly which URLs moved between splits or were added, which is itself a useful
  reproducibility/leakage check.
- **The raw HTML files under `data/raw/html/` are not versioned individually** (they're
  `.gitignore`d per §11); the manifest's `html_sha256` is what lets someone verify a
  re-generated snapshot matches what a given dataset version originally saw.

---

## 14. Dataset card contents (`data/DATASET_CARD.md`)

Generated (not hand-written from memory) by a script that reads `manifest.csv` and the run
summary JSONs, so its numbers can never drift from the actual data — directly satisfying
`CLAUDE.md` §14 rule 1 ("every reported number must be produced by code run on data"):

1. **Collection date(s)** — every `collection_run_date` present, oldest to newest.
2. **Sources** — PhishTank/OpenPhish/Tranco, with the exact endpoint URLs used, the Tranco List
   ID(s) (§2), and each source's license/terms summary (§2).
3. **Counts** — total URLs attempted, succeeded, failed (broken down by `error_type`), skipped
   by robots.txt, already-collected; phishing vs benign counts; unique vs duplicate-content
   counts (§6).
4. **Class balance** — realized phishing/benign ratio (§9), stated as measured, not targeted.
5. **Split sizes** — row and domain-group counts per split (§8), confirming no registered domain
   appears in more than one split (a generated assertion, not a claim).
6. **Filtering/exclusion decisions** — exactly what got excluded before splitting and why:
   content-hash duplicates (§6), `robots_disallowed` URLs, failed crawls.
7. **Known limitations** — label-trust caveats (§4), OpenPhish's feed-size ceiling (§9), the
   single-retry policy possibly under-counting transient failures (§3), no visual/screenshot
   data (§11), no manual verification pass.
8. **Reproducibility instructions** — the exact commands (once implemented) to re-run collection
   and regenerate splits from a given manifest.

---

## 15. Expected dataset size and storage requirements

- **Realistic first-run estimate**, based on §9's constraints, stated as an estimate, not a
  promise: on the order of **300–800 phishing snapshots** (bounded by OpenPhish's feed size and
  PhishTank URLs still alive at crawl time) and a **matching benign count** sampled from Tranco,
  so roughly **600–1,600 total HTML snapshots** for a single run. This is an order-of-magnitude
  planning estimate, not a number to hold the team to — actual counts will be measured and
  reported (§14 item 3), never assumed.
- **Storage:** average HTML snapshot size is unknown until measured, but the existing crawler's
  `CRAWLER_MAX_CONTENT_BYTES` cap (2MB) bounds each file; at ~1,600 snapshots worst-case that is
  at most ~3.2GB, almost certainly far less in practice (most pages are tens of KB). Since
  `data/raw/html/` is `.gitignore`d (§11), this storage lives only on the machine that ran
  collection, not in the git repository — relevant because the current repo (`.git` ≈ 3.6MB,
  working tree `data/` ≈ 11MB today) should not grow by gigabytes.
- **Committed artifacts** (`manifest.csv`, `splits/*.txt`, `DATASET_CARD.md`, the `feeds/*`
  summary JSONs if the team approves committing those per §2) are expected to be small —
  low hundreds of KB for a first run, growing slowly as runs accumulate.
- Repeated runs over time (to grow the phishing-class count per §9) will grow storage roughly
  linearly with total unique URLs collected; no cap is proposed in this plan beyond normal
  disk-space monitoring, since the team controls when runs happen.

---

## What this plan deliberately does NOT do yet

- No source is downloaded, no URL is crawled, no file under `data/raw/` or `data/manifest.csv`
  exists as a result of writing this plan.
- `requirements.txt` is not changed (the `tldextract` addition in §7 is proposed, not applied).
- `.gitignore` is not changed (the `data/raw/` addition in §11 is proposed, not applied).
- `crawler/fetcher.py` is not modified — the bulk-crawl policy layer in §3 is designed as new
  code that *calls* `fetch_url` per-URL, not a change to that module's existing behaviour or
  its Phase 2 tests.
- No model training, no featurisation beyond what `dataset_loader.extract_url_lexical_features`
  already does (and Phase 3 doesn't even call that — it collects snapshots, Phase 4 featurises
  them).

## Open questions for the team before implementation

1. Approve or reject committing `data/raw/feeds/*` (the raw third-party feed snapshots) given
   the licensing caution in §2 — proposed default is **not committed**.
2. Confirm the `robots.txt`-honoring policy in §3, including its explicit tension around
   phishing sites (applied uniformly, not skipped for them).
3. Confirm the 60/20/20 domain-grouped split ratio and the "match benign count to phishing
   count" balancing approach in §9, rather than a fixed target size.
4. Confirm `tldextract` as the registered-domain library (§7), and whether the Phase 4 shared
   featuriser should adopt it too when that phase starts (recommended, but a Phase 4 decision).
5. Decide whether a PhishTank `PHISHTANK_APP_KEY` will be obtained before implementation, or
   whether the first runs proceed anonymously (rate-limited) until one is available.
