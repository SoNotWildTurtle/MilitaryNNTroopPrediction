from pathlib import Path


MAKEFILE_PATH = Path("Makefile")
README_PATH = Path("README.md")
CONTRIBUTING_PATH = Path("CONTRIBUTING.md")
COMMON_TASKS_PATH = Path("docs/common_tasks.md")
CI_TROUBLESHOOTING_PATH = Path("docs/ci_troubleshooting.md")


def test_makefile_exposes_ci_triage_target():
    makefile = MAKEFILE_PATH.read_text(encoding="utf-8")

    assert "TRIAGE_ARTIFACT_DIR ?= ci_artifacts/local-ci" in makefile
    assert ".PHONY:" in makefile and "ci-triage" in makefile
    assert "make ci-triage" in makefile
    assert "ci-triage:" in makefile
    assert "docs/ci_troubleshooting.md" in makefile
    assert "make verify ARTIFACT_DIR=$(TRIAGE_ARTIFACT_DIR)" in makefile
    assert "$(TRIAGE_ARTIFACT_DIR)/release-bundle-index.html" in makefile
    assert "$(TRIAGE_ARTIFACT_DIR)/artifact-manifest.md" in makefile


def test_ci_triage_docs_are_linked_from_user_facing_guides():
    readme = README_PATH.read_text(encoding="utf-8")
    contributing = CONTRIBUTING_PATH.read_text(encoding="utf-8")
    common_tasks = COMMON_TASKS_PATH.read_text(encoding="utf-8")

    for document in (readme, contributing, common_tasks):
        assert "make ci-triage" in document
        assert "docs/ci_troubleshooting.md" in document


def test_ci_troubleshooting_guide_mentions_helper_target():
    guide = CI_TROUBLESHOOTING_PATH.read_text(encoding="utf-8")

    assert "make ci-triage" in guide
    assert "make verify ARTIFACT_DIR=ci_artifacts/local-ci" in guide
    assert "ci_artifacts/local-ci/release-bundle-index.html" in guide
