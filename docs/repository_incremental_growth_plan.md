# Repository Incremental Growth Plan

This plan turns recurring repository maintenance into a durable product-development loop. It is intentionally additive: each run should improve the existing application, documentation, validation, or handoff workflow without replacing working components or obscuring merge blockers.

## Purpose

Use this guide before selecting a new automation increment. It helps maintainers choose changes that are meaningful, mergeable, testable, and connected to a longer development path rather than isolated one-off patches.

## Run goals

Each maintenance run should:

1. Inspect the default branch, open pull requests, recent commits, issues, workflows, required checks, review threads, branch protection, and prior automation work.
2. Repair failing or unavailable validation before starting unrelated feature work.
3. Select one cohesive increment that advances the repository as a defensible analytical application.
4. Keep changes additive, backwards-compatible, and easy to review.
5. Add or update tests and documentation for the behavior being changed.
6. Preserve safe analytical framing: outputs are estimates, diagnostics, or review artifacts, not operational certainty.
7. Record follow-up work so later runs can build from the current state.

## Goal hierarchy

### Near-term goals

Near-term work should improve the next pull request's mergeability and reviewer confidence.

- Keep CI and required hosted checks green.
- Add narrow reproduction commands for failures.
- Improve setup validation, quickstart paths, and first-run error recovery.
- Keep generated artifacts easy to inspect through manifests, indexes, previews, and handoff summaries.
- Expand static regression coverage for documentation and schema contracts when those surfaces are changed.

### Medium-term goals

Medium-term work should connect existing modules into complete, user-facing workflows.

- Strengthen data provenance, uncertainty notes, and synthetic-versus-live artifact labels.
- Make scenario comparison, diagnostics, and review handoff outputs easier to understand.
- Improve CLI ergonomics with safe defaults, JSON/Markdown output, and actionable next commands.
- Document compatibility expectations for downstream consumers.
- Reduce repeated maintenance cost by consolidating checklists into discoverable runbooks and generated evidence.

### Long-term goals

Long-term work should move the repository toward a reliable defensive and analytical platform.

- Keep predictive outputs framed as analytical estimates with clear limitations.
- Support reproducible experiments, model diagnostics, safe fixtures, and explainable results.
- Maintain privacy-aware, lawful, defensive use cases with no operational targeting claims.
- Build reviewer-ready release bundles that can be handed off without requiring local expertise.
- Preserve backward compatibility while gradually improving APIs, schemas, artifacts, and docs.

## Increment selection checklist

Before implementing a change, confirm that it:

- Builds on current architecture, docs, and prior PRs.
- Has a clear user or maintainer benefit.
- Can be reviewed as one cohesive pull request.
- Includes a narrow validation plan.
- Avoids deleting, replacing, or broadly rewriting working functionality.
- Documents compatibility, rollback, risks, limitations, and follow-up work when relevant.

## Anti-patterns to avoid

Avoid changes that:

- Duplicate an existing runbook, CLI, schema, or artifact without improving navigation or integration.
- Add documentation that is not linked from a discoverable surface.
- Create generated outputs without manifest, provenance, or review guidance.
- Hide failing checks or weaken tests to make CI pass.
- Mix unrelated features, refactors, and documentation churn in one PR.
- Make unsupported claims about prediction certainty or operational readiness.

## Follow-up capture

Every PR should leave a small trail for the next run:

- What changed and why it matters.
- Which tests or checks were run.
- Which hosted checks passed or blocked merge.
- Any compatibility or rollback notes.
- The next highest-value increment.

This keeps recurring automation focused on cumulative repository growth instead of disconnected maintenance tasks.
