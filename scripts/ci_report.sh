#!/usr/bin/env bash
# Generate lightweight CI diagnostics and save them as workflow artifacts.
set -euo pipefail
trap 'status=$?; echo "::error::ci_report.sh failed at line ${LINENO}: ${BASH_COMMAND}" >&2; exit ${status}' ERR

PYTHON_BIN=${PYTHON_BIN:-python3}
ARTIFACT_DIR=${ARTIFACT_DIR:-ci_artifacts}

mkdir -p "${ARTIFACT_DIR}"

"${PYTHON_BIN}" --version > "${ARTIFACT_DIR}/python-version.txt"
"${PYTHON_BIN}" -m pip --version > "${ARTIFACT_DIR}/pip-version.txt"
"${PYTHON_BIN}" -m pip freeze > "${ARTIFACT_DIR}/pip-freeze.txt"
"${PYTHON_BIN}" -m app.cli.doctor --skip-optional --skip-mongo --skip-env-files --json > "${ARTIFACT_DIR}/doctor-minimal.json"
"${PYTHON_BIN}" -m app.cli.release_health --markdown-path "${ARTIFACT_DIR}/release-health.md" --json-path "${ARTIFACT_DIR}/release-health.json"
"${PYTHON_BIN}" -m app.cli.export_openapi --json-path "${ARTIFACT_DIR}/openapi.json" --markdown-path "${ARTIFACT_DIR}/openapi-summary.md"
"${PYTHON_BIN}" -m app.cli.export_api_examples --json-path "${ARTIFACT_DIR}/api-response-examples.json" --markdown-path "${ARTIFACT_DIR}/api-response-examples.md"
"${PYTHON_BIN}" -m app.cli.export_dashboard_mockup --html-path "${ARTIFACT_DIR}/dashboard-mockup.html"
"${PYTHON_BIN}" -m app.cli.synthetic_data_fixtures --output-dir "${ARTIFACT_DIR}/synthetic-fixtures" --json > "${ARTIFACT_DIR}/synthetic-fixtures-summary.json"
"${PYTHON_BIN}" -m app.cli.quickstart --help > "${ARTIFACT_DIR}/quickstart-help.txt"
"${PYTHON_BIN}" -m app.cli.doctor --help > "${ARTIFACT_DIR}/doctor-help.txt"
"${PYTHON_BIN}" -m app.cli.release_health --help > "${ARTIFACT_DIR}/release-health-help.txt"
"${PYTHON_BIN}" -m app.cli.release_notes --help > "${ARTIFACT_DIR}/release-notes-help.txt"
"${PYTHON_BIN}" -m app.cli.reviewer_handoff --help > "${ARTIFACT_DIR}/reviewer-handoff-help.txt"
"${PYTHON_BIN}" -m app.cli.operator_digest --help > "${ARTIFACT_DIR}/operator-digest-help.txt"
"${PYTHON_BIN}" -m app.cli.operator_readiness --help > "${ARTIFACT_DIR}/operator-readiness-help.txt"
"${PYTHON_BIN}" -m app.cli.operator_status_board --help > "${ARTIFACT_DIR}/operator-status-board-help.txt"
"${PYTHON_BIN}" -m app.cli.operator_session_plan --help > "${ARTIFACT_DIR}/operator-session-plan-help.txt"
"${PYTHON_BIN}" -m app.cli.operator_runbook_index --help > "${ARTIFACT_DIR}/operator-runbook-index-help.txt"
"${PYTHON_BIN}" -m app.cli.operator_next_steps --help > "${ARTIFACT_DIR}/operator-next-steps-help.txt"
"${PYTHON_BIN}" -m app.cli.uncertainty_review_packet --help > "${ARTIFACT_DIR}/uncertainty-review-packet-help.txt"
"${PYTHON_BIN}" -m app.cli.handoff_integrity_report --help > "${ARTIFACT_DIR}/handoff-integrity-report-help.txt"
"${PYTHON_BIN}" -m app.cli.evidence_checklist --help > "${ARTIFACT_DIR}/evidence-checklist-help.txt"
"${PYTHON_BIN}" -m app.cli.handoff_validation_receipt --help > "${ARTIFACT_DIR}/handoff-validation-receipt-help.txt"
"${PYTHON_BIN}" -m app.cli.automation_plan --help > "${ARTIFACT_DIR}/automation-plan-help.txt"
"${PYTHON_BIN}" -m app.cli.triage_summary --help > "${ARTIFACT_DIR}/triage-summary-help.txt"
"${PYTHON_BIN}" -m app.cli.artifact_gap_report --help > "${ARTIFACT_DIR}/artifact-gap-report-help.txt"
"${PYTHON_BIN}" -m app.cli.artifact_provenance_ledger --help > "${ARTIFACT_DIR}/artifact-provenance-ledger-help.txt"
"${PYTHON_BIN}" -m app.cli.synthetic_data_fixtures --help > "${ARTIFACT_DIR}/synthetic-data-fixtures-help.txt"
"${PYTHON_BIN}" -m app.cli.export_openapi --help > "${ARTIFACT_DIR}/export-openapi-help.txt"
"${PYTHON_BIN}" -m app.cli.export_api_examples --help > "${ARTIFACT_DIR}/export-api-examples-help.txt"
"${PYTHON_BIN}" -m app.cli.export_dashboard_mockup --help > "${ARTIFACT_DIR}/export-dashboard-mockup-help.txt"
"${PYTHON_BIN}" -m app.cli.release_bundle_index --help > "${ARTIFACT_DIR}/release-bundle-index-help.txt"
"${PYTHON_BIN}" -m app.cli.artifact_manifest --help > "${ARTIFACT_DIR}/artifact-manifest-help.txt"
"${PYTHON_BIN}" -m app.cli.export_html_previews --help > "${ARTIFACT_DIR}/export-html-previews-help.txt"

