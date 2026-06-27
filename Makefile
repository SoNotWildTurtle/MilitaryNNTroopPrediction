# Common project workflows for MilitaryNNTroopPrediction.
# These targets are intentionally lightweight wrappers around existing safe CLIs.

PYTHON_BIN ?= python3
PIP_BIN ?= $(PYTHON_BIN) -m pip
HOST ?= 127.0.0.1
PORT ?= 8000
ARTIFACT_DIR ?= ci_artifacts
TRIAGE_ARTIFACT_DIR ?= ci_artifacts/local-ci
FIXTURE_DIR ?= data/fixtures

.PHONY: help install-core install-optional configure doctor quickstart api test verify ci-triage ci-report openapi examples dashboard bundle-index previews manifest artifact-gap-report provenance-ledger operator-digest release-notes reviewer-handoff operator-readiness operator-status-board operator-session-plan operator-runbook-index operator-next-steps handoff-integrity automation-plan validate-handoff triage-summary synthetic-fixtures clean

help:
	@printf 'MilitaryNNTroopPrediction common tasks\n\n'
	@printf 'Setup:\n'
	@printf '  make install-core      Install minimal API/doctor/CI dependencies\n'
	@printf '  make install-optional  Install full optional ML/dashboard/GIS toolkit\n'
	@printf '  make configure         Create a safe local .env when one is missing\n'
	@printf '  make quickstart        Run the guided conservative first-run flow\n\n'
	@printf 'Validation:\n'
	@printf '  make doctor            Run minimal read-only setup diagnostics\n'
	@printf '  make test              Run local smoke checks and unit tests\n'
	@printf '  make verify            Run doctor, tests, diagnostics, and handoff contract validation\n'
	@printf '  make validate-handoff  Validate generated reviewer-handoff.json\n'
	@printf '  make ci-triage         Print CI failure reproduction and artifact review steps\n'
	@printf '  make ci-report         Build the local CI diagnostics bundle\n\n'
	@printf 'Artifacts:\n'
	@printf '  make openapi           Export OpenAPI JSON and Markdown summaries\n'
	@printf '  make examples          Export synthetic API response examples\n'
	@printf '  make dashboard         Export static dashboard mockup HTML\n'
	@printf '  make bundle-index      Export release bundle landing page\n'
	@printf '  make previews          Export lightweight SVG HTML previews\n'
	@printf '  make manifest          Export artifact manifest with SHA-256 hashes\n'
	@printf '  make artifact-gap-report Audit bundle completeness and suspicious artifacts\n'
	@printf '  make provenance-ledger Export artifact provenance and synthetic/preview labels\n'
	@printf '  make operator-digest   Export concise first-read operator digest\n'
	@printf '  make release-notes     Export manager-friendly release notes\n'
	@printf '  make reviewer-handoff  Export copyable reviewer handoff notes\n'
	@printf '  make operator-readiness Export operator launch/no-launch readiness brief\n'
	@printf '  make operator-status-board Export quick non-technical operator status board\n'
	@printf '  make operator-session-plan Export ranked next-session operator checklist\n'
	@printf '  make operator-runbook-index Export safe command, doc, and artifact map\n'
	@printf '  make operator-next-steps Export ranked operator action plan\n'
	@printf '  make handoff-integrity Export cross-artifact handoff integrity report\n'
	@printf '  make automation-plan   Export safe additive next-run plan\n'
	@printf '  make triage-summary    Export CI triage summary and narrow rerun targets\n'
	@printf '  make synthetic-fixtures Export safe JSONL/CSV fixtures for demos and clients\n\n'
	@printf 'Runtime:\n'
	@printf '  make api               Launch FastAPI on HOST=$(HOST) PORT=$(PORT)\n\n'
	@printf 'Cleanup:\n'
	@printf '  make clean             Remove generated local artifacts and caches\n'

install-core:
	$(PIP_BIN) install -r requirements-core.txt

install-optional:
	$(PIP_BIN) install -r requirements-optional.txt

configure:
	$(PYTHON_BIN) -m app.cli.configure --non-interactive

doctor:
	$(PYTHON_BIN) -m app.cli.doctor --skip-optional --skip-mongo --json

quickstart:
	$(PYTHON_BIN) -m app.cli.quickstart

api:
	$(PYTHON_BIN) -m uvicorn app.api.main:app --host $(HOST) --port $(PORT)

test:
	bash scripts/test.sh

verify: doctor test ci-report validate-handoff
	@printf '\nVerification complete. Review $(ARTIFACT_DIR)/release-bundle-index.html for generated diagnostics.\n'

