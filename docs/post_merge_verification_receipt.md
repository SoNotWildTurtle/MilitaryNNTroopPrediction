# Post-Merge Verification Receipt

Use this receipt after a pull request is merged to confirm the intended change is recoverable, traceable, and actually present on the default branch. It complements the pre-merge evidence packet and hosted check evidence log by focusing on the state after GitHub reports a successful merge.

## When to use this receipt

Complete this receipt immediately after merging any automation-authored pull request, especially when the PR used a squash merge, promoted a stacked dependency, changed reviewer handoff artifacts, or updated validation workflow guidance.

Do not use this receipt as a reason to merge early. Missing required hosted validation, unavailable job conclusions, unresolved review threads, branch-protection blockers, unsafe scope, or a stale final head SHA remain merge blockers before this checklist applies.

## Copyable receipt

```markdown
## Post-merge verification receipt

- Repository:
- Target branch:
- Pull request:
- Merge method:
- Expected PR head SHA before merge:
- Resulting merge commit SHA:
- Merge commit URL:
- Verified on target branch: yes/no
- Verification command or GitHub view used:
- Required checks before merge:
  - CI: passed/failed/unavailable/not applicable
  - Analytical Framing Audit: passed/failed/unavailable/not applicable
  - Handoff Validation Receipt: passed/failed/unavailable/not applicable
- Open stacked PRs after merge:
- Follow-up PRs that still need promotion:
- Files changed by merge:
- Generated artifacts intentionally excluded from repository:
- Compatibility impact:
- Rollback path:
- Safe analytical framing confirmed: yes/no
- Notes:
```

## Verification steps

1. Re-open the merged pull request and record the final PR head SHA that was approved for merge.
2. Record the resulting merge commit SHA from GitHub's merge result.
3. Open the default branch and verify that the merge commit is reachable from the intended target branch.
4. Compare the merged commit against the PR diff and confirm there are no accidental deletions, secrets, generated artifact commits, unsafe claims, unsupported operational framing, or target-branch mistakes.
5. Search for open pull requests in the repository and identify any stacked PR that still targets an intermediate branch or depends on the merged PR.
6. Confirm the next run should start from the updated default branch instead of the now-merged feature branch.
7. If verification fails, do not continue additive work on top of the uncertain state. Open a blocker issue or follow-up PR with the exact missing merge commit, target branch, check conclusion, or review-thread evidence.

## Evidence to retain

- Merged PR number and URL.
- Expected final PR head SHA.
- Resulting merge commit SHA.
- Target branch name and verification timestamp.
- Required hosted workflow names and conclusions.
- Final diff file list.
- Any remaining stacked PRs or follow-up blockers.

## Safe-scope notes

This receipt is repository-maintenance evidence only. It does not certify predictive accuracy, operational readiness, targeting suitability, live data quality, or conflict outcomes. Predictive outputs and generated examples remain analytical estimates or synthetic placeholders unless separately validated with documented provenance and uncertainty.

## Rollback guidance

Prefer a narrow revert PR against the default branch when a merged change must be undone. Include the merge commit SHA, the reason for rollback, the affected files, compatibility notes, and the smallest validation command that reproduces the issue. Avoid history rewrites, force pushes, branch deletion, or broad file removal.
