# Automation Goal Horizon Balance

This guide helps recurring maintenance runs choose work that is meaningful now while still advancing the repository as a coherent analytical product over time.

## Purpose

Use this guide after checking default-branch health, open pull requests, hosted checks, review blockers, and recent automation work. It prevents the next increment from becoming isolated busywork by requiring every change to connect to a near-term, medium-term, or long-term repository goal.

## Horizon model

| Horizon | Primary question | Good candidates | Evidence to capture |
| --- | --- | --- | --- |
| Near-term | What makes the next pull request easier to merge safely? | failing validation fixes, setup recovery, narrow rerun guidance, tests, artifact completeness, reviewer handoff gaps | exact failing check or local command, final head SHA, changed files, rollback notes |
| Medium-term | What connects existing modules into a better user workflow? | CLI ergonomics, JSON/Markdown artifacts, provenance labels, uncertainty notes, status boards, dashboard handoff, scenario comparison | user workflow before/after, compatibility notes, generated artifact paths, schema impact |
| Long-term | What compounds toward a reliable defensive analytical platform? | reproducible experiments, model diagnostics, safe fixtures, explainability, compatibility contracts, release evidence | assumptions, limitations, validation strategy, follow-up work, safe analytical framing |

## Selection rule

When validation is failing or unavailable, choose the smallest repair that makes the blocker reproducible and fixable. When validation is green, choose the highest-value increment that satisfies all of these constraints:

1. It belongs to one primary horizon and supports at least one other horizon.
2. It changes a cohesive surface area that can be reviewed in one pull request.
3. It adds or updates tests for the changed behavior.
4. It updates the discoverable documentation or generated artifact contract users need to understand the change.
5. It records the next follow-up so later runs can continue the same development path.

## Anti-stall checks

Before opening a pull request, confirm the increment is not just documentation churn. A good increment should do at least one of the following:

- Remove ambiguity from a repeated maintenance decision.
- Add machine-readable evidence or a deterministic artifact.
- Improve first-run, setup, validation, or handoff ergonomics.
- Make safe analytical estimates easier to explain, reproduce, compare, or audit.
- Reduce repeated maintenance cost for future runs.

## Pull request notes

Every pull request using this guide should include:

- Chosen horizon and secondary horizon support.
- Why this was the best mergeable increment now.
- Exact local and hosted validation evidence.
- Compatibility and rollback notes.
- A concrete next-step candidate for the next automation run.
