# Phase 3 — Dataset Collection Plan (v2 — approved design; since implemented, see "Since approval" below)

> **Historical status, as of approval of this v2 plan (see "Since approval" below): PLAN ONLY.
> Nothing in this document has been executed.** No URL has been fetched,
> no dataset has been downloaded, no file under `data/raw/` exists yet. `requirements.txt`,
> `.gitignore` and `crawler/fetcher.py` are unmodified. This revision incorporates an
> independent technical review of v1 (Freebuff). All 14 corrections below, and their listed
> resolutions, were approved by the team (see **Approved decisions** at the end) — approval
> covers the *design*, not execution; nothing is implemented, downloaded, or crawled by this
> document.

> **Since approval.** The design has been implemented (`dataset/`, with matching changes to
> `config.py`, `requirements.txt`, `.gitignore` and `crawler/fetcher.py`), and real collection runs
> have been performed (a pilot and five scaled versions, v1-v5, between 2026-09-29 and 2026-10-01).
> The collected data, manifest and generated dataset card are kept outside Git. The sections below
> were not rewritten to reflect this; they describe the design as approved, and later amendments
> are marked.

> **Amendment — committing dataset artifacts is suspended.** Wherever this plan proposes committing
> `data/manifest.csv`, `data/derived/selection_v*.csv`, `data/splits/`, `data/feed_digests/`, raw or
> normalized crawled URLs, or any other artifact that contains crawled URLs (including the
> "`.gitignore` / commit decisions" bullet in section 11), that proposal is **suspended**. Real feed
> URLs can embed victim identifiers (e-mail addresses, session or token values), and neither the
> manifest nor the files derived from it redact them. These artifacts are now `.gitignore`d and must
> stay uncommitted until URL privacy has been addressed and reviewed. `data/DATASET_CARD.md` and
> `data/backups/*.sha256` contain no crawled URLs and are unaffected. The rest of this document is
> the unchanged v2 design.

Branch: `phase-3-dataset`, created from `phase-2-crawler` at commit `98cefb8`. v1 of this plan
was commit `c6a04ed`; this revision (v2) replaces it, same branch, no other file touched.

**Tagging convention used throughout:** `[REQUIRED]` — the review identified a concrete
correctness/validity bug; applied to the design below, not optional. `[RECOMMENDED]` — a real
improvement, applied below as the default, approved as such. `[OPTIONAL]` — a nice-to-have,
noted, not built into the default design. `[DEFERRED]` — out of scope for Phase 3, with the
reason stated, not silently dropped.

---

## 0. What Phase 2 already gives us (inspected, not assumed)

- `crawler.fetch_url(url, *, timeout=None, max_redirects=None, max_content_bytes=None) -> dict`
  — async, GET-only. **Corrected understanding from the review:** `status: "ok"` means *the
  HTTP transaction completed*, not that the response is usable content. Verified in
  `fetcher.py`: there is no `raise_for_status`; a 403, 404 or 500 response is `status: "ok"`
  with that `http_status`. Only transport-level failures (timeout, connection refused, TLS
  failure, too-many-redirects, oversized body) produce `status: "error"`. §6/§10 below build an
  explicit *eligibility* layer on top of this fact — v1 conflated "fetch completed" with
  "content is usable," which is the root cause of several findings below.
- `html_length_bytes` is the length of the **raw wire body**; `html` (when populated) is the
  **decoded string** used for parsing. These can legitimately disagree (encoding expansion/
  collapse); §6 now names which one each stored hash is taken over, instead of leaving it
  implicit as v1 did.
