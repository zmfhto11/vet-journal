# Validation record — 2026-09-16 (Asia/Seoul)

## Executed and passed

- Python: `python -m unittest discover -s tests -v` — **31 passed**.
- JavaScript: `node --test tests/frontend.test.mjs` — **8 passed**.
- `node --check web/app.mjs` and `node --check web/core.mjs` — passed.
- `python -m digest.build` — validated both public datasets and produced the static site.
- `python -m tests.live_sources` — fetched **8 actual Europe PMC records** and their **8 PubMed records** from the official APIs.
- `python -m tests.live_e2e` — 16 real source records reconciled to **8 unique papers**, saved/reloaded, and verified no unprocessed records leaked into public JSON.
- `python -m digest.pipeline --collect-only --days 14` — PubMed **71**, Europe PMC **174** source records; **174 unique records** saved. Source health: both ok. No paid AI calls.
- Europe PMC `PMC13549437/fullTextXML` — actual OA body retrieved, **24,034 characters**. It was not sent to AI or published.
- Seven real-paper reference annotations were validated against actual abstract quotations; the offline processing/export test passed. Reference annotations are labelled separately from production AI results.

## Browser checks performed

- Local server returned HTTP 200; application rendered in the Codex browser.
- Search `pyometra` returned 1 matching paper.
- More expanded the reported results and limitations.
- Recommendation star revealed the specific recommendation reason.
- Cat filter returned 2 actual sample papers.
- Adding Full-text reviewed to abstract-only samples displayed the correct empty state.
- Reset restored all 7 sample papers.
- Desktop layout checked at 1440 × 1050.
- Mobile checked at 390 × 844; document width 375 px (excluding scrollbar), no page-level horizontal overflow. Specialty tabs intentionally scroll horizontally.
- Mobile filter open/close and journal selector visibility verified.
- Temporary viewport override reset; preview tab retained.

## Not executed / requires user configuration

- **Actual OpenAI API analysis and semantic accuracy evaluation:** no OPENAI_API_KEY was present. The five requested classification examples are covered by mocked output-contract tests. An opt-in paid `tests.live_ai` script tests those synthetic examples plus actual papers; it has not been run against the API. These are not reported as successful live-model tests.
- **GitHub Actions remote run / GitHub Pages publication:** workspace has no remote repository and no GitHub deployment destination was supplied. Workflow files are ready; deployment is not claimed complete.
- **Official publisher RSS live integration:** adapter exists; no verified feed URLs configured. Sources use official PubMed and Europe PMC only until feeds are added.
- No paywall bypass or publisher-page scraping was used.

## Tested runtime

Python bundled runtime with Pydantic 2.13.5 and tzdata 2026.3. Frontend is plain HTML/CSS/ES modules; no npm runtime dependencies. requirements.txt pins the tested Python library versions.

## Meaning of the 174 stored records

They are **pending candidates**, not 174 clinically eligible or summarized papers. Journals are queried broadly; OpenAI must still screen species, clinical relevance, laboratory-only studies and topic. Processed exclusions remain in canonical state but are omitted from the website. The seven reference summaries are not inserted as processed production analyses and will not bypass later automated screening.

## Follow-up: read markers and Korean typography

- Added reversible, browser-local read markers with DOI/PMID aliases.
- Node frontend suite: **12 passed**, including reload persistence, undo, identifier enrichment, unavailable storage and cross-tab merging.
- JavaScript syntax checks and static build passed; read-state module included in dist.
- Korean text uses Malgun Gothic first, with device-specific fallbacks; refined line height and character spacing.
- Browser visual QA was not repeated for this small follow-up; the existing preview was refreshed.

## Follow-up: incomplete findings in reference summaries

A user identified that the pyometra reference displayed overall survival while the takeaway discussed sepsis, creatinine and antibiotics. The individual sentences were supported by the abstract, but the displayed findings omitted the evidence connecting them. Earlier schema/quotation tests did not establish summary completeness.

