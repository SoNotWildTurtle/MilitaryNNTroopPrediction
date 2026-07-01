# Run Decision Record Bundle Targets

Use this guide when reviewing `run-decision-record.json` inside a CI diagnostics or local release bundle. It explains where the decision-record family appears, which artifacts should be checked together, and what evidence is still required before an implementation PR can merge.

The guide is offline-only repository-maintenance documentation. It does not fetch imagery, connect to OSINT feeds, run detections, run predictions, assign operational tasks, or claim that analytical estimates are true.

## Primary bundle targets

| Bundle target | Producer | Review purpose |
| --- | --- | --- |
| `next-increment-candidates.md` | `python -m app.cli.next_increment_candidates` | Human-readable candidate matrix for the next cohesive additive increment. |
| `next-increment-candidates.json` | `python -m app.cli.next_increment_candidates` | Machine-readable candidate recipes, roadmap/changelog context, blockers, and safe scope. |
| `run-decision-record.json` | `python -m app.cli.next_increment_candidates --decision-record-path ...` | Selected candidate, merge evidence contract, validation plan, blockers, rollback notes, and follow-up work. |
| `implementation-acceptance-checklist.md` | `python -m app.cli.implementation_acceptance_checklist` | Human-readable acceptance gates derived from the selected decision record. |
| `implementation-acceptance-checklist.json` | `python -m app.cli.implementation_acceptance_checklist` | Machine-readable acceptance gates, evidence status, gate summary, and blocker metadata. |
| `implementation-acceptance-handoff.md` | `python -m app.cli.implementation_acceptance_handoff` | Reviewer-facing handoff summary for completed or missing implementation evidence. |
| `implementation-acceptance-handoff.json` | `python -m app.cli.implementation_acceptance_handoff` | Machine-readable handoff status, evidence counts, warnings, and merge blockers. |
| `release-bundle-index.html` | `python -m app.cli.release_bundle_index` | Static landing page that should link all generated bundle artifacts for non-technical review. |
| `artifact-manifest.json` | `python -m app.cli.artifact_manifest` | Size and SHA-256 evidence proving which bundle files were generated. |
| `artifact-provenance-ledger.json` | `python -m app.cli.artifact_provenance_ledger` | Provenance labels that distinguish generated review evidence from synthetic fixtures and previews. |

## Review order

1. Open `release-bundle-index.html` first and confirm the decision-record family is discoverable from the bundle.
2. Open `run-decision-record.json` and inspect `status`, `selected_candidate`, `documentation_index`, `required_evidence_before_merge`, `validation_plan`, `merge_blockers`, `compatibility_notes`, `rollback_notes`, and `next_follow_up_candidate`.
3. Confirm `artifact-manifest.json` lists `run-decision-record.json` and the acceptance checklist/handoff artifacts with non-zero sizes and SHA-256 hashes.
4. Confirm `artifact-provenance-ledger.json` labels decision-record, candidate, acceptance checklist, and acceptance handoff artifacts as generated review evidence, not live intelligence or operational truth.
5. Inspect `implementation-acceptance-checklist.json` for blocking gates and missing evidence before treating the selected candidate as implementation-ready.
6. Inspect `implementation-acceptance-handoff.json` for unknown statuses, incomplete evidence rows, and explicit merge blockers.
7. Capture final PR evidence separately: final head SHA, hosted required-check conclusions, unresolved review-thread status, branch-stack/base correctness, final diff safety review, compatibility notes, rollback path, and follow-up work.

## Local reproduction

```bash
python -m app.cli.next_increment_candidates \
  --markdown-path /tmp/next-increment-candidates.md \
  --json-path /tmp/next-increment-candidates.json \
  --decision-record-path /tmp/run-decision-record.json
python -m app.cli.implementation_acceptance_checklist \
  --decision-record-path /tmp/run-decision-record.json \
  --markdown-path /tmp/implementation-acceptance-checklist.md \
  --json-path /tmp/implementation-acceptance-checklist.json
python -m app.cli.implementation_acceptance_handoff \
  --checklist-json /tmp/implementation-acceptance-checklist.json \
  --markdown-path /tmp/implementation-acceptance-handoff.md \
  --json-path /tmp/implementation-acceptance-handoff.json
```

For the complete diagnostics package, run:

```bash
bash scripts/ci_report.sh
```

## Merge blockers

Do not merge a PR solely because these artifacts exist. The decision-record bundle targets are planning and handoff evidence only. Merge remains blocked when any required hosted check is unavailable or failing, the final head SHA is not captured, review threads are unresolved, the final diff contains accidental deletions or unsupported claims, stacked dependencies are out of order, or branch protection/repository policy does not permit the merge.

## Compatibility and rollback

This guide is additive documentation for existing generated artifacts and does not change prediction logic, model training, live ingestion, API routes, database schemas, CLI exit behavior, or release-bundle generation. Roll back by reverting the documentation/test PR. Existing candidate, decision-record, acceptance checklist, acceptance handoff, manifest, provenance, and release-bundle artifacts remain valid.