- `dataset_loader.extract_url_lexical_features(url)` — unchanged from v1's note; still not
  called by Phase 3 (that's Phase 4).
- `config.py` / `seeding.py` — unchanged from v1's note.
- **Not present yet:** `tldextract`. §7 now specifies not just "add it" but *how* (pinned PSL
  snapshot), per the review and the approved decision.
- **Network reachability** (informational, from v1, restated): `data.phishtank.com` and
  `openphish.com` responded; `tranco-list.eu`, `raw.githubusercontent.com`, `api.github.com`
  did not respond within 8s from this sandbox. Execution environment and reachability must be
  re-verified at implementation time, not assumed by this plan. Unchanged from v1.

---

## 1. Exact data sources and acquisition method

Unchanged from v1's table (PhishTank bulk feed, OpenPhish free feed, Tranco dated list), with
corrections:

- `[REQUIRED]` **PhishTank filter corrected.** v1 filtered on `verified == "yes"` only. Also
  filter on the feed's `online`/`valid` columns, not verification alone — a verified-but-no-
  longer-online entry should not be crawled at all (it will fail at the fetch layer anyway, but
  filtering upstream avoids wasting a crawl attempt and keeps the "attempted" count in the run
  summary meaningful).
- `[REQUIRED]` **Feed digest, not raw feed, is the default committed artifact.** *(Approved
  decision 13.)* Each run computes and records `{source, endpoint (secret-redacted, see §18),
  timestamp, sha256 of the raw feed response, row count}` — a **feed digest** — which is small,
  contains no redistribution-restricted content, and *is* committed (§14). The raw feed response
  itself (`data/raw/feeds/*`) stays local-only per §2. OpenPhish entries have no stable ID
  (unlike PhishTank's `phish_id`), so the digest is the only record of "what OpenPhish listed at
  time X" once the raw feed itself is gone — making the digest commitment more important for
  OpenPhish specifically, not just a formality.
- `[APPROVED — decision 11]` **PhishTank key: anonymous first, key added later.** Initial
  collection runs proceed **without** a `PHISHTANK_APP_KEY`, accepting PhishTank's anonymous
  rate limiting. The env var (`PHISHTANK_APP_KEY`, read the same way every other secret in this
  project is — see `config.py`'s pattern) can be added at any later point with no other change
  to the acquisition code; the bulk-download step already reads the key from the environment and
  simply omits `?app_key=...` when it is unset. See §18 for how the key (once present) is kept
  out of every committed artifact.

Acquisition method (`dataset/sources.py`, separate from `crawler/`) is otherwise unchanged.

---

## 2. Licensing / terms and reproducibility considerations

Unchanged from v1, plus:

- `[REQUIRED]` **Secret redaction applies here too.** §14's "exact endpoint URLs used" item, if
  written naively, would embed the PhishTank `app_key` (a secret, once one exists) directly into
  a committed dataset card. §18 defines the redaction rule; this section cross-references it —
  the endpoint recorded in any committed artifact uses a placeholder (`?app_key=REDACTED`),
  never the real key, regardless of whether a key is configured.
- `[OPTIONAL]` **Missing `LICENSE` file.** Flagged as pre-existing and out of scope in v1; the
  review adds that it becomes *urgent*, not just untidy, the moment `data/manifest.csv` is
  committed publicly, since the repo's own redistribution terms for that committed data are then
  undefined. Still not a Phase 3 change; flagged again here so it isn't lost.

---

## 3. Crawl rate, timeout and safety limits

Unchanged base design (concurrency semaphore, per-host delay, 8s timeout, one retry for
transient errors, GET-only, no form submission), plus:

- `[APPROVED — decision 7]` **`robots.txt` honored uniformly for both labels.** Two concrete,
  label-correlated costs are accepted knowingly rather than assumed away: (a) phishing kits
  often serve `Disallow: /` as an anti-analysis measure, so uniform honoring systematically
  removes the most evasive kits from the phishing class; (b) major benign sites routinely
  disallow exactly the `/login`, `/signin`, `/account` paths `CLAUDE.md` §15 requires for the
  benign class, so uniform honoring can push benign collection back toward homepages. Both costs
  are **required to be measured**: the dataset card (§14) reports the per-label `robots.txt`
  disallow rate every run.
- `[REQUIRED — decision, documented not fixed]` **Redirect-target host is never robots-checked.**
  The bulk-crawl policy layer can only see the *original* host before calling `fetch_url`, which
  follows redirects internally; the final host's `robots.txt` is never consulted. Fixing this
  would mean either pre-flighting the redirect chain outside `fetch_url` or modifying
  `crawler/fetcher.py` (out of scope — this plan does not modify Phase 2 code). Accepted as a
  documented limitation: robots.txt is checked for the source host only.
- `[RECOMMENDED]` **Robots bookkeeping.** Replace v1's boolean `robots_txt_checked` with an
  enumerated `robots_result`: `allowed` / `disallowed` / `no_robots_file` / `unreachable`
  (distinguishing "robots.txt says no" from "we couldn't even check"). Also note explicitly:
  `urllib.robotparser` does not honor a `Crawl-delay` directive — the fixed 2-second per-host
  delay from §3 is the *only* rate limit actually enforced, regardless of what a site's
  `robots.txt` requests. State this in the dataset card rather than implying `Crawl-delay` is
  respected.

---

## 4. How phishing and benign labels are assigned

Unchanged core design (source's own verification status, no content-based re-labeling — still
avoiding the `CLAUDE.md` §14 rule 7 feature-derived-from-label trap), plus:

- `[REQUIRED]` PhishTank filter corrected per §1 (`online`/`valid`, not verification alone).
- `[REQUIRED]` **A label is assigned to every capture row regardless of outcome** (per §9/§10's
  status vocabulary), but a row only enters the **modelling pool** when it passes the
  eligibility gate defined in §16 *(approved decision 1)*. This distinction — "labeled" vs
  "eligible for splitting" — did not exist explicitly in v1 and is the mechanism that fixes the
  review's top finding (§6/§10 below).

---

## 5. Deduplication strategy

Two layers as in v1 (URL-level pre-crawl, cross-run pre-append), with one correction:

- `[APPROVED — decision 6]` **Cross-run "already collected" skip applies only to eligible,
  successful rows; failed/ineligible rows are retried in later runs, and every attempt is kept.**
  v1's wording applied to *any* prior row, including a prior failure, which would have made the
  single-retry policy in §3 the **permanent** retry policy — a URL that timed out in run 1 could
  never be attempted again, silently and permanently losing that phishing URL from the dataset,
  directly undermining §9's multi-run accumulation strategy. **Resolved:** cross-run skipping
  (`already_collected`) applies only when a prior row for that `normalized_url` has
  `crawl_status == "ok"` **and** passed the §16 eligibility gate. A URL whose most recent
  attempt failed or was ineligible remains eligible for re-attempt in a later run, producing a
  **new** capture row — the prior row is never overwritten or removed (§11's immutability rule).
- Still deliberately not deduplicating by "similar URL" at this stage (unchanged from v1) —
  content-level near-duplication is handled explicitly in §6, not conflated with URL dedup.

---

## 6. HTML/content hashing and near-duplicate policy

Substantially revised. v1 computed one exact hash and deferred near-duplicate detection to
Phase 4; per the review and the approved decision, this is a required correction, not a
nice-to-have, because snapshots go offline and near-duplicate evidence cannot be recovered
later.

- `[REQUIRED]` **Three hashes, computed at collection time:**
  - `raw_content_sha256` — `sha256` of the **raw wire bytes** `fetch_url` received, before
    decoding. Lets encoding-related corruption be detected later (a mis-detected charset that
    silently produces replacement characters in the decoded string would otherwise be
    invisible — this hash is the check).
  - `html_sha256` — `sha256` of the **decoded HTML string** exactly as `fetch_url` returns it
    (`html.encode("utf-8")`). This is what gets stored to disk (§11) and is the field name kept
    for continuity with v1.
  - `[APPROVED — decision 2]` `normalized_html_sha256` — `sha256` of the decoded HTML after:
    stripping `<script>`, `<style>` and comment nodes; collapsing whitespace runs; removing
    attributes matching common dynamic-token patterns (long hex/base64 strings, CSRF/session/
    nonce attribute names). Computed **during collection**, not deferred: phishing kits are
    reused verbatim across many domains with only a victim token, timestamp or swapped logo
    differing, which defeats `html_sha256` but not `normalized_html_sha256`. Full fuzzy/MinHash-
    based kit clustering stays `[DEFERRED]` to Phase 4 (a genuinely more involved technique),
    but this cheap normalized hash does not wait, because it can only be computed while the
    snapshot exists.
- `[REQUIRED]` **Duplicate canonicalization is deterministic, not completion-order-dependent.**
  v1's "first row with a given hash wins" is racy under §3's concurrent crawling — completion
  order under `asyncio` scheduling varies run to run and machine to machine. **Correction:**
  canonicalization is computed **after** collection, over the **full accumulated pool** (not
  per-run), by sorting candidates sharing a hash (`html_sha256` or `normalized_html_sha256`) by
  `(normalized_url, collection_run_date)` ascending and keeping the first — a rule that depends
  only on the data, never on crawl timing. This computation lives in the derived selection
  artifact (§11/§12), not the capture manifest, so it can be recomputed whenever the pool grows
  without touching immutable history.
- **Purpose 2 (snapshot integrity)** unchanged from v1: hashes let a stored file be verified
  without re-crawling.

---

## 7. Registered-domain grouping

- `[APPROVED — decision 9]` **`tldextract` with a pinned offline Public Suffix List snapshot.**
  By default `tldextract` can fetch and cache the live PSL at runtime; if that happens on
  different machines or dates, grouping keys silently drift between collection runs, which would
  break the freeze-on-assign guarantee in §8. **Resolved:** use `tldextract` in offline mode
  against a vendored PSL snapshot (`suffix_list_urls=()` with a committed snapshot file, or an
  explicitly pinned cached copy), record `psl_snapshot_date` per dataset version (§13), and use
  exactly one snapshot per version — never re-resolve mid-version.
- `[APPROVED — decision 9]` **Fallback for IP-hosted and unresolvable URLs: literal host.**
  `tldextract` returns an empty/`None` registered domain for a bare IP host (a real, distinct
  sub-population — `dataset_loader`'s existing `having_ip_address` feature exists precisely
  because of this). **Resolved:** when no registered domain resolves, use the literal host
  string (the IP itself, or the unresolvable name) as the grouping key instead of letting all
  such URLs collide on an empty-string key.
- `[REQUIRED]` **`final_registered_domain` is also recorded**, computed from `fetch_url`'s
  `final_url` (post-redirect), separately from the source URL's registered domain. See §8 for
  how this is used as the grouping key and how a source/final mismatch is handled.

---

## 8. Train/validation/test split strategy

Substantially revised for determinism and freeze semantics.

- `[APPROVED — decision 3]` **Grouping key is `final_registered_domain`; source/final mismatch
  is excluded by default and logged.** v1 grouped by the source URL's registered domain,
  computed before redirects, while the *content* comes from wherever `fetch_url` actually landed
  (`final_url`) — meaning the "no registered domain spans two splits" guarantee could hold on
  paper while the same actual content host spans splits in practice (e.g. a phishing URL
  redirecting into an unrelated benign host, or a Tranco apex redirecting to a third-party SSO
  domain). **Resolved:** the grouping key is `final_registered_domain` when the crawl succeeded
  (falling back to the source `registered_domain` when the URL was never successfully fetched,
  since there is then no `final_url` to use). When `final_registered_domain` differs from the
  source `registered_domain` on a successful crawl, the row is flagged
  (`domain_redirect_mismatch: true`) and **excluded from the modelling pool by default**, with
  the count logged in the dataset card (§14).
- `[APPROVED — decision 4]` **Domain-level label-conflict detection: exclude both sides, log.**
  v1 assumed phishing and benign domains are "disjoint by construction" — not true in general
  (Tranco includes large hosting/blogging/user-content platforms; a phishing URL on a subdomain
  of such a platform collapses to the same `registered_domain` as a Tranco-sampled benign URL on
  it). **Resolved:** after collection, before splitting, assert no `registered_domain` (using
  §7's grouping key) carries both labels among eligible rows; on conflict, exclude *both* sides
  of that domain group from the modelling pool and log the conflict (count and example domains)
  in the dataset card — a generated check, not a manual one.
- `[APPROVED — decision 5]` **Freeze-on-assign: split membership never changes once written.**
  v1 regenerated `splits/*.txt` in full whenever the manifest grew, with no freeze rule — a
  re-run over a larger pool could move previously-assigned domain groups between splits, so a
  later dataset version's `test.txt` would not be a safe extension of an earlier version's,
  silently invalidating any experiment already run against that earlier test set. **Resolved:**
  once a domain group's split assignment is written and tagged as part of a dataset version
  (§13), it is never moved. Regenerating splits for a later version only **adds** assignments
  for newly-collected, previously-unseen domain groups; every prior assignment is carried
  forward unchanged. `git diff` between two versions' selection files shows only additions.
- `[RECOMMENDED]` **Deterministic bin-packing input order, stated explicitly.** Domain groups are
  sorted by `(label, registered_domain, group_size)` — size descending — before the seeded
  greedy assignment runs, so the algorithm's input order (and therefore its output, given the
  same seed) is fully specified, not merely "seeded" in the abstract.
- `[RECOMMENDED]` **Benign second-page selection is made reproducible.** v1's "first same-domain
  login link found on the homepage" step has no stated ordering and depends on homepage content
  that can change between runs. **Correction:** the link selection rule is *document order*
  (first matching link encountered in the parsed homepage HTML, by DOM position), and the
  manifest records `discovered_from` (the homepage URL) and the anchor's `href`/path, so the
  choice is auditable even though the homepage itself may differ next time.
- Ratio (60/20/20) and the "two independent grouped splits, phishing and benign" structure are
  unchanged from v1 — not in dispute (see closing note in the Approved decisions list).

---

## 9. Class balance

- `[APPROVED — decision 8]` **Benign sampling: rank-progressive, without replacement, rank-
  stratified across runs.** v1 sampled benign URLs each run to match that run's phishing yield
  from the top of Tranco, but Tranco's top ranks are near-static day to day — a second run would
  re-sample largely the same domains, find them `already_collected` (§5), and contribute close
  to nothing, drifting the dataset steadily more phishing-heavy over multiple runs. It also
  concentrated the benign class in a few dozen mega-brand/CDN/consent-page domains, an
  unrepresentative distribution. **Resolved:** track the cumulative set of Tranco ranks/domains
  already sampled (across all runs, stored alongside the manifest); sample new benign URLs
  rank-progressively **without replacement** from the unused remainder, **stratified across rank
  bands** (e.g. 1-100, 101-1,000, 1,001-10,000, 10,001-100,000, 100,001-1,000,000), drawing
  proportionally from each band rather than exhausting the top before moving down.
- `[REQUIRED — as a measurement, not a design change]` **Crawl failure is label-correlated, and
  this must be reported, not left implicit.** Phishing URLs die fast; benign Tranco URLs mostly
  don't. Restricting the modelling pool to eligible `ok` rows therefore selects a systematically
  different population per class — a survivorship bias v1's per-`error_type` reporting did not
  surface, because it wasn't cross-tabulated by label. **Correction:** the dataset card (§14)
  reports a **label x crawl_status matrix** (and label x `robots_result`), plus feed-to-crawl
  latency using PhishTank's own `verification_time` (already captured in `source_metadata`).
- `[OPTIONAL]` One sentence in the dataset card: a roughly-balanced research dataset encodes a
  class prior far from real-world deployment prevalence; any evaluation claim built on it should
  be scoped accordingly. Not a Phase 3 design change.

---

## 10. Failed/invalid/ineligible URL handling

Rewritten to add the eligibility gate (the review's top-priority finding, approved decision 1)
and the corrected retry rule from §5 (approved decision 6).

- `[APPROVED — decision 1]` **Eligibility gate, applied after a technically-successful fetch.**
  `fetch_url` returning `status: "ok"` only means the HTTP transaction completed — it says
  nothing about whether the response is usable content. Left as v1 had it, a phishing URL whose
  domain expired and now serves a registrar "domain for sale" page (HTTP 200) would be stored as
  a `label=1` snapshot of entirely benign parked-page content; symmetrically, a benign URL that
  hits a temporary block would be stored with the block page as its content. **Resolved:** a row
  is only **eligible** for the modelling pool when *all* of the following hold (the exact
  predicate is defined once, in §16, not reimplemented per consumer):
  - `crawl_status == "ok"` (the HTTP transaction completed)
  - `200 <= http_status < 300`
  - the decoded HTML is non-empty after stripping whitespace
  - `content_type` is HTML-like (matches `fetch_url`'s own existing textual-content check)
  Rows failing any of these are still recorded (never dropped) but are excluded from splitting
  and from any modelling use.
- `[REQUIRED]` **Expanded, explicit status vocabulary**, replacing v1's shorter list:

  | Outcome | `crawl_status` | Eligible? | Notes |
  |---|---|---|---|
  | 2xx response, non-empty HTML-like body | `ok` | Yes (pending dedup/conflict checks) | Snapshot stored |
  | 2xx response, empty body | `ok` | **No** | New: `html.strip()` is empty; flagged, not silently included |
  | 2xx response, non-HTML content type | `ok` | **No** | New: e.g. an image/PDF-serving URL; `html` is `""` per `fetch_url`'s own textual-content check |
  | Non-2xx final status after redirects | `ok` | **No** | New: `http_status` recorded but `eligible=false` — a 403/404/5xx "successful fetch" of an unusable page is no longer silently `ok`-and-eligible |
  | `fetch_url` returned `status: "error"` | the exact `error_type` (`timeout`, `connection_error`, `ssl_error`, `too_many_redirects`, `content_too_large`, `invalid_url`, `error`) | No | Retried once per §3 for `timeout`/`connection_error` only; **may be retried again in a later run** (§5) |
  | Blocked by `robots.txt` | `robots_disallowed` | No | Not crawled at all; `robots_result` records why |
  | Already collected **and eligible** in a prior run | `already_collected` | N/A (prior row stands) | Only applies when the prior row was `ok` **and** eligible, per §5 |
  | Malformed/unparseable source-feed row | `source_parse_error` | No | Raw offending line saved to the run log |

- `[REQUIRED]` A per-run collection summary reports counts by *eligibility*, not just by
  `crawl_status`, feeding directly into §9's required label x crawl_status matrix.
- `[RECOMMENDED]` **Bot/challenge-page detection.** A subset of `ok` + `200` + eligible rows can
  still be a Cloudflare/Akamai interstitial rather than real page content (common on Tranco top
  sites when crawled with a non-browser research UA). A cheap heuristic pass (known challenge-
  page marker strings, near-empty `<body>` relative to script size, `cf-browser-verification`
  and similar tokens) sets `bot_challenge_suspected: true`. **Not auto-excluded** — flagged for
  human review instead, reported as a count in the dataset card.
- `[RECOMMENDED]` **Meta-refresh recorded, cloaking otherwise deferred.** `fetch_url` follows
  HTTP-level redirects only. A kit using `<meta http-equiv="refresh">` to hop to the real
  phishing content, or server-side cloaking to a differing UA, produces a label/content mismatch
  nothing here can fully correct. **The cheap part:** record `meta_refresh_detected: true` when
  such a tag is present in the stored HTML. **Full UA-differential cloaking detection is
  `[DEFERRED]`** (would need a second fetch with a browser-like UA, out of scope for a GET-only
  research crawler) — stated as a named limitation in the dataset card (§14).

---

## 11. Snapshot storage structure

Revised for content-addressed storage, the manifest/derived-artifact split, and SSL/TLS capture.

```
data/
  raw/
    feeds/
      phishtank_2026-10-01.csv          # local only, not committed (see §2)
      openphish_2026-10-01.txt
      tranco_2026-10-01_<listid>.csv
      run_2026-10-01_summary.json       # per-run counts: eligibility, label x status, tls capture rate
    html/
      <html_sha256>.html                # content-addressed: identical content across different
                                         # URLs (e.g. copies of the same phishing kit) shares one
                                         # file; a URL's manifest row points to this file via
                                         # html_snapshot_path, keyed by the row's own html_sha256
  manifest.csv                          # IMMUTABLE capture manifest -- append-only, one row per
                                         # attempt, collection-time facts only (see 12a)
  derived/
    selection_v1.csv                    # DERIVED, regenerated per dataset version: eligibility,
    selection_v2.csv                    # duplicate/near-duplicate canonicalization, label-conflict
    ...                                 # flags, split assignment (see 12b)
  splits/
    train.txt / val.txt / test.txt      # generated FROM the current derived selection artifact
  feed_digests/
    phishtank_2026-10-01.json           # {endpoint (redacted), timestamp, sha256, row_count}
    openphish_2026-10-01.json
    tranco_2026-10-01.json
  backups/
    run_2026-10-01_manifest.sha256      # checksums for that run's out-of-band archive (§19);
                                         # the archive itself lives off-machine, not in the repo
  DATASET_CARD.md                       # see §14
```

- `[APPROVED — decision 10]` **Snapshot files are content-addressed by `html_sha256`, not by URL
  hash.** v1 named files by `sha256(normalized_url)` so that "re-crawling the same URL overwrites
  deterministically" — but this contradicts v1's own other claims: once a previously-failed URL
  is re-attempted and succeeds with content different from what an earlier crawl of that same
  URL produced, overwriting the URL-keyed file destroys the earlier run's evidence, and that
  earlier row's `html_sha256` no longer matches the file it points to — a silent, after-the-fact
  provenance failure. **Resolved:** name files by the content hash itself. Every distinct piece
  of HTML ever collected gets one permanent file; a manifest row's `html_snapshot_path` is
  always correct, forever, regardless of how many times the source URL is later re-crawled with
  different content. This also makes exact-duplicate content (the same phishing kit deployed on
  many domains) visibly share one file on disk.
- `[APPROVED — decision 12]` **Manifest split into an immutable capture manifest and a derived
  selection artifact.** v1 called `data/manifest.csv` "append-only, never rewritten in place"
  while also specifying that its `split` and `duplicate_content_of` columns get filled in
  *after* collection — necessarily rewriting rows, contradicting the immutability claim.
  **Resolved:** `data/manifest.csv` holds only collection-time facts (everything `fetch_url`
  returns, plus source/label/hashes/TLS info) and is genuinely never rewritten — only appended
  to. Every derived judgment — eligibility, exact/near-duplicate canonicalization, domain-level
  label-conflict exclusion, and split assignment — lives in a separate
  `data/derived/selection_v<N>.csv`, one per dataset version, regenerated from the manifest plus
  the version's seed and PSL snapshot. "Which inclusion rules did experiment X use" is then
  answerable by naming a version file.
- **`.gitignore` / commit decisions unchanged from v1's proposal:** `data/raw/` stays
  `.gitignore`d (not applied yet — still a proposal); `data/manifest.csv`, `data/derived/
  selection_v*.csv`, `data/splits/`, `data/feed_digests/`, `data/backups/*.sha256` and
  `data/DATASET_CARD.md` are proposed as committed artifacts. **[SUSPENDED for the manifest, derived
  selections, splits and feed digests — see the amendment at the top of this document.]**
- `[APPROVED — decision 10]` **Out-of-band backup for `data/raw/html/` is mandatory.** This
  directory is `.gitignore`d and lives on a single machine, yet the phishing snapshots inside it
  are the *only* irreplaceable artifact this project produces — live pages vanish from the web
  within hours to days and can never be re-collected once gone. **Resolved:** each collection
  run's procedure includes producing a checksummed archive (e.g. `tar.gz` of that run's new
  files, plus a `sha256sum` manifest of its contents, committed under `data/backups/*.sha256` so
  the checksums themselves are versioned even though the archive isn't) and copying the archive
  to storage independent of the working machine (institutional storage, an external drive, or an
  encrypted cloud backup — medium is the team's call; the step itself is mandatory). See §19.

---

## 12a. Capture manifest schema (immutable)

`data/manifest.csv` — one row per **collection attempt**, append-only, never rewritten:

| Column | Type | Description |
|---|---|---|
| `url` | str | Original URL as given by the source |
| `normalized_url` | str | Normalized form (§5) |
| `source` | str | `phishtank`, `openphish`, or `tranco`; `;`-joined if seen in more than one |
| `source_metadata` | JSON str | Source-specific fields (`phish_id`, `verification_time`, Tranco `rank`/`list_id`) |
| `label` | int (0/1) | As assigned by source at collection time (§4) |
| `collection_run_date` | date (ISO 8601) | Which run attempted this URL |
| `retry_count` | int | 0 for a first attempt; incremented for a same-run retry (§3) |
| `crawl_status` | str | `ok` or one of §10's failure/skip codes |
| `crawled_at` | ISO 8601 datetime or empty | From `fetch_url` |
| `final_url` | str or empty | From `fetch_url` |
| `registered_domain` | str | From the **source** URL, via pinned `tldextract` (§7) |
| `final_registered_domain` | str or empty | From `final_url`, via pinned `tldextract` (§7/§8) |
| `domain_redirect_mismatch` | bool | `final_registered_domain != registered_domain` on a successful crawl (§8) |
| `http_status` | int or empty | From `fetch_url` |
| `redirect_count` | int or empty | From `fetch_url` |
| `content_type` | str or empty | From `fetch_url` |
| `html_length_bytes` | int or empty | Raw wire body length (§0) |
| `decoded_text_length` | int or empty | Length of the decoded `html` string (§0's raw-vs-decoded distinction) |
| `visible_text_length` | int or empty | Length of `fetch_url`'s `visible_text` (§16 rendering-gap measurement) |
| `dom_node_count` | int or empty | Count of parsed elements (cheap, at collection — §16) |
| `script_count` | int or empty | Count of `<script>` tags (§16) |
| `raw_content_sha256` | str or empty | Hash of raw wire bytes (§6) |
| `html_sha256` | str or empty | Hash of the decoded HTML string; also the snapshot filename (§6/§11) |
| `normalized_html_sha256` | str or empty | Hash of normalized HTML for near-dup detection (§6) |
| `html_snapshot_path` | str or empty | `data/raw/html/<html_sha256>.html`, empty if not `ok` |
| `error_type` / `error_message` | str or empty | From `fetch_url`'s error dict |
| `robots_result` | str | `allowed` / `disallowed` / `no_robots_file` / `unreachable` (§3) |
| `meta_refresh_detected` | bool | §10 |
| `bot_challenge_suspected` | bool | §10 |
| `tls_captured` | bool | Whether a TLS metadata probe was attempted (`https://` URLs only) (§20) |
| `tls_version` | str or empty | Negotiated TLS protocol version, when `tls_captured` (§20) |
| `certificate_subject` | str or empty | Leaf certificate subject, when `tls_captured` (§20) |
| `certificate_issuer` | str or empty | Leaf certificate issuer, when `tls_captured` (§20) |
| `certificate_self_signed` | bool or empty | Heuristic (`issuer == subject`), when `tls_captured` (§20) |
| `certificate_not_after` | date or empty | Certificate expiry, when `tls_captured` (§20) |
| `discovered_from` | str or empty | For a Tranco "second page": the homepage URL it was found on (§8) |
| `feed_to_crawl_latency_seconds` | float or empty | `crawled_at` minus the source's own listing/verification timestamp, where available (§9) |
| `collection_tool_version` | str | git SHA of the collection code at run time |
| `normalization_version` | str | Version tag of the URL/HTML normalization logic used (so a later change to normalization rules doesn't silently reinterpret old rows) |
| `psl_snapshot_date` | date | Which pinned PSL snapshot was used for this row's domain fields (§7) |

## 12b. Derived selection artifact schema (per dataset version, regenerated)

`data/derived/selection_v<N>.csv` — one row per `normalized_url` **considered for this
version** (not per attempt; joins back to the capture manifest by `normalized_url`, using the
most recent `ok` capture row for that URL as of this version's cutoff date):

| Column | Type | Description |
|---|---|---|
| `normalized_url` | str | Join key into `manifest.csv` |
| `dataset_version` | str | e.g. `v1` |
| `source_collection_run_date` | date | Which capture row this selection is based on |
| `registered_domain_used` | str | The grouping key actually applied (`final_registered_domain`, falling back to source per §8) |
| `eligible` | bool | §16's predicate |
| `duplicate_of_normalized_url` | str or empty | Canonical row for this content cluster, if any (§6) |
| `duplicate_basis` | str or empty | `exact` (`html_sha256`) or `near` (`normalized_html_sha256`) |
| `label_conflict` | bool | This row's `registered_domain_used` carries both labels among eligible rows (§8) |
| `split` | str or empty | `train`/`val`/`test`; empty if excluded (ineligible, duplicate, or label-conflicted) |
| `split_frozen_at_version` | str | The dataset version in which this row's split was first assigned — never changes on later regeneration (§8) |

---

## 13. Dataset versioning

- `[REQUIRED]` **A dataset version is the pair `(derived/selection_v<N>.csv, DATASET_CARD.md)`,
  tagged together** (e.g. `dataset-v1-2026-10-01`), same git-tag pattern as the Phase 0 baseline
  tag. This replaces v1's looser "version = a manifest-updating commit" framing, since the
  manifest itself is no longer what changes per version (it only grows) — the *selection* is
  what's versioned.
- `[REQUIRED]` **The capture manifest is not versioned per tag** — it is the continuously-
  growing raw record, referenced by date range, not by version number.
- `[REQUIRED]` Each new version's derived selection file only **adds** rows/assignments for
  domain groups not previously split; it never edits a prior version's `split` values (§8).
  `git diff` between two `selection_v<N>.csv` files should show only additions in the common
  case.
- `[REQUIRED]` **One pinned PSL snapshot per version** (§7); `psl_snapshot_date` recorded in
  both the capture manifest (per-row) and the dataset card (per-version, the snapshot actually
  used when that version's selection was computed).
- Raw HTML files remain un-versioned individually (content-addressed, §11); a version's
  `html_sha256` values are how a re-generated or re-fetched snapshot is verified against what
  that version originally saw.

---

## 14. Dataset card contents (`data/DATASET_CARD.md`)

Generated from `manifest.csv` + the version's `selection_v<N>.csv` + run summaries — never
hand-typed — per `CLAUDE.md` §14 rule 1. Revised list:

1. **Collection date(s)** — unchanged from v1.
2. **Sources** — endpoint URLs with secrets redacted per §18 (**required change from v1**, which
   would have committed the literal PhishTank app key once one exists); PSL snapshot date (§7);
   feed digests (§1/§11) instead of raw feed content.
3. **Counts** — attempted / succeeded / failed by `error_type` / `robots_disallowed` /
   `already_collected`, split by eligibility, phishing vs benign, unique vs exact-duplicate vs
   near-duplicate (§6).
4. **Label x crawl-status matrix** and label x `robots_result` matrix (§9/§3) — makes the
   survivorship bias and the robots-policy cost measurable, not assumed away.
5. **Class balance** — realized ratio, unchanged framing from v1.
6. **Split sizes** — per split, per version, confirming (a) no registered domain (using the §8
   grouping key) spans two splits, and (b) no domain carries a label conflict among included
   rows — both generated assertions.
7. **Filtering/exclusion decisions** — exact and near-duplicate exclusions (§6), label conflicts
   (§8), `domain_redirect_mismatch` exclusions (§8), `robots_disallowed`, ineligible rows by
   reason (empty body / non-HTML / non-2xx / bot-challenge-suspected).
8. **Rendering-gap measurement** — median/quantile `html_length_bytes`, `decoded_text_length`,
   `visible_text_length`, `dom_node_count`, `script_count`, each broken down by label — makes the
   "benign pages are more often thin, JS-rendered SPAs than phishing kits are" asymmetry (§16)
   measurable rather than an unstated assumption a model could exploit unnoticed.
9. **Known limitations**, expanded from v1: label-trust caveats; OpenPhish's feed-size ceiling;
   single-retry-per-run policy (mitigated by the §5 cross-run retry correction, but same-run
   retries are still capped at one); no visual/screenshot data; no manual verification pass;
   **no browser-rendered content** (§16, an explicit, measured limitation); **no cloaking
   detection beyond meta-refresh** (§10). SSL/TLS metadata **is** captured (§20) — its capture
   success rate (share of `https://` rows with `tls_captured=True`) is reported here instead of
   being listed as a limitation.
10. **Canonical modelling-view definition** — the exact eligibility predicate from §16, stated
    once, so every later phase is provably reading the same rows.
11. **Reproducibility instructions**, unchanged in spirit from v1: exact commands to re-run
    collection and regenerate a new version's selection from a given manifest + PSL snapshot +
    seed.
12. **Redaction confirmation** — a one-line statement (generated by checking the committed
    artifacts for known secret patterns before commit, §18) that no credential appears in the
    committed card, summaries, or logs.
13. **Backup confirmation** — that the out-of-band backup (§11/§19) for this version's
    contributing runs was completed, with a pointer to where (not the archive itself).

---

## 15. Expected dataset size and storage requirements

Unchanged estimate from v1 (~300-800 phishing, matching benign, less than or equal to ~3.2GB
worst case for raw HTML), with one addition:

- `[NOTE]` Content-addressed storage (§11) means actual disk usage will likely be **somewhat
  below** the naive per-URL estimate, since exact-duplicate phishing-kit copies across different
  domains now share a single file rather than each getting their own copy.

---

## 16. Eligibility gate and the canonical modelling view

`[APPROVED — decision 1]` Consolidates §4/§6/§10/§14's eligibility logic into one place, written
once and referenced everywhere else, so no phase (including this plan's own split/card
generation) reimplements it slightly differently:

```
eligible =
    crawl_status == "ok"
    AND 200 <= http_status < 300
    AND len(html.strip()) > 0
    AND content_type is HTML-like   # same check fetch_url already applies internally
    AND duplicate_of_normalized_url is empty   # this row IS the canonical copy, or has none
    AND label_conflict is False
    AND domain_redirect_mismatch is False
```

A row additionally needs `split` to be non-empty (§8) before any experiment actually reads it —
`eligible` and `split-assigned` are tracked as separate booleans/columns (§12b) so "eligible but
not yet split" (e.g. a brand-new domain group before the next version regenerates) is
distinguishable from "ineligible."

`[REQUIRED]` This predicate is implemented once, as a single shared function, called by both the
split-generation script and the dataset-card generator (§14 item 10) — not copy-pasted, so a
future change to the rule can't silently diverge between the two consumers.

---

## 17. Bot-challenge and cloaking detection

`[RECOMMENDED / DEFERRED — see breakdown]` Covered inline above (§10); consolidated here for
visibility:

- `[RECOMMENDED]` `bot_challenge_suspected` flag via marker-string/near-empty-body heuristic —
  flagged for review, never auto-excluded (avoids content-derived-label leakage).
- `[RECOMMENDED]` `meta_refresh_detected` flag — cheap, recorded at collection time.
- `[DEFERRED]` Full user-agent-differential cloaking detection (a second fetch with a
  browser-like UA to compare against the research UA's response) — meaningfully more machinery,
  out of scope for Phase 3's GET-only crawler; named as a limitation in §14 rather than silently
  absent.

---

## 18. Secret hygiene

`[REQUIRED]`

- No API key or app key (`PHISHTANK_APP_KEY` or any future addition) is ever written into any
  **committed** artifact: `DATASET_CARD.md`, `feed_digests/*.json`, run summary JSON, or any log
  file kept under version control. Local-only files (`data/raw/feeds/*`, not committed) may
  contain the real key incidentally, since they're `.gitignore`d — but generation of every
  *committed* artifact passes recorded endpoint URLs through a redaction step first (replace any
  `app_key=...` or similar query parameter with `app_key=REDACTED`).
- Before a commit that touches any dataset artifact, a redaction check scans the changed files
  for known secret-shaped patterns (the configured env var names, generic high-entropy query
  parameters) and fails the commit step if a match is found, rather than relying on manual
  review alone.
- Applies identically whether collection is running anonymously or with a `PHISHTANK_APP_KEY`
  configured (§1, approved decision 11) — the redaction step doesn't need to know which case it
  is; it just never lets a key-shaped string reach a committed file.

---

## 19. Out-of-band backup procedure

`[APPROVED — decision 10, operational, not code]` Restated from §11 for visibility as its own
section, since the review specifically calls out that this is easy to treat as optional cleanup
and it must not be:

1. After each collection run, produce a checksummed archive of that run's new files under
   `data/raw/html/` (e.g. `tar.gz` plus a `sha256sum` listing).
2. Copy that archive to storage independent of the machine that ran collection (institutional
   storage, an external drive, or an encrypted cloud backup — medium is the team's choice).
3. Commit the `sha256sum` listing itself under `data/backups/` (small, no restricted content) so
   the checksums are versioned even though the archive is not.
4. Record in the run summary that the backup step completed, and where (a label, not the
   archive's actual location if that's sensitive) — this is what §14 item 13 reports.

This step exists because phishing snapshots cannot be re-collected once the source page goes
offline (typically within hours to days); the manifest and hashes alone prove *that* something
was seen, not what it contained, if the only copy is lost.

---

## 20. SSL/TLS metadata

`[APPROVED — decision 14: capture basic SSL/TLS metadata during collection]`

`CLAUDE.md` §15 proposes capturing SSL/TLS metadata (certificate subject/issuer, self-signed
status, TLS version) at crawl time as a "cheap, genuine" signal; v1 omitted it from Phase 3
without discussion. The review's point, now acted on: unlike most other deferrable items, this
one cannot wait — phishing hosts go offline, and TLS facts about a page that no longer exists
can never be captured retroactively.

- **Mechanism (Phase-3-only code, not a `crawler/fetcher.py` change):** a small, separate helper
  (e.g. `dataset/tls_probe.py`) opens a direct TLS connection to `host:443` using Python's
  standard-library `ssl`/`socket` modules and reads the leaf certificate's subject, issuer, and
  expiry, plus the negotiated protocol version — independent of, and not blocking, the main
  `fetch_url` HTML fetch. This is a parallel probe, not a modification of Phase 2's crawler.
- **Scope:** attempted only for `https://` URLs. For `http://` URLs, `tls_captured = False` and
  the TLS fields are left empty — not a failure, just not applicable.
- **Failure handling:** any error during the probe (timeout, handshake failure, certificate
  parse error) sets `tls_captured = False` with the fields left empty; it never blocks or delays
  the main HTML fetch, and it is not retried beyond whatever this probe's own short timeout
  allows within the same run (a failed TLS probe on a URL that otherwise crawled fine does not
  make that row ineligible — TLS capture is additive metadata, not part of §16's eligibility
  predicate).
- **Reporting:** the dataset card (§14 item 9) reports the TLS-capture success rate among
  `https://` rows, so gaps are visible rather than silently assumed complete.
- Columns added to the capture manifest: `tls_captured`, `tls_version`, `certificate_subject`,
  `certificate_issuer`, `certificate_self_signed`, `certificate_not_after` (§12a).

---

## 21. Testing and acceptance criteria

`[REQUIRED, new section — criteria only; no test code exists yet, per this plan's own scope]`
Phase 3 is not declared complete until every item in §21.1 passes as an automated check and
every item in §21.2 has been manually confirmed for that run. §21.1 items are properties a test
suite can assert without a person looking at anything; §21.2 items require human judgment or
access to something outside the repository (an off-machine backup, a chosen PSL vendor file)
and cannot be automated away — conflating the two would let an operational gap (e.g. a skipped
backup) hide behind a green test run.

### 21.1 Automated assertions (test suite)

Each of these must hold as a property the test suite checks directly, using local fixtures
(never real PhishTank/OpenPhish/Tranco traffic — same no-real-network rule already in force for
the Phase 2 crawler tests, §17 of the Phase 2 report):

1. **Deterministic clean-environment run.** Given a fixed set of fixture "feed" responses and a
   fixed seed, running collection twice from a clean environment produces byte-identical
   `manifest.csv` rows (ignoring genuinely time-varying fields like `crawled_at`) and identical
   `selection_v<N>.csv` output. This is the plan's core reproducibility claim, made checkable.
2. **Feed digests generated; secrets redacted.** For a fixture feed download (including one with
   a fake `app_key` in its URL), the resulting feed digest file contains the correct sha256/row
   count and **never** contains the literal key — the redaction rule (§18) is asserted against a
   known secret-shaped input, not just described.
3. **Capture-row schema completeness.** Every row written to `manifest.csv` has every column
   listed in §12a populated with the correct type (or explicitly empty where "empty" is a valid
   state per that column's description) — no silently-missing provenance field.
4. **Single canonical eligibility predicate.** A unit test exercises §16's `eligible` function
   directly against constructed rows covering every branch (non-2xx, empty body, non-HTML type,
   duplicate, label-conflict, domain mismatch) and confirms the expected boolean; a static check
   (e.g. a single grep/import-graph check) confirms the split-generation script and the
   dataset-card generator both call that one function rather than each having their own copy.
5. **Deterministic duplicate canonicalization.** Given the same set of capture rows sharing a
   hash, processed in randomized/shuffled order across repeated test runs, the same row is
   always selected as canonical (§6's `(normalized_url, collection_run_date)` sort), independent
   of input order.
6. **No included registered domain spans two splits.** A generated assertion over a fixture
   `selection_v<N>.csv`: for every `registered_domain_used` among rows with a non-empty `split`,
   all such rows share the same `split` value.
7. **No label-conflicted domain enters the modelling pool.** A generated assertion: no row with
   `label_conflict = true` has a non-empty `split`.
8. **Frozen split assignments survive version regeneration.** A test that builds `selection_v1`
   from a fixture manifest, then appends new fixture rows and rebuilds `selection_v2`, and
   asserts every row present in `v1` with a `split` keeps the identical `split` value in `v2`
   (§8/§13's freeze-on-assign guarantee, checked directly rather than assumed from the process
   description).
9. **Retry without overwrite.** A test simulates a URL failing in one fixture run and succeeding
   in a later fixture run, and asserts both capture rows exist in `manifest.csv` afterward (the
   failed row is not deleted or replaced) — §5/§10's retry-history guarantee.
10. **Snapshot hash integrity.** For every `ok` row with a non-empty `html_snapshot_path`, a
    check reads the file at that path and confirms its sha256 equals the row's `html_sha256`.
11. **Dataset card is generated, not hand-typed.** The dataset-card generator is invoked against
    a fixture manifest/selection pair and its output is diffed against a known-correct expected
    card (or checked for a "generated by `<script>` at `<commit>`" marker plus internal
    consistency with the source data) — nothing in `DATASET_CARD.md` is asserted by a value that
    isn't traceable back to the input files.
12. **TLS/robots/crawl-status reporting populates correctly.** Given fixture rows covering each
    `robots_result` value, each `crawl_status`/eligibility combination, and both TLS-captured and
    TLS-not-captured cases, the generated dataset card's label x crawl_status matrix, per-label
    robots-disallow rate, and TLS-capture-success-rate figures match hand-computed expected
    values for that fixture set.
13. **All of the above pass before Phase 3 is declared complete.** This item is the gate itself:
    Phase 3 sign-off requires a single test-suite run (once implemented) showing items 1-12 all
    passing, reported the same way Phase 0-2 reports were (pass/fail counts stated plainly, no
    partial credit implied).

### 21.2 Manual operational checks (not automatable)

These depend on something outside the repository's own logic — human judgment, or state on a
machine/backup medium the test suite cannot inspect — and must be confirmed by a person for
each real collection run, separately from the automated suite above:

- **Out-of-band backup actually exists and is restorable.** §19's archive was produced, copied
  off-machine, and (periodically, not necessarily every run) test-restored to confirm it isn't
  silently corrupt. A test can check that a run's summary *claims* the backup step ran (§14 item
  13); only a person can confirm the archive is actually sitting in the intended off-machine
  location and is openable.
- **PSL snapshot choice is reasonable.** Pinning *a* snapshot (§7/§9 decision) is automatable;
  judging whether the vendored snapshot is current enough for the domains this run actually
  collected is a human call, made once per dataset version, not per row.
- **Flagged rows are actually reviewed.** `domain_redirect_mismatch`, `bot_challenge_suspected`,
  and `label_conflict` rows are *detected and excluded* automatically (§21.1 items 6/7 and the
  domain-mismatch equivalent), but whether the excluded examples reveal a systematic problem
  worth fixing before the next run is a judgment call for a person to make by reading a sample.
- **Secret hygiene beyond known patterns.** The automated redaction check (§18, §21.1 item 2)
  catches known secret-shaped patterns; a person should still glance at a newly-generated
  `DATASET_CARD.md`/run summary before it's committed, since a redaction rule can only catch
  what it was told to look for.
- **`.env`/local key handling.** Confirming a real `PHISHTANK_APP_KEY` (once one exists) never
  ends up in a shell history, a screen share, or a non-`.gitignore`d file is a per-person
  operational habit, not something this repository's tests can verify.

---

## What this plan deliberately does NOT do yet

Unchanged from v1's list, plus:
- No PSL snapshot has been pinned or vendored yet (§7).
- No capture-manifest/derived-selection-artifact separation has been implemented yet (§11/§12).
- No backup infrastructure, redaction-check tooling, or TLS probe has been built yet
  (§18/§19/§20).
- `requirements.txt`, `.gitignore` and `crawler/fetcher.py` remain unmodified — every
  correction above is a design change to *new* Phase 3 code, not a change to Phase 2.

---

## Approved decisions

All 14 items below were reviewed and approved. Each remains a **design decision** — nothing is
implemented, downloaded, or crawled as a result of this approval; implementation is a separate,
later step.

1. **Eligibility gates (§10/§16):** 2xx + non-empty HTML + HTML-compatible content type required
   for a row to enter the modelling pool; explicit status codes for everything else. **Approved
   as specified.**
2. **Near-duplicate policy (§6):** `normalized_html_sha256` computed during collection, not
   deferred to Phase 4. **Approved as specified.**
3. **Grouping key and redirect-mismatch policy (§7/§8):** group by `final_registered_domain`;
   source/final domain mismatch excluded by default and logged. **Approved as specified.**
4. **Label-conflict rule (§8):** domains carrying conflicting eligible labels are excluded from
   the modelling pool and logged. **Approved as specified.**
5. **Split freeze semantics (§8/§13):** domain split assignments frozen across dataset versions;
   later versions only add. **Approved as specified.**
6. **Cross-run retry rule (§5/§10):** failed URLs retried in later runs; every previous attempt
   preserved, never overwritten. **Approved as specified.**
7. **`robots.txt` policy (§3):** honored uniformly for both labels; per-label disallow rates
   reported in the dataset card. **Approved as specified.**
8. **Benign multi-run sampling (§9):** rank-progressive, without-replacement, rank-stratified
   sampling. **Approved as specified.**
9. **`tldextract`/PSL configuration (§7):** pinned offline PSL snapshot; literal host used as
   the grouping key for IP-hosted/unresolved cases. **Approved as specified.**
10. **Snapshot addressing and backup (§11/§19):** content-addressed HTML snapshots
    (`html_sha256`); checksummed out-of-band backups mandatory per run. **Approved as
    specified.**
11. **Secret hygiene (§2/§18):** no secret ever committed; anonymous/rate-limited PhishTank
    collection supported first if no app key is available, key addable later without other
    changes. **Approved as specified.**
12. **Manifest architecture (§11/§12/§13):** immutable capture manifest plus a derived,
    per-version selection/split artifact. **Approved as specified.**
13. **Feed digests vs. raw feeds (§1/§2):** commit feed digests only, not raw feed contents.
    **Approved as specified.**
14. **SSL/TLS metadata (§20):** capture basic SSL/TLS metadata during collection (subject,
    issuer, self-signed heuristic, expiry, TLS version), via a separate lightweight probe, not
    a `crawler/fetcher.py` change. **Approved — resolved as "capture now," not deferred.**

Carried over from v1, not re-opened by this approval:
- **60/20/20 split ratio:** unchanged, not in dispute — only the mechanism underneath it (items
  3-5 above) was the actual risk, and that mechanism is now specified.
