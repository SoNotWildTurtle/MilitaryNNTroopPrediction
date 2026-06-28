# Handoff closeout summary

The handoff closeout summary is a lightweight offline artifact for the final review check before an analytical bundle is attached to a PR or handed to another reviewer. It composes the existing decision log, validation receipt, readiness scorecard, and artifact manifest into one status line plus a small Markdown table.

This workflow is conservative. It does not run prediction, connect to live sources, validate intelligence, or imply certainty. It only summarizes whether generated review artifacts are present, ready, blocked, or still need human review.

## Generate the summary

After building diagnostics, run:

```bash
python -m app.cli.handoff_closeout_summary --artifact-dir ci_artifacts
```

By default the command writes:

- `ci_artifacts/handoff-closeout-summary.md` for review notes.
- `ci_artifacts/handoff-closeout-summary.json` for automation and structured review.
- `ci_artifacts/handoff-closeout-summary.txt` for a one-line status that can be copied into PR notes or handoff notes.

Use explicit paths when exporting into a separate bundle:

```bash
python -m app.cli.handoff_closeout_summary \
  --artifact-dir ci_artifacts \
  --markdown-path /tmp/handoff-closeout-summary.md \
  --json-path /tmp/handoff-closeout-summary.json \
  --text-path /tmp/handoff-closeout-summary.txt
```

## Inputs

The closeout summary reads these generated files from the selected artifact directory:

| Input | Why it matters |
| --- | --- |
| `decision-log.json` | Captures the ready/blocked/needs-review analytical decision from cross-artifact diagnostics. |
| `handoff-validation-receipt.json` | Captures final validation status and blockers before review closeout. |
| `handoff-readiness-scorecard.json` | Captures weighted readiness signals when the bundle includes scorecard output. |
| `artifact-manifest.json` | Confirms the bundle has a generated inventory with reproducibility metadata. |

Missing or invalid inputs block the closeout. Warning-bearing inputs move the closeout to `needs_review` so a reviewer can document accepted limitations before handoff.

## Recommended review use

1. Build diagnostics with `make ci-report` or use the CI diagnostics bundle.
2. Generate the closeout summary.
3. Attach the Markdown or text output to the PR or handoff notes with the decision log and validation receipt.
4. If status is `blocked`, repair the missing or invalid artifact and regenerate diagnostics.
5. If status is `needs_review`, review the warning rows and document accepted limitations.
6. If status is `ready`, treat it as a reproducibility signal only, not as proof of live-world accuracy.

## Rollback

This feature is additive. To roll back, stop invoking `python -m app.cli.handoff_closeout_summary` and remove the generated `handoff-closeout-summary.*` files from local or CI artifact bundles. Existing diagnostics, APIs, and prior CLI tools are unchanged.
