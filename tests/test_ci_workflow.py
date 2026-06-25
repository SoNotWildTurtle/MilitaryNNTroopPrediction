from pathlib import Path


WORKFLOW_PATH = Path(".github/workflows/ci.yml")


def test_ci_uses_unified_make_verify_entrypoint():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "make verify ARTIFACT_DIR=ci_artifacts" in workflow
    assert "Run unified verification" in workflow
    assert "bash scripts/test.sh" not in workflow
    assert "bash scripts/ci_report.sh" not in workflow


def test_ci_still_uploads_diagnostic_artifacts():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "actions/upload-artifact@v4" in workflow
    assert "name: ci-diagnostics" in workflow
    assert "path: ci_artifacts/" in workflow
    assert "if-no-files-found: error" in workflow