Changes:
- Rechecked the pyometra abstract at PubMed (PMID 42716105) and all seven reference summaries against the captured official-source abstracts.
- Restored principal endpoints, null comparisons, harms and relevant subgroup/denominator distinctions.
- Replaced the broad antibiotic-stopping warning with the study's specific perioperative/nonseptic population and outcome scope.
- Moved generation provenance out of research limitations; retained reference-mode disclosure.
- Numbered findings and made source quotations expandable for easier reading.
- Added coverage instructions to the production prompt and rejected numerical headline/takeaway claims absent from displayed results or cohort size.
- Added regression checks for the exact missing clinical topics in these curated references.

Validation: 35 Python tests and 12 frontend tests passed; JavaScript syntax and static build passed. The reference corrections are source-checked annotations, not live API output. No live OpenAI semantic evaluation was run. Neither topic regression tests nor numeric validation prove every generated summary is semantically complete; the prompt change reduces this failure mode but is not a guarantee.

## Follow-up: richer evidence-based overviews and explicit AI interpretation label

- Expanded all seven reference overviews into substantive multi-sentence summaries; added grounded study methods and richer detailed results.
- Diet reference now distinguishes 27 enrolled, 7 withdrawals, 20 analyzed, 14 responders (70%), score changes and 90-day follow-up; it explains the denominator and uncontrolled design.
- Added backward-compatible nullable study_methods to Analysis, included it in numeric grounding and published detail rendering. The legacy one_sentence_summary field now requests 2–4 informative sentences.
- Clinical takeaway visibly states in Korean that it is the AI's discretionary interpretation, not the authors' conclusion.
- Extended integer validation to explicitly spelled-out counts; derived group totals remain rejected. Increased the default output cap to 4800 to accommodate meaningful detail.
- Validation: **38 Python + 12 JavaScript tests passed**; JavaScript syntax and static build passed. Tests include attrition/denominator completeness, legacy data compatibility, unsupported method numerics and spelled-out versus derived counts.
- No paid OpenAI call or live semantic evaluation was performed. Reference improvements do not claim the model's future output is automatically correct. Browser visual QA was not repeated; preview refreshed.

## Follow-up: full-text preference and independent clinical interpretation

- Full-text retrieval is now enabled by default in Python, `.env.example`, and GitHub Actions. Exact DOI/PMID lookup resolves missing PMCIDs. Missing abstract metadata does not block an available full text. Input limit is 120000 characters; oversized or unavailable full text falls back to explicitly labelled abstract evidence without truncation.
- Found and fixed a real XML extraction error: the former HTML-stripping helper interpreted literal inequality signs as tags and removed intervening scientific text. XML text extraction now preserves inequalities, section/paragraph boundaries, table-cell separation, and embedded appendices. Initial probing of the renal paper was repeated after this correction before review.
- Retrieved the official OA XML for PMC13549437 and reviewed its methods, results, tables, discussion, and appendix. Added a source-checked full-text reference annotation with exclusions, nonblinded measurement, missing GFR validation, confounding and exploratory analysis limitations. Source is CC BY 4.0; the attributed text fixture supports grounding regression checks. Images were not quantitatively reanalyzed.
- Europe PMC exact DOI lookups for the original seven references provided no PMCID and only subscription DOI links. These remain abstract-based; no claim is made that no accessible version exists anywhere else. The automatic retriever currently supports Europe PMC XML, not arbitrary publisher PDF repositories.
- All eight clinical takeaways use moderate-length, study-specific interpretation. They are collapsed initially under `AI 임상 해석 보기`, independent of the study-detail panel, with the explicit AI interpretation label retained. Picks open the corresponding interpretation.
- Browser interaction checks passed: all eight interpretations initially hidden, opening one leaves details closed, closing it while details are open leaves details open, ARIA expanded state follows the toggle, and the full-text filter returns exactly the renal paper.
- Automatic OpenAI API analysis and deployment remain unexecuted; this change updates the pipeline and source-checked reference dataset, not paid production output.
- Validation: **44 Python tests + 12 JavaScript tests passed**; JavaScript syntax check and static build passed. New coverage checks inequality/table preservation, identifier resolution, default complete-body input, missing abstract fallback, and actual full-text reference grounding.
