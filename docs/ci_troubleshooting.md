# CI troubleshooting guide

Use this guide when a pull request or push fails the lightweight GitHub Actions smoke workflow. The workflow is intentionally defensive and reproducible: it installs only the core dependency profile, runs `make verify`, and uploads a static `ci-diagnostics` artifact bundle for review.

## Fast reproduce path

Print the quick local triage checklist at any time:

```bash
make ci-triage
```

Then run the same command that hosted CI uses, with an isolated local artifact directory:

```bash
make install-core
make verify ARTIFACT_DIR=ci_artifacts/local-ci
```

Then open:

```text
ci_artifacts/local-ci/release-bundle-index.html
```

That landing page links the release health report, release notes, triage summary, OpenAPI summary, synthetic API examples, dashboard mockup, HTML previews, and artifact manifest. Start there before reading raw logs.

## Triage order

1. **Open the generated triage summary first**
   - Review `triage-summary.md` in the artifact bundle.
   - Use its first recommended target as the narrow rerun path.
   - If it says the bundle is ready, review `release-bundle-index.html` and attach the diagnostics bundle to the PR.

2. **Install step failed**
   - Re-run `make install-core` locally.
   - Confirm the active Python version is compatible with the workflow in `.github/workflows/ci.yml`.
   - Avoid installing optional ML/GIS/dashboard packages unless the change specifically requires them.

3. **Doctor failed**
   - Run `make doctor` for the minimal read-only diagnostics path.
   - Use `python -m app.cli.doctor --skip-optional --skip-mongo --json` when you need machine-readable output.
   - Treat failures as setup blockers. Warnings usually identify optional capabilities that should not block core CI.

4. **Unit tests failed**
   - Run `make test` to reproduce the standard-library smoke suite.
   - If a test verifies docs or workflow text, update the user-facing documentation in the same change as the behavior.

5. **Diagnostics bundle failed**
   - Run `make ci-report ARTIFACT_DIR=ci_artifacts/local-ci`.
   - Check `triage-summary.md` for failing health checks and narrow rerun targets.
   - Check `artifact-manifest.md` for missing generated files.
   - Re-run the narrow target that failed, such as `make doctor`, `make test`, `make ci-report`, `make openapi`, `make examples`, `make dashboard`, `make previews`, `make manifest`, `make release-notes`, or `make triage-summary`.

6. **Artifact upload failed**
   - Confirm `ci_artifacts/` exists after `make verify`.
   - Confirm `release-bundle-index.html`, `triage-summary.md`, and `artifact-manifest.json` were generated.
   - Check whether `.gitignore` is correctly excluding generated artifacts from source control without preventing local creation.

## Common fixes

| Symptom | Likely cause | First fix |
| --- | --- | --- |
| `ModuleNotFoundError` during CI | Core dependency missing from `requirements-core.txt` | Add the lightweight runtime dependency there, or move optional imports behind lazy imports. |
| Doctor reports missing optional packages | Optional dependencies were checked accidentally | Use `make doctor` or `--skip-optional --skip-mongo` for CI-equivalent diagnostics. |
| OpenAPI export fails | API import pulled in heavy prediction dependencies | Keep heavy TensorFlow/YOLO imports lazy and route-specific. |
| Artifact manifest reports missing files | A generator path changed or a new artifact was not wired into `scripts/ci_report.sh` | Update the generator, manifest expectations, README, and `triage-summary.md` expectations together. |
| Docs tests fail | Workflow docs drifted from Makefile or CI behavior | Update `README.md`, `CONTRIBUTING.md`, and `docs/common_tasks.md` with the changed command path. |

## Safe-scope reminder

CI troubleshooting should stay focused on local setup, deterministic tests, synthetic examples, API contracts, generated reviewer artifacts, and documentation. Do not add workflows that perform unauthorized collection, targeting, evasion, disruption, credential access, or operational deployment against real people or systems.

## Pull request note

When opening or updating a pull request after a CI fix, include:

```markdown
## Validation
- make verify ARTIFACT_DIR=ci_artifacts/local-ci
- Reviewed ci_artifacts/local-ci/release-bundle-index.html
- Reviewed ci_artifacts/local-ci/triage-summary.md

## Follow-up
- Remaining CI warnings or missing optional capabilities
```
