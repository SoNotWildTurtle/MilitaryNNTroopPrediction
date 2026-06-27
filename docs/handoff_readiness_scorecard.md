# Handoff Readiness Scorecard

`app.cli.handoff_readiness_scorecard` creates an offline Markdown and JSON scorecard for generated analytical handoff bundles. It condenses provenance, evidence completeness, validation, and artifact-quality signals into a weighted 100-point readiness view.

## Why this exists

Recent diagnostics expose detailed reviewer artifacts such as the provenance validation matrix, evidence checklist, handoff validation receipt, artifact gap report, and manifest. The scorecard gives maintainers a fast first-read view before they inspect the detailed artifacts.

The scorecard is intentionally conservative. Missing or blocked validation artifacts lower the score and mark the bundle as blocked. Warning-level artifacts mark the bundle as needing review instead of claiming readiness.

## Safe analytical scope

The command reads local generated diagnostics and writes optional Markdown/JSON outputs. It does not collect OSINT, fetch imagery, connect to MongoDB, run model inference, train models, deploy services, or make claims of real-world certainty.

## Usage

```bash
python -m app.cli.handoff_readiness_scorecard --artifact-dir ci_artifacts
python -m app.cli.handoff_readiness_scorecard \
  --artifact-dir ci_artifacts \
  --markdown-path ci_artifacts/handoff-readiness-scorecard.md \
  --json-path ci_artifacts/handoff-readiness-scorecard.json
```

Use `--no-markdown` or `--no-json` when only one output format is needed.

## Inputs

The command prefers these generated diagnostics:

| Category | Preferred input | Fallback |
| --- | --- | --- |
| Data provenance and source labeling | `provenance-validation-matrix.json` | `artifact-provenance-ledger.json` |
| Evidence completeness | `evidence-checklist.json` | none |
| Validation receipt and blockers | `handoff-validation-receipt.json` | `reviewer-handoff-validation.json` |
| Artifact integrity and completeness | `artifact-gap-report.json` | `artifact-manifest.json` |

## Outputs

The Markdown output is intended for human review and handoff notes. The JSON output is intended for automation, release gates, and future CI promotion.

Important JSON fields:

- `status`: `ready`, `needs_review`, or `blocked`.
- `score`: weighted 0-100 readiness score.
- `categories`: per-category status, score, source artifact, and requirement.
- `blockers` and `warnings`: copyable follow-up reasons.
- `safe_scope`: reminder that the output is diagnostic and analytical only.

## Validation

Run the focused tests:

```bash
python -m unittest tests.test_handoff_readiness_scorecard
```

Run the full lightweight suite before opening or merging a PR:

```bash
python -m compileall app tests
python -m unittest discover -s tests -p 'test_*.py'
```

## Rollback

Remove `app/cli/handoff_readiness_scorecard.py`, `tests/test_handoff_readiness_scorecard.py`, and this document. No data migration is required because the command only reads existing diagnostics and writes requested report files.

## Follow-up work

- Wire the scorecard into `make ci-report` after the generated artifact set stabilizes.
- Link the scorecard from the release bundle index.
- Add a CSV export for spreadsheet-oriented review workflows.