cat > "${ARTIFACT_DIR}/summary.txt" <<'SUMMARY'
MilitaryNNTroopPrediction CI diagnostic artifact bundle

Files:
- python-version.txt: Python interpreter version used by CI.
- pip-version.txt: pip version used by CI.
- pip-freeze.txt: installed package versions for reproducibility.
- doctor-minimal.json: machine-readable core setup diagnostics.
- release health/release notes/reviewer handoff/operator digest/operator readiness/operator status board/operator session plan/operator runbook index/operator next steps/uncertainty review packet/handoff integrity report/evidence checklist/handoff validation receipt/automation plan artifacts: generated local readiness, review, uncertainty, command-map, cross-artifact integrity, baseline evidence, final receipt, and next-run guidance.
- reviewer-handoff-validation.txt/json: reviewer handoff contract validation results.
- triage-summary.md/json: CI failure triage summary with narrow rerun targets.
- artifact-gap-report.md/json: diagnostic bundle completeness and suspicious-artifact report.
- artifact-provenance-ledger.md/json: diagnostic bundle provenance labels for generated, synthetic, preview, and review artifacts.
- openapi.json/openapi-summary.md: API contract exports.
- api-response-examples.json/md: synthetic API response examples.
- dashboard-mockup.html: self-contained static dashboard preview.
- synthetic-fixtures/*: safe JSONL/CSV fixture records for local demos and client tests.
- release-bundle-index.html/html-previews.md/previews/*.svg: dependency-free artifact landing page and static previews.
- artifact-manifest.json/md: machine-readable and human-readable artifact manifests with sizes and SHA-256 hashes.
- *-help.txt: current CLI help output for supported operator and artifact commands.
SUMMARY

"${PYTHON_BIN}" -m app.cli.release_bundle_index --artifact-dir "${ARTIFACT_DIR}" --html-path "${ARTIFACT_DIR}/release-bundle-index.html"
"${PYTHON_BIN}" -m app.cli.export_html_previews --artifact-dir "${ARTIFACT_DIR}" --markdown-path "${ARTIFACT_DIR}/html-previews.md"
"${PYTHON_BIN}" -m app.cli.artifact_manifest --artifact-dir "${ARTIFACT_DIR}" --json-path "${ARTIFACT_DIR}/artifact-manifest.json" --markdown-path "${ARTIFACT_DIR}/artifact-manifest.md"
"${PYTHON_BIN}" -m app.cli.artifact_provenance_ledger --artifact-dir "${ARTIFACT_DIR}" --json-path "${ARTIFACT_DIR}/artifact-provenance-ledger.json" --markdown-path "${ARTIFACT_DIR}/artifact-provenance-ledger.md"
"${PYTHON_BIN}" -m app.cli.release_notes --health-json "${ARTIFACT_DIR}/release-health.json" --manifest-json "${ARTIFACT_DIR}/artifact-manifest.json" --markdown-path "${ARTIFACT_DIR}/release-notes.md" --json-path "${ARTIFACT_DIR}/release-notes.json"
"${PYTHON_BIN}" -m app.cli.triage_summary --artifact-dir "${ARTIFACT_DIR}" --health-json "${ARTIFACT_DIR}/release-health.json" --manifest-json "${ARTIFACT_DIR}/artifact-manifest.json" --markdown-path "${ARTIFACT_DIR}/triage-summary.md" --json-path "${ARTIFACT_DIR}/triage-summary.json"
"${PYTHON_BIN}" -m app.cli.reviewer_handoff --artifact-dir "${ARTIFACT_DIR}" --markdown-path "${ARTIFACT_DIR}/reviewer-handoff.md" --json-path "${ARTIFACT_DIR}/reviewer-handoff.json"
"${PYTHON_BIN}" -m app.cli.operator_digest --artifact-dir "${ARTIFACT_DIR}" --markdown-path "${ARTIFACT_DIR}/operator-digest.md" --json-path "${ARTIFACT_DIR}/operator-digest.json"
"${PYTHON_BIN}" -m app.cli.operator_readiness --artifact-dir "${ARTIFACT_DIR}" --markdown-path "${ARTIFACT_DIR}/operator-readiness.md" --json-path "${ARTIFACT_DIR}/operator-readiness.json"
"${PYTHON_BIN}" -m app.cli.automation_plan --artifact-dir "${ARTIFACT_DIR}" --markdown-path "${ARTIFACT_DIR}/automation-plan.md" --json-path "${ARTIFACT_DIR}/automation-plan.json"
"${PYTHON_BIN}" -m app.cli.operator_status_board --artifact-dir "${ARTIFACT_DIR}" --markdown-path "${ARTIFACT_DIR}/operator-status-board.md" --json-path "${ARTIFACT_DIR}/operator-status-board.json"
"${PYTHON_BIN}" -m app.cli.operator_session_plan --artifact-dir "${ARTIFACT_DIR}" --markdown-path "${ARTIFACT_DIR}/operator-session-plan.md" --json-path "${ARTIFACT_DIR}/operator-session-plan.json"
"${PYTHON_BIN}" -m app.cli.operator_runbook_index --artifact-dir "${ARTIFACT_DIR}" --markdown-path "${ARTIFACT_DIR}/operator-runbook-index.md" --json-path "${ARTIFACT_DIR}/operator-runbook-index.json"
"${PYTHON_BIN}" -m app.cli.operator_next_steps --artifact-dir "${ARTIFACT_DIR}" --markdown-path "${ARTIFACT_DIR}/operator-next-steps.md" --json-path "${ARTIFACT_DIR}/operator-next-steps.json"
"${PYTHON_BIN}" -m app.cli.uncertainty_review_packet --artifact-dir "${ARTIFACT_DIR}" --markdown-path "${ARTIFACT_DIR}/uncertainty-review-packet.md" --json-path "${ARTIFACT_DIR}/uncertainty-review-packet.json"
"${PYTHON_BIN}" -m app.cli.handoff_integrity_report --artifact-dir "${ARTIFACT_DIR}" --markdown-path "${ARTIFACT_DIR}/handoff-integrity-report.md" --json-path "${ARTIFACT_DIR}/handoff-integrity-report.json"
"${PYTHON_BIN}" -m app.cli.evidence_checklist --artifact-dir "${ARTIFACT_DIR}" --markdown-path "${ARTIFACT_DIR}/evidence-checklist.md" --json-path "${ARTIFACT_DIR}/evidence-checklist.json"
"${PYTHON_BIN}" scripts/validate_reviewer_handoff.py "${ARTIFACT_DIR}/reviewer-handoff.json" > "${ARTIFACT_DIR}/reviewer-handoff-validation.txt"
"${PYTHON_BIN}" scripts/validate_reviewer_handoff.py "${ARTIFACT_DIR}/reviewer-handoff.json" --json > "${ARTIFACT_DIR}/reviewer-handoff-validation.json"
"${PYTHON_BIN}" -m app.cli.artifact_manifest --artifact-dir "${ARTIFACT_DIR}" --json-path "${ARTIFACT_DIR}/artifact-manifest.json" --markdown-path "${ARTIFACT_DIR}/artifact-manifest.md"
"${PYTHON_BIN}" -m app.cli.artifact_provenance_ledger --artifact-dir "${ARTIFACT_DIR}" --json-path "${ARTIFACT_DIR}/artifact-provenance-ledger.json" --markdown-path "${ARTIFACT_DIR}/artifact-provenance-ledger.md"
"${PYTHON_BIN}" -m app.cli.artifact_gap_report --artifact-dir "${ARTIFACT_DIR}" --json-path "${ARTIFACT_DIR}/artifact-gap-report.json" --markdown-path "${ARTIFACT_DIR}/artifact-gap-report.md"
"${PYTHON_BIN}" -m app.cli.operator_digest --artifact-dir "${ARTIFACT_DIR}" --markdown-path "${ARTIFACT_DIR}/operator-digest.md" --json-path "${ARTIFACT_DIR}/operator-digest.json"
"${PYTHON_BIN}" -m app.cli.operator_status_board --artifact-dir "${ARTIFACT_DIR}" --markdown-path "${ARTIFACT_DIR}/operator-status-board.md" --json-path "${ARTIFACT_DIR}/operator-status-board.json"
"${PYTHON_BIN}" -m app.cli.operator_session_plan --artifact-dir "${ARTIFACT_DIR}" --markdown-path "${ARTIFACT_DIR}/operator-session-plan.md" --json-path "${ARTIFACT_DIR}/operator-session-plan.json"
"${PYTHON_BIN}" -m app.cli.operator_runbook_index --artifact-dir "${ARTIFACT_DIR}" --markdown-path "${ARTIFACT_DIR}/operator-runbook-index.md" --json-path "${ARTIFACT_DIR}/operator-runbook-index.json"
"${PYTHON_BIN}" -m app.cli.operator_next_steps --artifact-dir "${ARTIFACT_DIR}" --markdown-path "${ARTIFACT_DIR}/operator-next-steps.md" --json-path "${ARTIFACT_DIR}/operator-next-steps.json"
"${PYTHON_BIN}" -m app.cli.uncertainty_review_packet --artifact-dir "${ARTIFACT_DIR}" --markdown-path "${ARTIFACT_DIR}/uncertainty-review-packet.md" --json-path "${ARTIFACT_DIR}/uncertainty-review-packet.json"
"${PYTHON_BIN}" -m app.cli.handoff_integrity_report --artifact-dir "${ARTIFACT_DIR}" --markdown-path "${ARTIFACT_DIR}/handoff-integrity-report.md" --json-path "${ARTIFACT_DIR}/handoff-integrity-report.json"
"${PYTHON_BIN}" -m app.cli.evidence_checklist --artifact-dir "${ARTIFACT_DIR}" --markdown-path "${ARTIFACT_DIR}/evidence-checklist.md" --json-path "${ARTIFACT_DIR}/evidence-checklist.json"
"${PYTHON_BIN}" -m app.cli.artifact_manifest --artifact-dir "${ARTIFACT_DIR}" --json-path "${ARTIFACT_DIR}/artifact-manifest.json" --markdown-path "${ARTIFACT_DIR}/artifact-manifest.md"
"${PYTHON_BIN}" -m app.cli.artifact_provenance_ledger --artifact-dir "${ARTIFACT_DIR}" --json-path "${ARTIFACT_DIR}/artifact-provenance-ledger.json" --markdown-path "${ARTIFACT_DIR}/artifact-provenance-ledger.md"
"${PYTHON_BIN}" -m app.cli.handoff_validation_receipt --artifact-dir "${ARTIFACT_DIR}" --markdown-path "${ARTIFACT_DIR}/handoff-validation-receipt.md" --json-path "${ARTIFACT_DIR}/handoff-validation-receipt.json"
"${PYTHON_BIN}" -m app.cli.artifact_manifest --artifact-dir "${ARTIFACT_DIR}" --json-path "${ARTIFACT_DIR}/artifact-manifest.json" --markdown-path "${ARTIFACT_DIR}/artifact-manifest.md"
"${PYTHON_BIN}" -m app.cli.artifact_provenance_ledger --artifact-dir "${ARTIFACT_DIR}" --json-path "${ARTIFACT_DIR}/artifact-provenance-ledger.json" --markdown-path "${ARTIFACT_DIR}/artifact-provenance-ledger.md"

printf 'Wrote CI diagnostics to %s\n' "${ARTIFACT_DIR}"