ci-triage:
	@printf 'CI triage quick path\n\n'
	@printf 'Guide: docs/ci_troubleshooting.md\n\n'
	@printf '1. Install the same lightweight dependency profile used by CI:\n'
	@printf '   make install-core\n\n'
	@printf '2. Reproduce hosted validation locally with an isolated local artifact directory:\n'
	@printf '   make verify ARTIFACT_DIR=$(TRIAGE_ARTIFACT_DIR)\n\n'
	@printf '3. Open the reviewer landing page first:\n'
	@printf '   $(TRIAGE_ARTIFACT_DIR)/release-bundle-index.html\n\n'
	@printf '4. If the bundle is incomplete, inspect the generated handoff, its validation result, gap report, provenance ledger, operator digest, operator status, operator session plan, operator runbook index, operator next steps, uncertainty review packet, handoff integrity report, and triage summary, then rerun the narrow target:\n'
	@printf '   $(TRIAGE_ARTIFACT_DIR)/reviewer-handoff.md\n'
	@printf '   $(TRIAGE_ARTIFACT_DIR)/reviewer-handoff-validation.json\n'
	@printf '   $(TRIAGE_ARTIFACT_DIR)/artifact-gap-report.md\n'
	@printf '   $(TRIAGE_ARTIFACT_DIR)/artifact-provenance-ledger.md\n'
	@printf '   $(TRIAGE_ARTIFACT_DIR)/operator-digest.md\n'
	@printf '   $(TRIAGE_ARTIFACT_DIR)/operator-readiness.md\n'
	@printf '   $(TRIAGE_ARTIFACT_DIR)/operator-status-board.md\n'
	@printf '   $(TRIAGE_ARTIFACT_DIR)/operator-session-plan.md\n'
	@printf '   $(TRIAGE_ARTIFACT_DIR)/operator-runbook-index.md\n'
	@printf '   $(TRIAGE_ARTIFACT_DIR)/operator-next-steps.md\n'
	@printf '   $(TRIAGE_ARTIFACT_DIR)/uncertainty-review-packet.md\n'
	@printf '   $(TRIAGE_ARTIFACT_DIR)/handoff-integrity-report.md\n'
	@printf '   $(TRIAGE_ARTIFACT_DIR)/triage-summary.md\n'
	@printf '   $(TRIAGE_ARTIFACT_DIR)/automation-plan.md\n'
	@printf '   $(TRIAGE_ARTIFACT_DIR)/artifact-manifest.md\n'
	@printf '   make doctor | make test | make ci-report | make validate-handoff | make openapi | make examples | make dashboard | make previews | make manifest | make artifact-gap-report | make provenance-ledger | make operator-digest | make release-notes | make reviewer-handoff | make operator-readiness | make operator-status-board | make operator-session-plan | make operator-runbook-index | make operator-next-steps | make handoff-integrity | make automation-plan | make triage-summary | make synthetic-fixtures\n\n'
	@printf 'Safe-scope reminder: keep triage limited to local setup, deterministic tests, synthetic examples, API contracts, generated artifacts, and documentation.\n'

ci-report:
	ARTIFACT_DIR=$(ARTIFACT_DIR) bash scripts/ci_report.sh

openapi:
	$(PYTHON_BIN) -m app.cli.export_openapi \
		--json-path $(ARTIFACT_DIR)/openapi.json \
		--markdown-path $(ARTIFACT_DIR)/openapi-summary.md

examples:
	$(PYTHON_BIN) -m app.cli.export_api_examples \
		--json-path $(ARTIFACT_DIR)/api-response-examples.json \
		--markdown-path $(ARTIFACT_DIR)/api-response-examples.md

dashboard:
	$(PYTHON_BIN) -m app.cli.export_dashboard_mockup \
		--html-path $(ARTIFACT_DIR)/dashboard-mockup.html

bundle-index:
	$(PYTHON_BIN) -m app.cli.release_bundle_index \
		--artifact-dir $(ARTIFACT_DIR) \
		--html-path $(ARTIFACT_DIR)/release-bundle-index.html

previews:
	$(PYTHON_BIN) -m app.cli.export_html_previews \
		--artifact-dir $(ARTIFACT_DIR) \
		--output-dir $(ARTIFACT_DIR)/previews \
		--markdown-path $(ARTIFACT_DIR)/html-previews.md

manifest:
	$(PYTHON_BIN) -m app.cli.artifact_manifest \
		--artifact-dir $(ARTIFACT_DIR) \
		--json-path $(ARTIFACT_DIR)/artifact-manifest.json \
		--markdown-path $(ARTIFACT_DIR)/artifact-manifest.md

