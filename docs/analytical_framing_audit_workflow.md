# Analytical Framing Audit Workflow

The `analytical_framing_audit` CLI scans generated Markdown, text, and JSON diagnostics for language that could overstate certainty, imply live operational use, or omit safe analytical scope. The workflow is intentionally offline and deterministic.

## What the workflow validates

The dedicated GitHub Actions workflow `.github/workflows/analytical-framing-audit.yml` performs a narrow smoke check that:

1. Installs the core dependency profile used by the main CI workflow.
2. Compiles the application and test package.
3. Seeds a small synthetic diagnostic note with explicit analytical-scope language.
4. Runs `tests.test_analytical_framing_audit`.
5. Exports `ci_artifacts/analytical-framing-audit.md` and `ci_artifacts/analytical-framing-audit.json`.
6. Uploads the generated audit artifacts for reviewer inspection, even if a later step fails.

## Local reproduction

Run the same focused validation locally with:

```bash
python -m pip install -r requirements-core.txt
python -m compileall app tests
python -m unittest tests.test_analytical_framing_audit
mkdir -p ci_artifacts/framing-audit-seed
cat > ci_artifacts/framing-audit-seed/scope-note.md <<'EOF'
# Analytical scope note

These generated diagnostics are analytical estimates for lawful defensive review.
They use synthetic examples where needed and must not be treated as operational certainty.
EOF
python -m app.cli.analytical_framing_audit \
  --artifact-dir ci_artifacts \
  --markdown-path ci_artifacts/analytical-framing-audit.md \
  --json-path ci_artifacts/analytical-framing-audit.json
```

## Review guidance

Treat findings as wording-review prompts, not truth labels. A warning means the reviewer should inspect the referenced artifact line and decide whether the text needs uncertainty, provenance, synthetic-data, or non-operational caveats before handoff.

This audit does not run collection, prediction, targeting, live feeds, model training, deployment, or database access. It only reads local diagnostic artifacts and writes review artifacts.

## Compatibility and rollback

The workflow is additive. It does not change existing commands, APIs, generated schemas, or the main smoke-test workflow. To roll it back, remove `.github/workflows/analytical-framing-audit.yml` and this document.
