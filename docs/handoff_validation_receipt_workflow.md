# Handoff Validation Receipt Workflow

The `handoff_validation_receipt` CLI creates a deterministic final receipt for generated diagnostic bundles. The focused workflow makes that receipt independently visible in GitHub Actions so reviewers can confirm bundle identity, required artifacts, upstream gate statuses, and rerun commands before accepting a handoff.

## What the workflow validates

The dedicated GitHub Actions workflow `.github/workflows/handoff-validation-receipt.yml` performs a narrow validation path that:

1. Installs the core dependency profile used by the main CI workflow.
2. Compiles the application and tests.
3. Runs `tests.test_handoff_validation_receipt`.
4. Builds the deterministic diagnostics bundle with `make ci-report ARTIFACT_DIR=ci_artifacts`.
5. Exports `ci_artifacts/handoff-validation-receipt.md` and `ci_artifacts/handoff-validation-receipt.json`.
6. Confirms the receipt artifacts exist and include the expected uncertainty-scope language.
7. Uploads the generated bundle for reviewer inspection, even if a later assertion fails.

## Local reproduction

Run the same focused validation locally with:

```bash
python -m pip install -r requirements-core.txt
python -m compileall app tests
python -m unittest tests.test_handoff_validation_receipt
make ci-report ARTIFACT_DIR=ci_artifacts
python -m app.cli.handoff_validation_receipt \
  --artifact-dir ci_artifacts \
  --markdown-path ci_artifacts/handoff-validation-receipt.md \
  --json-path ci_artifacts/handoff-validation-receipt.json
test -s ci_artifacts/handoff-validation-receipt.md
test -s ci_artifacts/handoff-validation-receipt.json
grep -q "claim of predictive certainty" ci_artifacts/handoff-validation-receipt.md
```

## Review guidance

Treat the receipt as a final bundle-check record, not a claim that analytical outputs are true or complete. A `blocked` receipt means at least one required handoff artifact is missing, one upstream validation gate failed, or the manifest reports missing expected outputs. A `needs_review` receipt means the bundle can be inspected but a reviewer should document accepted limitations or rerun the narrow generator that produced the warning.

This workflow stays offline. It does not run collection, live feeds, prediction, model training, deployment, database access, or external services beyond normal GitHub Actions dependency installation.

## Compatibility and rollback

The workflow is additive. It does not change existing commands, APIs, generated schemas, or the main smoke-test workflow. To roll it back, remove `.github/workflows/handoff-validation-receipt.yml`, this document, and `tests/test_handoff_validation_receipt_workflow.py`.
