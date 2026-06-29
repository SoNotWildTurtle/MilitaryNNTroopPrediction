# Automation PR Evidence Template

Use this template when an automation-maintained pull request needs a concise, reviewable description that ties the change to validation evidence, safe analytical framing, compatibility, rollback, and merge blockers. It is intentionally additive and does not replace `docs/automation_run_preflight.md`, `docs/validation_evidence_crosswalk.md`, `docs/hosted_check_evidence_log.md`, `docs/merge_readiness_record_template.md`, or `docs/post_merge_verification_receipt.md`.

The template is documentation-only. It does not run prediction workflows, fetch live data, change model behavior, bypass branch protection, or imply operational certainty. Predictive outputs and generated artifacts must remain framed as analytical estimates, synthetic fixtures, static previews, diagnostics, or reviewer handoff evidence.

## Copyable PR body

```markdown
## Summary
- Additive change:
- User/reviewer value:
- Existing guidance or feature extended:

## Implementation details
- Files changed:
- New docs, tests, schemas, CLI flags, or generated artifacts:
- Backwards compatibility preserved by:

## Analytical and UX rationale
- How this helps reviewers validate, explain, reproduce, or hand off the work:
- How uncertainty, validation limits, and analytical-estimate framing are preserved:
- Why this is not operational targeting advice or a claim of real-world certainty:

## Validation evidence
- Local narrow rerun:
- Local broad validation:
- Hosted `CI` conclusion for final head SHA:
- Hosted `Analytical Framing Audit` conclusion for final head SHA:
- Hosted `Handoff Validation Receipt` conclusion for final head SHA:
- Diagnostic artifacts reviewed:

## Final diff review
- Target branch:
- Final head SHA:
- Accidental deletions checked:
- Secrets/generated artifacts checked:
- Unsupported claims or unsafe scope checked:
- Review threads and requested changes checked:

## Risks and compatibility
- Runtime behavior impact:
- API/schema/CLI compatibility impact:
- Documentation or artifact-consumer impact:
- Known limitations:

## Rollback
- Smallest safe rollback:
- Migration notes, if any:
- Recovery notes for downstream consumers:

## Dependencies and follow-up
- Stacked PRs or dependencies:
- Remaining blockers before merge:
- Best next step after merge or if left open:
```

## Required evidence discipline

Before marking a PR ready to merge, the body should name the exact final head SHA and record conclusions for `CI`, `Analytical Framing Audit`, and `Handoff Validation Receipt`. Missing, queued, stale, skipped, cancelled, failed, or wrong-head hosted validation remains a blocker even if local checks pass.

When a check fails, update the PR body with the precise failing job, step, command, schema field, artifact path, brittle assertion, or compatibility condition. Fix the root cause and rerun the narrowest relevant command before broader validation.

## Narrow rerun menu

Use the smallest command that covers the changed surface before running broad checks:

```bash
python -m unittest tests.test_automation_pr_evidence_template_docs
make ci-triage
make workflow-gate-summary ARTIFACT_DIR=ci_artifacts/local-ci
make triage-summary ARTIFACT_DIR=ci_artifacts/local-ci
make handoff-validation-receipt ARTIFACT_DIR=ci_artifacts/local-ci
make verify ARTIFACT_DIR=ci_artifacts/local-ci
```

## Review checklist

- The change extends existing behavior or documentation rather than deleting or replacing working components.
- The PR body names the target branch, final head SHA, required hosted checks, local validation, artifacts reviewed, risks, compatibility impact, rollback path, known limitations, and follow-up work.
- Predictive, diagnostic, and generated outputs are framed as analytical estimates or review artifacts rather than operational truth.
- The final diff contains no secrets, accidental generated artifacts, broad deletions, unsupported certainty claims, unsafe operational instructions, or target-branch mistakes.
- Review threads, requested changes, merge conflicts, branch protection, and stacked dependencies are resolved before merge.

## Relationship to existing docs

- Start with `docs/automation_run_preflight.md` before selecting a new increment.
- Use `docs/validation_evidence_crosswalk.md` to map reviewer questions to commands and artifacts.
- Use `docs/hosted_check_evidence_log.md` to capture hosted run URLs and job conclusions.
- Use `docs/merge_readiness_record_template.md` when the final merge decision needs a fuller record.
- Use `docs/post_merge_verification_receipt.md` after merge to confirm the resulting commit reached the intended target branch.

## Rollback

Rollback is a normal documentation/test/changelog revert of this template and its regression coverage. Reverting this page should not remove existing PR workflows, generated artifact contracts, branch-protection expectations, or prior validation runbooks.
