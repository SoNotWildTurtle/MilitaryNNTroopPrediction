# Workflow Gate Summary

`python -m app.cli.workflow_gate_summary` exports an offline JSON/Markdown map of the hosted validation gates reviewers should check before merge. It is a reviewer aid for deterministic repository hygiene, not a live GitHub status client and not a predictive model quality assessment.

## Why this exists

Pull requests now have multiple review-oriented workflows. The gate summary gives reviewers a single artifact that explains:

- which hosted checks are expected before merge;
- the local command that best reproduces each check;
- what a green check proves;
- what a green check does **not** prove;
- when a missing, stale, queued, failed, or unavailable gate should block merge.

The CLI only inspects static workflow file presence in the local checkout and renders documented gate metadata. It never contacts GitHub, collects OSINT, launches model inference, connects to MongoDB, or treats analytical estimates as operational certainty.

## Usage

```bash
python -m app.cli.workflow_gate_summary
python -m app.cli.workflow_gate_summary \
  --artifact-dir ci_artifacts/local-review \
  --markdown-path ci_artifacts/local-review/workflow-gate-summary.md \
  --json-path ci_artifacts/local-review/workflow-gate-summary.json
```

Default outputs:

- `ci_artifacts/workflow-gate-summary.md`
- `ci_artifacts/workflow-gate-summary.json`

You can also use the Makefile wrapper:

```bash
make workflow-gate-summary ARTIFACT_DIR=ci_artifacts/local-review
```

The standard diagnostic bundle now includes the same artifacts when running:

```bash
make ci-report ARTIFACT_DIR=ci_artifacts/local-review
make verify ARTIFACT_DIR=ci_artifacts/local-review
```

In the bundle, review:

- `workflow-gate-summary.md`
- `workflow-gate-summary.json`
- `workflow-gate-summary-help.txt`

## Review workflow

1. Generate or open the workflow gate summary.
2. Confirm every required hosted check named in the summary is complete and green for the final PR head SHA.
3. If a check is failing or unavailable, fetch the exact job logs and reproduce the narrow local command listed for that gate.
4. Fix root causes or brittle assertions without bypassing behavioral guarantees.
5. Review the final diff for accidental deletions, secrets, generated artifacts, unsupported claims, unsafe changes, regressions, and target-branch correctness before merge.

## Compatibility

This CLI is additive and standard-library only. It does not alter existing APIs, schemas, data files, workflows, or generated artifact contracts. JSON consumers should treat new fields as additive. The Makefile and CI bundle wiring only add new outputs; existing commands and artifact names remain unchanged.

## Rollback

To roll back the CLI itself, remove `app/cli/workflow_gate_summary.py`, `tests/test_workflow_gate_summary.py`, this document, and the changelog entry. To roll back only the bundle wiring, revert the Makefile target, `scripts/ci_report.sh` additions, static wiring tests, and the related changelog entry. No data migration is required.
