# Reviewer handoff JSON contract

`reviewer-handoff.json` is the machine-readable companion to `reviewer-handoff.md`. Use it when automation, dashboards, release scripts, or review bots need to inspect a diagnostics bundle without parsing Markdown.

The authoritative schema lives at:

```text
docs/reviewer_handoff_schema.json
```

## Status routing

Consumers should route work from `review_status` first:

| `review_status` | Meaning | Recommended consumer behavior |
| --- | --- | --- |
| `ready` | Required reviewer artifacts are present and release health is passing. | Continue with normal review or publish the bundle. |
| `review_warnings` | Required reviewer artifacts are present, but release health reports warnings/degraded state. | Review warnings before publishing. |
| `needs_attention` | Expected outputs or key reviewer artifacts are missing. | Run `recommended_rerun`, then regenerate the handoff. |
| `needs_review` | The bundle does not match a known pass/warn state, but no key artifacts are missing. | Ask a maintainer to inspect release health and triage notes. |

`release_status` is intentionally kept as the raw status reported by release health when available. Treat it as supporting detail; do not use it instead of `review_status` for routing.

## Required top-level fields

| Field | Type | Purpose |
| --- | --- | --- |
| `generated_at` | string | UTC ISO-8601 timestamp for the generated handoff. |
| `artifact_dir` | string | Directory inspected by the handoff generator. |
| `release_status` | string | Raw release-health status, or `unknown` when release health is missing. |
| `review_status` | string | Stable reviewer-facing status: `ready`, `review_warnings`, `needs_attention`, or `needs_review`. |
| `recommended_rerun` | string | Narrow local command to run when the bundle is incomplete. |
| `copyable_summary` | string | One-paragraph handoff for PRs, issues, or chat review. |
| `missing_expected` | array of strings | Expected outputs missing according to `artifact-manifest.json`. |
| `missing_key_artifacts` | array of strings | Reviewer-critical artifacts missing from the bundle. |
| `key_artifacts` | array of objects | Presence, purpose, size, and hash data for important artifacts. |
| `review_order` | array of objects | Ordered checklist matching the release bundle index review flow. |

Optional preview fields may be `null` when their source artifact is unavailable:

- `release_health_preview`
- `triage_preview`

## `key_artifacts[]` contract

Each key artifact object includes:

| Field | Type | Notes |
| --- | --- | --- |
| `path` | string | Artifact path relative to `artifact_dir`. |
| `purpose` | string | Human-readable reason the artifact matters. |
| `present` | boolean | Whether the artifact was found in the manifest or on disk. |
| `size_bytes` | integer or null | File size from the manifest when available. |
| `sha256` | 64-character hex string or null | SHA-256 from the manifest when available. |

## `review_order[]` contract

Each checklist object includes:

| Field | Type | Notes |
| --- | --- | --- |
| `step` | integer | 1-based review step. |
| `action` | string | Short reviewer action. |
| `artifact` | string | Artifact to open or inspect. |
| `detail` | string | Why this step matters. |
| `present` | boolean | Whether the artifact was found in the manifest. |
| `status` | string | `present` or `missing`. |

Consumers should preserve ordering by sorting on `step` rather than relying only on array order.

## Minimal consumer algorithm

```python
import json
from pathlib import Path

handoff = json.loads(Path("ci_artifacts/reviewer-handoff.json").read_text(encoding="utf-8"))

if handoff["review_status"] == "ready":
    print("Bundle is ready for review.")
elif handoff["review_status"] == "review_warnings":
    print("Review warnings before publishing.")
else:
    print(f"Run: {handoff['recommended_rerun']}")
    print("Missing:", handoff["missing_expected"], handoff["missing_key_artifacts"])
```

## Compatibility rules

- Treat unknown extra fields as forward-compatible metadata.
- Treat missing required fields as an invalid handoff.
- Use `review_status` for automation routing.
- Use `recommended_rerun` before inventing a broader command.
- Regenerate the handoff after changing artifacts or rerunning diagnostics.
- Keep usage limited to defensive validation, documentation, onboarding, and analytical software review.
