# Analytical Framing Audit

`app.cli.analytical_framing_audit` is an offline review aid for generated diagnostic bundles. It scans Markdown, text, and JSON artifacts for wording that could overstate certainty, imply live operational use, or omit basic analytical-scope caveats.

The audit is intentionally conservative and local-only. It does not collect data, connect to services, run models, validate ground truth, or provide operational direction. It is meant to help reviewers make handoff language clearer, safer, and easier to explain.

## Run it

```bash
python -m app.cli.analytical_framing_audit --artifact-dir ci_artifacts
```

The default outputs are:

- `ci_artifacts/analytical-framing-audit.md`
- `ci_artifacts/analytical-framing-audit.json`

You can narrow the scanned artifact types when debugging a specific generator:

```bash
python -m app.cli.analytical_framing_audit \
  --artifact-dir ci_artifacts \
  --include-pattern '*.md'
```

## What it flags

The audit currently reports:

- warning findings for overconfident certainty language;
- warning findings for operationally framed phrases that should be rewritten as defensive analytical review language;
- warning findings for authority overclaims such as treating generated artifacts as official or live truth;
- informational findings when a file has no standard safe-scope terms;
- informational findings when predictive language appears without uncertainty or estimate language in the same artifact.

A warning sets the audit status to `needs_review`. Informational findings keep the audit `ready` while still giving reviewers useful cleanup notes.

## Reviewer workflow

1. Generate or download the diagnostics bundle.
2. Run the audit against the artifact directory.
3. Review warning findings first.
4. Rewrite generated handoff text to emphasize analytical estimates, uncertainty, data provenance, synthetic fixtures, and non-operational scope.
5. Regenerate the bundle and rerun the audit before PR merge or external handoff.

## Safe-scope reminder

The output is a language-quality diagnostic. It does not verify whether any prediction or record is true, current, complete, or operationally usable. Predictive outputs should remain framed as analytical estimates with uncertainty, assumptions, and provenance.
