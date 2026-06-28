# CI triage summary JSON contract

`app.cli.triage_summary` exports a deterministic JSON and Markdown summary from local diagnostic artifacts. The JSON is intended for reviewers, automation, and handoff tools that need to decide which narrow validation target to rerun before broad CI is repeated.

## Generate the artifact

```bash
python -m app.cli.triage_summary \
  --artifact-dir ci_artifacts \
  --health-json ci_artifacts/release-health.json \
  --manifest-json ci_artifacts/artifact-manifest.json \
  --markdown-path ci_artifacts/triage-summary.md \
  --json-path ci_artifacts/triage-summary.json
# or
make triage-summary ARTIFACT_DIR=ci_artifacts
```

The command reads only local generated diagnostics. It does not call external services, collect OSINT, run model inference, deploy anything, or make operational claims.

## Top-level fields

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | string | Stable contract identifier. Current value: `triage-summary/v1`. |
| `generated_at` | string | UTC ISO-8601 timestamp for the local export. |
| `status` | string | One of `blocked`, `incomplete`, `review`, or `ready`. |
| `status_explanation` | string | Human-readable explanation for the chosen status. |
| `health_summary` | object | Counts of normalized `ok`, `warn`, and `fail` release-health checks. |
| `failing_checks` | array | Original failing release-health check records. |
| `warning_checks` | array | Original warning release-health check records. |
| `missing_artifacts` | array | Expected artifact paths reported missing by the manifest. |
| `merge_blockers` | array | Machine-readable blocker strings derived from failing checks and missing expected artifacts. |
| `recommended_actions` | array | Ordered narrow rerun targets with reason, target, detail, and remediation. |
| `next_step` | string | First recommended action or reviewer handoff instruction. |
| `artifact_count` | integer | File count reported by the artifact manifest. |
| `source_artifacts` | object | Paths and counts for the artifact directory, health JSON, manifest JSON, health checks, and missing artifacts. |
| `review_order` | array | Deterministic reviewer workflow for safe local reproduction and handoff. |
| `safe_scope` | string | Reminder that the artifact is limited to local setup, deterministic tests, synthetic examples, API contracts, generated artifacts, and documentation. |

## Status semantics

| Status | Meaning | Merge guidance |
| --- | --- | --- |
| `blocked` | At least one release-health check failed. | Do not merge; reproduce the first `recommended_actions[].target` and fix the root cause. |
| `incomplete` | No failing health checks, but expected artifacts are missing. | Do not merge until the mapped artifact target is regenerated and the manifest is refreshed. |
| `review` | No hard blockers, but warnings exist. | Review and acknowledge warnings; rerun `make verify` after fixes if any behavior changes. |
| `ready` | No failing health checks or missing expected artifacts were reported by the local inputs. | Continue with hosted final-head-SHA checks, final diff review, and repository policy. |

## Compatibility expectations

Downstream consumers should key on `schema_version` before relying on field names. Additive fields may appear in future `triage-summary/v1` outputs, but existing fields should remain stable unless the schema version changes. Consumers should treat unknown fields as informational.

## Safe analytical framing

The triage summary is a review and reproducibility artifact. It must not be presented as proof that predictive estimates are correct, certain, operationally actionable, or derived from live intelligence. It only explains local diagnostic state and safe rerun targets.

## Rollback

If a downstream parser cannot consume a new artifact, rerun the CLI with the previous release branch or inspect `triage-summary.md` manually. Keep `release-health.json` and `artifact-manifest.json` attached so the triage state remains recoverable.
