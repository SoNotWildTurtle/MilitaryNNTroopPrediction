# Reviewer Workflow Status Index

Use this index as the first stop when a pull request has multiple green checks and reviewers need to understand what each check proves, what it does not prove, and which local command reproduces it. The checks are deliberately scoped to deterministic, offline, review-oriented validation. They do not claim that analytical estimates are true, complete, current, or operationally actionable.

## Status matrix

| Hosted check | Primary purpose | Local reproduction | What green means | What green does not mean |
| --- | --- | --- | --- | --- |
| `CI` | Broad smoke-test bundle covering setup diagnostics, static API contracts, synthetic fixtures, generated review artifacts, and unit discovery. | `make verify ARTIFACT_DIR=ci_artifacts/local-review` | Core safe workflows still compose and the standard diagnostics bundle can be generated. | It does not validate model quality, live data collection, external services, or operational certainty. |
| `Analytical Framing Audit` | Focused wording audit for generated handoff artifacts. | `python -m unittest tests.test_analytical_framing_audit` then `python -m app.cli.analytical_framing_audit --artifact-dir ci_artifacts --markdown-path ci_artifacts/analytical-framing-audit.md --json-path ci_artifacts/analytical-framing-audit.json` | Generated handoff language retains analytical-scope caveats and avoids the audited overconfident/operational wording patterns. | It does not prove that every possible phrase is safe or that analytical conclusions are correct. |
| `Handoff Validation Receipt` | Focused final receipt generation for bundle identity, expected artifacts, upstream gate summaries, and rerun commands. | `make ci-report ARTIFACT_DIR=ci_artifacts` then `make handoff-validation-receipt ARTIFACT_DIR=ci_artifacts` | The handoff receipt can be exported and includes the expected uncertainty-scope language. | It does not replace reviewer judgment or validate predictive truth. |

## Review order

1. Check that all required hosted checks for the PR head SHA are completed and green.
2. Open the PR diff and confirm the changed files are additive, scoped, and targeted at the intended base branch.
3. Review generated or documented commands from the narrowest relevant workflow before rerunning the full bundle.
4. Inspect `release-bundle-index.html`, `handoff-validation-receipt.md`, `analytical-framing-audit.md`, and `triage-summary.md` when available.
5. Treat any missing workflow result, queued workflow, unavailable artifact, or unresolved review thread as a merge blocker until it is explained or resolved.

## Failure triage

Prefer the narrowest failing check first:

- If `CI` fails, start with `make ci-triage` and the failing job log.
- If `Analytical Framing Audit` fails, rerun the audit CLI against the generated artifact directory and inspect the reported phrase, file, and severity.
- If `Handoff Validation Receipt` fails, regenerate the diagnostics bundle with `make ci-report`, then rerun `make handoff-validation-receipt` and inspect missing artifact or gate-status details.

Avoid bypassing failures by weakening assertions. Update brittle tests only when the behavior remains strictly validated and the new assertion is resistant to harmless formatting or environment differences.

## Compatibility and rollback

This guide is additive documentation for reviewers. It does not change runtime code, workflows, generated schemas, APIs, tests, or data files. To roll it back, remove this file, its README/CHANGELOG references, and `tests/test_reviewer_workflow_status_index.py` if present.
