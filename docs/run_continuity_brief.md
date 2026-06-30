# Run Continuity Brief

`app.cli.run_continuity_brief` generates a deterministic offline Markdown and JSON summary for recurring maintenance runs. It helps the next maintainer choose one cohesive additive increment from the current roadmap, recent changelog entries, and the next-run decision register without duplicating recent process-only work.

## Purpose

Use this brief at the start of a maintenance pass after default-branch, open-PR, and required-check inspection. The output is intended to make the next decision easier to review and hand off:

- recent `CHANGELOG.md` entries inspected;
- numbered `goals.md` roadmap slice inspected;
- whether `docs/next_run_decision_register.md` is present;
- scored focus areas for user friendliness, validation, provenance, model diagnostics, and automation planning;
- a recommended next increment with rationale;
- blockers that should stop a new PR until continuity context is repaired.

The brief is planning evidence only. It does not collect live OSINT, fetch imagery, query networks, run detection, run prediction, mutate source artifacts, or assert operational truth.

## Usage

```bash
python -m app.cli.run_continuity_brief
python -m app.cli.run_continuity_brief --markdown-path ci_artifacts/run-continuity-brief.md --json-path ci_artifacts/run-continuity-brief.json
python -m app.cli.run_continuity_brief --no-markdown --json-path /tmp/run-continuity-brief.json
```

By default, outputs are written to:

- `run-continuity-brief.md`
- `run-continuity-brief.json`

Use `--repository-root` when generating a brief from a checked-out repository that is not the current working directory.

## Review workflow

1. Inspect open PRs, required checks, and review threads first. If a failing or unavailable PR validation exists, fix that blocker before selecting new work.
2. Generate the brief locally.
3. Read the recommended focus area and the scored focus table.
4. Compare the recommendation against open issues, current PRs, and recent merged work.
5. Choose one cohesive increment that improves product functionality, validation, usability, provenance, or maintainability.
6. Add tests and update user-facing documentation before opening a PR.
7. Include the final head SHA, hosted check evidence, compatibility notes, rollback path, and safe analytical framing in the PR body.

## Status semantics

- `ready`: the changelog, roadmap, and decision-register inputs were readable enough to support the next planning decision.
- `blocked`: one or more continuity inputs were missing or empty. Inspect recent commits and roadmap context manually before opening new work.

## Compatibility

The JSON output includes `schema_version: "1.0"`. Downstream consumers should preserve unknown fields and treat new focus areas as additive. A missing field should be handled as an informational warning unless the `status` is `blocked` or the `blockers` list is non-empty.

## Rollback

This utility is isolated from prediction and ingestion paths. If it causes unexpected CI failures, revert the CLI file, its test file, and this document. No generated diagnostic schema or runtime API contract depends on it.

## Safe analytical scope

Use the brief only to plan lawful defensive analytical repository maintenance, reviewer handoff, reproducibility, validation, uncertainty communication, and user-friendly tooling. It does not validate operational predictions or imply certainty about real-world activity.
