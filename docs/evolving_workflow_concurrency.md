# Evolving Workflow Concurrency

This guide documents a small workflow evolution step for recurring repository maintenance: add conservative GitHub Actions concurrency controls to high-frequency pull-request validation while preserving existing workflow names, required checks, jobs, artifact uploads, and branch-protection expectations.

## Purpose

Pull-request automation can produce several validation runs for the same branch when stacked review fixes land quickly. Concurrency controls keep the newest pull-request run authoritative, reduce duplicate queued work, and make reviewer evidence easier to interpret without deleting successful workflows or replacing release gates.

## Current policy

For workflows that opt in, use this top-level pattern:

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}
```

The group is scoped by workflow name and ref so independent workflows still run separately. Pull-request runs may cancel older runs on the same branch, while push runs to `main` are not cancelled by this policy.

## Reviewer evidence rules

Before merging a pull request that changes workflow concurrency, reviewers should record:

- the final head SHA;
- every required workflow name and conclusion;
- whether any run was cancelled because a newer same-ref pull-request run superseded it;
- the artifact names still produced by successful runs;
- the rollback commit or revert plan.

A cancelled older pull-request run is acceptable only when a newer run for the same workflow, same PR branch, and final head SHA completed successfully. Missing, skipped, unavailable, wrong-head, or failed required validation remains a merge blocker.

## Compatibility and rollback

This is an additive workflow ergonomics change. It does not change Python runtime behavior, prediction APIs, generated artifact schemas, CLI arguments, database behavior, model behavior, or analytical outputs. It preserves existing workflow names and job names so branch-protection settings and reviewer runbooks can continue using the same labels.

Rollback by reverting the workflow concurrency block and this documentation/test update. Do not remove unrelated CI smoke checks, handoff validation, analytical framing audits, artifact uploads, or diagnostics generation.

## Safe analytical framing

Workflow concurrency is repository-maintenance automation only. It does not fetch live data, run model inference, perform targeting, improve prediction certainty, or validate real-world conditions. Generated artifacts remain review evidence for analytical estimates, uncertainty communication, and reproducible handoff, not operational tasking or proof of real-world outcomes.

## Follow-up work

Future runs can evolve workflows slowly by adding release-readiness summaries, manifest validation, reusable workflow components, caching, or targeted compatibility matrices only when a concrete recurring failure, validation gap, or reviewer handoff need justifies the added complexity.
