# Common project workflows for MilitaryNNTroopPrediction.
# These targets are intentionally lightweight wrappers around existing safe CLIs.

PYTHON_BIN ?= python3
PIP_BIN ?= $(PYTHON_BIN) -m pip
HOST ?= 127.0.0.1
PORT ?= 8000
ARTIFACT_DIR ?= ci_artifacts

.PHONY: help install-core install-optional configure doctor quickstart api test ci-report openapi examples dashboard bundle-index previews manifest release-notes clean

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
	@printf '  make ci-report         Build the local CI diagnostics bundle\n\n'
	@printf 'Artifacts:\n'
	@printf '  make openapi           Export OpenAPI JSON and Markdown summaries\n'
	@printf '  make examples          Export synthetic API response examples\n'
	@printf '  make dashboard         Export static dashboard mockup HTML\n'
	@printf '  make bundle-index      Export release bundle landing page\n'
	@printf '  make previews          Export lightweight SVG HTML previews\n'
	@printf '  make manifest          Export artifact manifest with SHA-256 hashes\n'
	@printf '  make release-notes     Export manager-friendly release notes\n\n'
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

release-notes:
	$(PYTHON_BIN) -m app.cli.release_notes \
		--health-json $(ARTIFACT_DIR)/release-health.json \
		--manifest-json $(ARTIFACT_DIR)/artifact-manifest.json \
		--markdown-path $(ARTIFACT_DIR)/release-notes.md \
		--json-path $(ARTIFACT_DIR)/release-notes.json

clean:
	rm -rf $(ARTIFACT_DIR) .pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
