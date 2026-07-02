# CI run summary navigation

This guide defines a small, repeatable `GITHUB_STEP_SUMMARY` pattern for hosted workflow runs. It is intended for reviewers who need to move from a failing or successful run to the exact local command, diagnostic artifact, and merge-readiness evidence without scraping logs.

## Purpose

Use a run-summary navigation block when a workflow already produces reviewer-facing artifacts but the hosted run page does not clearly show where to start. The summary should reduce handoff friction while preserving the existing workflow, artifact upload, and required-check behavior.

This is a documentation and reviewer-navigation pattern only. It must not change prediction, ingestion, model-training, API, database, live OSINT, or operational behavior.

## Recommended summary fields

A useful summary block should include:

| Field | Why it matters |
| --- | --- |
| Workflow name | Confirms which hosted gate produced the summary. |
| Final head SHA | Anchors review and merge decisions to an immutable commit. |
| Primary artifact name | Points reviewers to the uploaded bundle or receipt to download first. |
| First document to open | Identifies the fastest human-readable starting point. |
| Machine-readable evidence | Names the JSON artifact that downstream tools should parse. |
| Narrow local rerun | Gives the smallest safe command to reproduce the gate. |
| Safe analytical scope | Reminds reviewers that artifacts are synthetic/offline evidence, not operational truth. |
| Merge blocker reminder | States that unavailable hosted validation remains a blocker before merge. |

## Minimal workflow snippet

```yaml
- name: Append reviewer navigation summary
  if: always()
  run: |
    {
      echo '## Reviewer navigation'
      echo ''
      echo '- Workflow: `${{ github.workflow }}`'
      echo '- Final head SHA: `${{ github.sha }}`'
      echo '- Artifact: `ci-diagnostics`'
      echo '- First document: `release-bundle-index.html`'
      echo '- Machine-readable evidence: `workflow-gate-summary.json`'
      echo '- Narrow rerun: `make ci-report ARTIFACT_DIR=ci_artifacts`'
      echo '- Scope: offline diagnostics, synthetic examples, and documentation evidence only.'
      echo '- Merge blocker: do not merge when required hosted validation is unavailable.'
    } >> "$GITHUB_STEP_SUMMARY"
```

## Compatibility guidance

Keep the summary additive and low risk:

- Do not rename required workflows, jobs, or uploaded artifacts only to add a summary.
- Do not replace artifacts with summary text; summaries are navigation aids, not complete evidence bundles.
- Keep commands deterministic and offline-first where possible.
- Preserve existing concurrency, permissions, triggers, and required-check names unless a separate reviewed change justifies them.
- Prefer single-quoted shell `echo` lines when embedding Markdown backticks so static tests and shell expansion remain predictable.

## Review checklist

Before adding or modifying a summary block, confirm:

1. The workflow still uploads the existing artifact bundle.
2. The summary names the exact artifact and first file reviewers should open.
3. The local rerun command is narrower than rerunning every workflow when possible.
4. The text preserves safe analytical framing and does not imply live operational validation.
5. The final PR description includes the final head SHA, hosted checks, local validation, compatibility impact, rollback path, and any blockers.

## Rollback

Revert the workflow-summary step and this guide if the hosted summary causes shell quoting issues, duplicates existing reviewer output, or creates maintenance noise. Removing the summary should not affect generated artifacts, CLI behavior, model outputs, or API behavior.