artifact-gap-report:
	$(PYTHON_BIN) -m app.cli.artifact_gap_report \
		--artifact-dir $(ARTIFACT_DIR) \
		--json-path $(ARTIFACT_DIR)/artifact-gap-report.json \
		--markdown-path $(ARTIFACT_DIR)/artifact-gap-report.md

provenance-ledger:
	$(PYTHON_BIN) -m app.cli.artifact_provenance_ledger \
		--artifact-dir $(ARTIFACT_DIR) \
		--json-path $(ARTIFACT_DIR)/artifact-provenance-ledger.json \
		--markdown-path $(ARTIFACT_DIR)/artifact-provenance-ledger.md

operator-digest:
	$(PYTHON_BIN) -m app.cli.operator_digest \
		--artifact-dir $(ARTIFACT_DIR) \
		--markdown-path $(ARTIFACT_DIR)/operator-digest.md \
		--json-path $(ARTIFACT_DIR)/operator-digest.json

release-notes:
	$(PYTHON_BIN) -m app.cli.release_notes \
		--health-json $(ARTIFACT_DIR)/release-health.json \
		--manifest-json $(ARTIFACT_DIR)/artifact-manifest.json \
		--markdown-path $(ARTIFACT_DIR)/release-notes.md \
		--json-path $(ARTIFACT_DIR)/release-notes.json

reviewer-handoff:
	$(PYTHON_BIN) -m app.cli.reviewer_handoff \
		--artifact-dir $(ARTIFACT_DIR) \
		--markdown-path $(ARTIFACT_DIR)/reviewer-handoff.md \
		--json-path $(ARTIFACT_DIR)/reviewer-handoff.json

operator-readiness:
	$(PYTHON_BIN) -m app.cli.operator_readiness \
		--artifact-dir $(ARTIFACT_DIR) \
		--markdown-path $(ARTIFACT_DIR)/operator-readiness.md \
		--json-path $(ARTIFACT_DIR)/operator-readiness.json

operator-status-board:
	$(PYTHON_BIN) -m app.cli.operator_status_board \
		--artifact-dir $(ARTIFACT_DIR) \
		--markdown-path $(ARTIFACT_DIR)/operator-status-board.md \
		--json-path $(ARTIFACT_DIR)/operator-status-board.json

operator-session-plan:
	$(PYTHON_BIN) -m app.cli.operator_session_plan \
		--artifact-dir $(ARTIFACT_DIR) \
		--markdown-path $(ARTIFACT_DIR)/operator-session-plan.md \
		--json-path $(ARTIFACT_DIR)/operator-session-plan.json

operator-runbook-index:
	$(PYTHON_BIN) -m app.cli.operator_runbook_index \
		--artifact-dir $(ARTIFACT_DIR) \
		--markdown-path $(ARTIFACT_DIR)/operator-runbook-index.md \
		--json-path $(ARTIFACT_DIR)/operator-runbook-index.json

operator-next-steps:
	$(PYTHON_BIN) -m app.cli.operator_next_steps \
		--artifact-dir $(ARTIFACT_DIR) \
		--markdown-path $(ARTIFACT_DIR)/operator-next-steps.md \
		--json-path $(ARTIFACT_DIR)/operator-next-steps.json

handoff-integrity:
	$(PYTHON_BIN) -m app.cli.handoff_integrity_report \
		--artifact-dir $(ARTIFACT_DIR) \
		--markdown-path $(ARTIFACT_DIR)/handoff-integrity-report.md \
		--json-path $(ARTIFACT_DIR)/handoff-integrity-report.json

automation-plan:
	$(PYTHON_BIN) -m app.cli.automation_plan \
		--artifact-dir $(ARTIFACT_DIR) \
		--markdown-path $(ARTIFACT_DIR)/automation-plan.md \
		--json-path $(ARTIFACT_DIR)/automation-plan.json

validate-handoff:
	$(PYTHON_BIN) scripts/validate_reviewer_handoff.py $(ARTIFACT_DIR)/reviewer-handoff.json --json

triage-summary:
	$(PYTHON_BIN) -m app.cli.triage_summary \
		--artifact-dir $(ARTIFACT_DIR) \
		--markdown-path $(ARTIFACT_DIR)/triage-summary.md \
		--json-path $(ARTIFACT_DIR)/triage-summary.json

synthetic-fixtures:
	$(PYTHON_BIN) -m app.cli.synthetic_data_fixtures --output-dir $(FIXTURE_DIR)

clean:
	rm -rf $(ARTIFACT_DIR) $(FIXTURE_DIR) .pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
