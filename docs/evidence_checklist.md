# Evidence Checklist

The evidence checklist is a deterministic, local-only review artifact for validating whether a generated diagnostics bundle is ready for defensive analytical handoff.

It is intentionally conservative. The command only reads local bundle metadata and writes Markdown/JSON summaries. It does not collect live data, run model inference, call network services, alter source artifacts, or claim operational certainty.

## Generate the checklist

The checklist is now part of the standard diagnostics bundle:

```bash
make ci-report
# writes ci_artifacts/evidence-checklist.md and ci_artifacts/evidence-checklist.json
```

You can also run it directly when reviewing a custom artifact directory:

```bash
python -m app.cli.evidence_checklist \
  --artifact-dir ci_artifacts \
  --markdown-path ci_artifacts/evidence-checklist.md \
  --json-path ci_artifacts/evidence-checklist.json
```

Or use the dedicated Make target:

```bash
make evidence-checklist ARTIFACT_DIR=ci_artifacts
```

The default output names are `evidence-checklist.md` and `evidence-checklist.json` inside the selected artifact directory.

## CI and release-bundle wiring

Hosted CI smoke-checks the CLI and `scripts/ci_report.sh` includes both the CLI help text and generated Markdown/JSON checklist in the uploaded `ci-diagnostics` bundle. The local `make ci-triage` helper also points reviewers to the checklist when a bundle is incomplete or needs human evidence review.

This makes the checklist available to non-technical reviewers from the same `release-bundle-index.html` landing page and avoids a separate manual command during handoff.

## What it checks

The checklist verifies that the bundle has baseline evidence for:

- required review artifacts, including manifest, provenance, triage, reviewer handoff, uncertainty review, and handoff integrity reports;
- manifest completeness and unexpected/suspicious artifact review;
- provenance labels that separate generated review evidence from synthetic fixtures and previews;
- uncertainty actions that should be acknowledged before external handoff;
- cross-artifact handoff integrity status;
- triage and reviewer handoff readiness.

Statuses are deliberately simple:

- `pass` means the evidence item is present and ready for review;
- `warn` means a human should inspect or acknowledge the item before sharing;
- `fail` means the bundle should not be handed off until the narrow generator or evidence source is repaired.

## Safe analytical framing

Checklist output should be treated as release-review evidence, not model evidence. It confirms the presence and consistency of generated artifacts; it does not validate the truth of predictions, live data quality, or operational conclusions.

Predictive outputs from the broader project must remain framed as analytical estimates with uncertainty. Synthetic examples and placeholder records must not be presented as operational truth.

## Rollback

The feature is additive. To roll back, stop invoking `make evidence-checklist` or `python -m app.cli.evidence_checklist` and remove the generated `evidence-checklist.md/json` files from local artifact directories. If CI bundle inclusion must be reverted, remove the `evidence_checklist` calls from `scripts/ci_report.sh`, the Make target, and the CI smoke step; existing diagnostics and prediction workflows remain unchanged.
