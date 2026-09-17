# Live deployment

- Site: https://zmfhto11.github.io/vet-journal/
- Repository: https://github.com/zmfhto11/vet-journal
- Deployment: https://github.com/zmfhto11/vet-journal/actions/runs/35089598284
- Verified 2026-09-17: deployment completed successfully; site returned HTTP 200; browser rendered all eight reference papers; clinical interpretation toggle opened with the explicit AI label.

## Automation connection — 2026-09-17

The complete reviewed source (Python collector/analyzer, web source, tests, journal configuration, and initial pending state) is now installed in the repository. One-time installation and deployment succeeded: https://github.com/zmfhto11/vet-journal/actions/runs/35165331403. The temporary source archive was removed by the installation job. Root static files remain from the initial publication; current deployments build `web/` into `dist/` and publish only that output.

GitHub Pages now uses **GitHub Actions**, with HTTPS. `.github/workflows/update.yml` runs daily at 23:17 UTC / 08:17 Asia/Seoul. It collects, analyzes, saves checkpoints, validates, and deploys, preserving existing valid summaries on errors. Model default: gpt-4.1-mini; daily AI request cap: 12; full text preferred; input cap: 120000 characters; output cap: 4800 tokens. Manual runs can lower the daily cap with `max_ai_papers` or choose collection only.

First real collection-only run: https://github.com/zmfhto11/vet-journal/actions/runs/35187735449. PubMed returned 556 records and Europe PMC returned 897 records for the 45-day window; these are source receipts before deduplication and clinical AI screening, not counts of reviewed clinical papers. Both source statuses were `ok`. No paid AI analysis was performed.

**Remaining requirement:** repository Actions secret `OPENAI_API_KEY` has not been registered at the last check. The user must enter their API key directly at https://github.com/zmfhto11/vet-journal/settings/secrets/actions/new (Name: `OPENAI_API_KEY`). No key is stored in source, website, archive or chat. Paid API connectivity, account quota/model access and live-model summary quality remain unverified. Until successful AI analyses exist, the site displays eight explicitly labelled reference annotations.

The local checkout is not a synchronized clone of the GitHub source history. Do not force-push this local repository over remote data checkpoints; future updates must retain the latest remote state.

Read markers remain browser-local and origin-specific. Marks from localhost do not automatically transfer to the public site.
