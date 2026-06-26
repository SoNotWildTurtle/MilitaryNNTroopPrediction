# Diagnostic artifact gap reports

The artifact gap report is a lightweight reviewer safety check for generated
CI/local diagnostic bundles. It reads `artifact-manifest.json` and produces a
short JSON and Markdown report that highlights:

- expected artifacts that are missing from the bundle,
- generated files that are empty,
- expected files that are present but suspiciously small, and
- a single recommended next step for the reviewer.

This is intended to make handoffs safer and faster. The manifest proves what was
generated; the gap report tells a reviewer whether the bundle looks complete
enough to trust before opening larger HTML, Markdown, or JSON artifacts.

## Usage

```bash
python -m app.cli.artifact_gap_report --artifact-dir ci_artifacts
# or
make artifact-gap-report
```

By default the command writes:

- `ci_artifacts/artifact-gap-report.json`
- `ci_artifacts/artifact-gap-report.md`

Use `--fail-on-gap` in stricter local gates when missing or empty expected
artifacts should return a non-zero exit status:

```bash
python -m app.cli.artifact_gap_report --artifact-dir ci_artifacts --fail-on-gap
```

The default CI report generation includes this report after the final manifest is
built, so the reviewer handoff can point to a concise bundle completeness check.
