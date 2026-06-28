# Workflow Gate Summary JSON Contract

`python -m app.cli.workflow_gate_summary --json-path <path>` writes an offline JSON document for reviewer handoff tooling. This page documents the stable, additive contract for consumers that want to validate hosted workflow evidence without guessing field meaning.

The contract is intentionally static. The exporter inspects the local checkout for expected workflow files and renders reviewer guidance. It does not call GitHub, launch model inference, collect external intelligence, connect to MongoDB, or treat analytical estimates as certainty. It is not a predictive model quality assessment.

## Compatibility rules

- Existing fields are kept stable wherever practical.
- New fields should be treated as additive and optional by downstream consumers until they are documented here.
- Consumers should ignore unknown fields rather than failing closed on additive metadata.
- String values are human-readable review guidance, not machine proof of model quality or live data validity.
- Hosted check status must still be verified against the final PR head SHA in GitHub before merge.

## Top-level object

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `schema_version` | string | Yes | Contract version for the exported summary. Consumers should log it with artifacts. |
| `generated_at` | string | Yes | UTC timestamp for when the summary was rendered. |
| `status` | string | Yes | `ready_for_review` when required workflow files are present; `blocked` when one or more required workflow files are missing. |
| `safe_scope` | string | Yes | Analytical safety framing to preserve in reviewer handoffs. |
| `artifact_dir` | string | Yes | Artifact directory used by the exporter for Markdown/JSON output planning. |
| `next_action` | string | Yes | Human-readable next reviewer action. |
| `required_gate_count` | integer | Yes | Count of gates marked required before merge. |
| `missing_required_workflows` | array of strings | Yes | Required workflow file paths missing from the local checkout. Empty means file-presence review is ready. |
| `gates` | array of gate objects | Yes | Per-workflow gate metadata documented below. |
| `narrow_rerun_plan` | array of rerun objects | Yes | Flattened focused rerun sequence derived from all gate-level `narrow_rerun_targets`. |
| `review_order` | array of strings | Yes | Ordered merge-review checklist for final-head-SHA validation. |
| `merge_blockers` | array of strings | Yes | Human-readable blocking conditions detected by the offline checkout inspection. Empty means no offline file-presence blockers were detected. |

## Gate object

Each item in `gates` describes one hosted workflow gate and its local review metadata.

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `name` | string | Yes | Hosted workflow display name reviewers should look for. |
| `workflow_path` | string | Yes | Expected workflow file path in the repository. |
| `required_before_merge` | boolean | Yes | Whether this gate must be green and current before merge. |
| `local_reproduction` | string | Yes | Broad local command that best reproduces the hosted gate. |
| `green_means` | string | Yes | What a successful gate reasonably validates. |
| `green_does_not_mean` | string | Yes | Explicit limit on what the gate does not prove. |
| `blocker_when` | string | Yes | Failure, staleness, or unavailability condition that should block merge. |
| `evidence_to_collect` | string | Yes | Run URL, job conclusion, artifact, and final-head-SHA evidence reviewers should capture. |
| `narrow_rerun_targets` | array of strings | Yes | Focused commands to run before rerunning the broader hosted/local gate. |
| `workflow_file_status` | string | Yes | `present` or `missing` based on local file presence. |
| `merge_blocker` | boolean | Yes | True when a required workflow file is missing from the local checkout. |

## Narrow rerun object

Each item in `narrow_rerun_plan` is generated from one gate command so automation can render a single ordered troubleshooting list.

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `gate` | string | Yes | Gate name associated with the focused command. |
| `command` | string | Yes | Narrow local command to run first when a matching hosted job fails or is unavailable. |
| `purpose` | string | Yes | Reviewer explanation for why this command appears in the plan. |

## Consumer guidance

1. Parse the JSON and record `schema_version`, `generated_at`, and the final PR head SHA under review.
2. Confirm `status` is not `blocked` and `missing_required_workflows` is empty.
3. For every gate where `required_before_merge` is true, verify the hosted workflow conclusion on the final head SHA.
4. Capture the evidence described by `evidence_to_collect` before merge.
5. If a gate fails or is unavailable, start with the matching `narrow_rerun_targets` before rerunning the broader `local_reproduction` command.
6. Keep `green_does_not_mean` in handoff notes so successful checks are not represented as predictive truth, operational certainty, or live data validity.

## Example shape

```json
{
  "schema_version": "workflow-gate-summary/v1",
  "status": "ready_for_review",
  "missing_required_workflows": [],
  "merge_blockers": [],
  "gates": [
    {
      "name": "CI",
      "required_before_merge": true,
      "workflow_file_status": "present",
      "merge_blocker": false,
      "narrow_rerun_targets": ["python -m compileall app tests"]
    }
  ],
  "narrow_rerun_plan": [
    {
      "gate": "CI",
      "command": "python -m compileall app tests",
      "purpose": "Reproduce a focused slice before rerunning the broader hosted or local gate."
    }
  ]
}
```

## Rollback

Revert this document and its static documentation test coverage. No data migration, branch rewrite, workflow change, generated artifact cleanup, or CLI behavior rollback is required.
