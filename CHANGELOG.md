# Changelog

## Unreleased

- Added navigation coverage for the run decision record schema contract so reviewers can find the JSON contract, merge-evidence expectations, validation plan, compatibility notes, rollback path, and safe analytical framing from the existing run decision record guide.
- Documented strict `implementation_acceptance_handoff --strict` validation mode and added static regression coverage so reviewers know the offline exit-code contract, readiness requirements, merge-blocker behavior, rollback path, and safe analytical limits before wiring it into release gates.
- Added evidence-status diagnostics to the offline `implementation_acceptance_handoff` JSON/Markdown outputs so reviewers can see status counts, known statuses, unknown status warnings, affected gate IDs, and merge blockers for edited manifests without scraping completed evidence rows.
- Added `docs/implementation_acceptance_schema.md` and static regression coverage so downstream reviewers and release-bundle consumers can validate implementation acceptance JSON fields, gate-evidence readiness rules, compatibility expectations, rollback guidance, and safe analytical framing without scraping CLI code.
- Promoted implementation acceptance checklist and handoff artifacts to first-class diagnostics provenance/gap-report artifacts so reviewers can see missing, undersized, and provenance-labeled acceptance evidence in the standard bundle without treating it as live analytical truth.
