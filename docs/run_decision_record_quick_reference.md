# Run decision record quick reference

Use this guide when a reviewer or automation run needs the shortest safe path from a selected maintenance increment to merge-ready evidence. It is a navigation layer only: it does not collect live data, run detection, run prediction, make operational claims, or replace the underlying schema and runbook documents.

## Primary documents

| Need | Start here | Why it matters |
| --- | --- | --- |
| Select the next cohesive additive increment | `docs/run_continuity_brief.md` | Summarizes roadmap, changelog, and decision-register context before choosing work. |
| Record the selected candidate and merge evidence | `docs/run_decision_record.md` | Explains the machine-readable record emitted by the candidate CLI, including validation, blockers, compatibility, rollback, and next follow-up fields. |
| Validate the JSON contract | `docs/run_decision_record_schema.md` | Defines required schema fields such as `required_evidence_before_merge`, `validation_plan`, `merge_blockers`, `compatibility_notes`, and `rollback_notes`. |
| Convert the selected increment into acceptance gates | `docs/implementation_acceptance_checklist.md` | Turns the selected candidate into reviewer-facing acceptance gates and evidence expectations. |
| Validate acceptance handoff artifacts | `docs/implementation_acceptance_schema.md` | Documents the implementation-acceptance JSON fields, gate readiness rules, and safe analytical framing. |

## Safe handoff sequence

1. Generate or review the continuity brief before selecting work so the run does not duplicate recent process-only changes.
2. Generate the next-increment candidate matrix and decision record with `python -m app.cli.next_increment_candidates --no-markdown --json-path /tmp/next-increment-candidates.json --decision-record-path /tmp/run-decision-record.json`.
3. Check the decision record against `docs/run_decision_record_schema.md`, especially `required_evidence_before_merge`, `validation_plan`, `merge_blockers`, `compatibility_notes`, and `rollback_notes`.
4. Convert the selected candidate into acceptance gates with the implementation acceptance checklist before opening a PR.
5. Treat missing hosted checks, unavailable required validation, unresolved review blockers, incompatible target branches, or unsafe analytical framing as merge blockers until resolved on the final head SHA.

## Compatibility and rollback

This quick reference is additive documentation. Revert only this file if the navigation layer becomes stale; the underlying decision-record CLI, schema guide, implementation acceptance guides, tests, and runtime behavior remain unchanged.

## Analytical safety note

Decision records and acceptance handoff artifacts are repository-maintenance evidence. They should communicate uncertainty, validation status, blockers, and reviewer handoff state; they must not be presented as operational targeting guidance or certainty about real-world troop movement.
