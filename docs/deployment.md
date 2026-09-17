# Live deployment

- Site: https://zmfhto11.github.io/vet-journal/
- Repository: https://github.com/zmfhto11/vet-journal
- Deployment: https://github.com/zmfhto11/vet-journal/actions/runs/35089598284
- Verified 2026-09-17: deployment completed successfully; site returned HTTP 200; browser rendered all eight reference papers; clinical interpretation toggle opened with the explicit AI label.

## Published scope

The repository currently contains the built static website at its root and the reference dataset under `data/`. GitHub Pages uses `main` → `/ (root)` with HTTPS. `data/papers.json` explicitly indicates `setup_required` with an empty live dataset, so the UI displays the eight source-checked reference annotations. No API key or unpublished state file was uploaded.

The local source checkout still contains the Python collector, analyzer, tests, journal configuration, and daily GitHub Actions workflows. Those backend/source files and workflows have **not** yet been uploaded to the live repository. Scheduled collection and paid AI analysis are therefore not active. Future automation setup must publish the complete source, reconcile the root-static layout with the source build, configure Pages for the deployment workflow, and add the OpenAI key through GitHub Secrets. Do not treat this static deployment repository as an already synchronized source remote or blindly overwrite it.

Read markers remain browser-local and origin-specific. Marks from localhost do not automatically transfer to the public site.
