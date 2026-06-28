# Workflow Gate Review Runbook

This runbook gives maintainers a deterministic, offline-first checklist for deciding whether a pull request can move from generated diagnostics to a safe merge decision. It complements `docs/workflow_gate_summary.md` and the `python -m app.cli.workflow_gate_summary` exporter without replacing reviewer judgment.

## Safe analytical scope

Use this guide only for repository validation, diagnostics handoff, and reproducible review. It does not validate model quality, live data availability, external intelligence sources, operational targeting, or the truth of analytical estimates. Predictive outputs must remain framed as estimates with uncertainty and provenance, not certainty.

## Required hosted gates

Before merge, confirm these checks are present, complete, green, and attached to the final PR head SHA:

| Gate | Local reproduction | What green means | What green does not mean |
| --- | --- | --- | --- |
| `CI` | `make verify ARTIFACT_DIR=ci_artifacts/local-review` | Core setup, tests, diagnostics, artifact generation, and handoff validation compose successfully. | Predictive correctness, live data reliability, external service access, or analyst approval. |
| `Analytical Framing Audit` | `python -m unittest tests.test_analytical_framing_audit && python -m app.cli.analytical_framing_audit --artifact-dir ci_artifacts` | Generated handoff language preserves analytical-scope caveats and avoids audited overconfident wording. | Every unsafe phrase is impossible, or all downstream use is safe without review. |
| `Handoff Validation Receipt` | `make ci-report ARTIFACT_DIR=ci_artifacts && make handoff-validation-receipt ARTIFACT_DIR=ci_artifacts` | A deterministic diagnostics bundle and final receipt can be generated offline. | Reviewer judgment, branch policy, or policy review can be skipped. |

## Review order

1. Confirm there are no open stacked PRs that must merge first.
2. Confirm the PR targets the default branch and the branch is current.
3. Fetch the exact check names and final head SHA from GitHub.
4. If any gate is failing, queued, cancelled, skipped, missing, or unavailable, treat the PR as blocked.
5. Reproduce the narrow failing command locally before changing code.
6. Fix root causes or brittle assertions rather than bypassing checks.
7. Run the full relevant validation path after the narrow fix passes.
8. Inspect the final diff for accidental deletions, generated artifacts, secrets, unsupported claims, target-branch mistakes, and incompatible changes.
9. Merge only when required validation is available, current, green, and repository policy permits it.

## Blocker handling

| Blocker | First action | Narrow rerun |
| --- | --- | --- |
| CI missing or queued | Wait for the run or rerun the workflow from the PR if policy allows. | `make verify ARTIFACT_DIR=ci_artifacts/local-review` |
| CI failure | Fetch the failing job log and identify the exact command. | The single failing CLI, unit test, or `make` target named by the log. |
| Analytical framing failure | Open the Markdown/JSON audit artifact and inspect severe findings first. | `python -m app.cli.analytical_framing_audit --artifact-dir ci_artifacts` |
| Handoff receipt failure | Compare `reviewer-handoff.json`, validation output, gap report, and receipt JSON. | `make ci-report ARTIFACT_DIR=ci_artifacts && make handoff-validation-receipt ARTIFACT_DIR=ci_artifacts` |
| Required check unavailable | Do not merge; document the unavailable validation and leave the PR open. | `python -m app.cli.workflow_gate_summary --artifact-dir ci_artifacts` |

## Handoff notes

When leaving a PR open, include the exact blocker, final head SHA, failing or unavailable gate name, narrow reproduction command, risks, rollback path, and next best step. When merging, include the merge SHA and confirm that no stacked PR still needs promotion to the default branch.

## Compatibility and rollback

This runbook is documentation-only. It preserves existing APIs, workflows, CLIs, generated artifact shapes, and user commands. Rollback is limited to reverting this file and its static regression test if the guidance becomes obsolete.
