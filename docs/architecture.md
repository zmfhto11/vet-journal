# Veterinary Clinical Journal Digest — architecture

## Phase 1: decisions

Python 3.11+ batch job → validated JSON → HTML/CSS/JavaScript → GitHub Pages.
No database, browser API key, application server, or frontend framework. Node 20+ is only needed for JavaScript checks/tests. Python standard library handles HTTP/XML; Pydantic validates all records and structured AI output.

Repository structure:

```text
config/journals.json          enabled journals, ISSNs, aliases, optional verified RSS URLs
digest/models.py              validated metadata and grounded analysis
digest/sources.py             PubMed, Europe PMC, official RSS, legal OA full text
digest/store.py               atomic state, DOI/PMID aliases and reconciliation
digest/analyze.py             one bounded Structured Outputs API call per new paper
digest/pipeline.py            fault isolation, retries, run status, budget
digest/build.py               validated public projection → dist/
web/                         buildless responsive dashboard
data/state.json              canonical metadata, statuses and analysis checkpoints
data/papers.json              public processed/relevant papers only
tests/                       offline contracts and optional live checks
.github/workflows/           CI, scheduled update, Pages deployment
```

Phase 2: Query all enabled journals, without oncology keyword exclusions. PubMed uses entry/update/publication dates; Europe PMC uses first-index/update/publication dates. Rolling window + persistent last-success checkpoint catches delayed indexing. Page through results. Parse source dates separately; incomplete dates remain null with original date text preserved. Optional publisher RSS detects ahead-of-print and waits for usable abstracts; it does not scrape pages.

Phase 3: Persistent stable internal ID with DOI preferred on first discovery. DOI and PMID aliases merge records even when a new DOI appears later. Conservative title+journal fallback only when one side lacks both identifiers; never coalesce two conflicting known DOIs. Persist every successful analysis before continuing. Rebuild a small public projection, never expose full text or credentials.

Phase 4: One cost-efficient semantic classification + concise Korean summary call using title AND evidence. Cheaper than screening then summarizing every relevant article twice at this scale. Model/configurable quotas enable future optional second stage; no second paid stage in v1. Missing abstracts are retriable failures without an AI call. Optional complete OA XML body only; oversized full text falls back to abstract, never labelled full-text reviewed. Grounded findings require exact source quotes; numerical tokens and sample-size evidence validated. These safeguards cannot prove every medical interpretation; retain source links and cautious interpretations.

Phase 5: Binary recommendation, explicit reason, no star score. Explain clinical applicability and evidence limitations. Today's Picks = up to 3 recommended papers first discovered on the current Asia/Seoul date, never recycled on quiet days.

Phase 6: English original titles + Korean summaries, expandable evidence, overlapping specialty filters, species/journal/design/evidence filters, full field search, honest empty/loading/error states.

Phase 7: Daily 23:17 UTC = next-day 08:17 KST. One update workflow; concurrency avoids state races. New papers and retries are interleaved. Failed article retries are bounded per day but retained for the next schedule; successes are not reanalyzed. Both source failures preserve stored papers and fail the final workflow health check after checkpointing.

Phase 8: Publish only dist/ via GitHub Pages artifact; scheduled job deploys directly because commits created using GITHUB_TOKEN do not trigger another push workflow. Deployment requires a user-owned repository and Pages enabled. Public Pages means public summaries even if the source repository is private (plan dependent); do not store patient data.

Phase 9: Unit/integration fixtures, actual PubMed/Europe PMC smoke collection, optional paid live AI semantic evaluation, browser checks and documented setup. Distinguish mocked tests from live paid API tests in reports.

## Data ownership and reliability

Bibliographic metadata and evidence provenance come from APIs, never from AI. AI returns only analysis. Accepted statuses: pending/processed/failed. Processed irrelevant papers remain in state but are omitted from website. Re-fetch metadata for failed/missing abstracts; metadata enrichment never triggers reanalysis of a processed paper. Atomic same-directory writes use replace; malformed existing state stops the run instead of wiping it. Logs expose stage/id/error type but never URLs containing API keys or secret values. Run status distinguishes last attempt and last successful collection.
