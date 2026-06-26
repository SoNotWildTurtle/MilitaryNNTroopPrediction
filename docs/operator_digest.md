# Operator digest

`operator-digest.md` is the first-read summary for a generated diagnostics bundle. It condenses release health, artifact manifest, CI triage, and reviewer handoff data into one short Markdown file plus a machine-readable JSON companion.

The workflow is intentionally local and safe. It reads generated files under `ci_artifacts/` and writes summary artifacts only. It does not run live ingestion, prediction, detection, network collection, deployment, or destructive workflows.

## Generate the digest

```bash
make ci-report
make operator-digest
```

The standalone target writes:

- `ci_artifacts/operator-digest.md`
- `ci_artifacts/operator-digest.json`

Use a separate artifact directory when comparing runs:

```bash
make ci-report ARTIFACT_DIR=ci_artifacts/local-review
make operator-digest ARTIFACT_DIR=ci_artifacts/local-review
```

## Review flow

1. Open `release-bundle-index.html` to confirm the full bundle is present.
2. Open `operator-digest.md` for the short status, next command, and copyable summary.
3. If the digest reports missing outputs or failing checks, open `triage-summary.md` and rerun the narrow target it recommends.
4. Use `reviewer-handoff.md` when sharing the bundle with another maintainer.

## Machine-readable contract

`operator-digest.json` includes:

- `generated_at`: UTC timestamp for the digest generation.
- `artifact_dir`: artifact directory used as input.
- `status` and `status_label`: normalized review status for quick display.
- `release_status`: release-health status from diagnostics.
- `next_step`: the preferred next local command or reviewer action.
- `artifact_count`: number of files indexed by the manifest.
- `missing_expected` and `missing_key_artifacts`: bundle gaps to resolve before handoff.
- `blocking_reasons`: short human-readable reasons attention is needed.
- `recommended_actions`: top triage rerun actions.
- `copyable_summary`: short handoff text for issue comments or PR summaries.
- `safe_scope`: reminder that the digest is limited to local diagnostics and documentation.

## Compatibility and rollback

The digest is additive. Existing targets, APIs, generated artifacts, and review flows remain available. To roll back, remove the `operator-digest` target and the two digest entries from the artifact manifest expectation list, then stop invoking `app.cli.operator_digest` from `scripts/ci_report.sh`.
