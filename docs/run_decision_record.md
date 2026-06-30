# Run decision record

`python -m app.cli.next_increment_candidates --decision-record-path ...` can now emit a machine-readable JSON decision record for a maintenance run. The record turns the offline candidate matrix into a concrete handoff artifact that captures what was selected, why alternatives were not selected, which validation evidence must exist before merge, and which blockers still prevent release.

The command reads only local repository files through the existing candidate generator:

- `CHANGELOG.md` for recent `Unreleased` work.
- `goals.md` for roadmap demand.

It does not fetch live data, call external APIs, run prediction, inspect targets, or claim certainty about real-world activity.

## Usage

Generate the usual candidate JSON plus a decision record:

```bash
python -m app.cli.next_increment_candidates \
  --no-markdown \
  --json-path /tmp/next-increment-candidates.json \
  --decision-record-path /tmp/run-decision-record.json
```

Select an explicit candidate after reviewing the matrix:

```bash
python -m app.cli.next_increment_candidates \
  --json-path /tmp/next-increment-candidates.json \
  --decision-record-path /tmp/run-decision-record.json \
  --selected-candidate-id candidate-05
```

## JSON fields

The decision record includes:

- `schema_version` - decision-record schema version.
- `status` - `ready_for_implementation` when local candidate inputs are readable, or `blocked` when required local planning context is missing.
- `selected_candidate` - the selected candidate recipe from the candidate matrix.
- `selection_reason` - whether the selection came from deterministic scoring or an explicit candidate override.
- `alternatives_considered` - non-selected candidates with reason-not-selected text.
- `required_evidence_before_merge` - machine-readable checklist items such as final head SHA, hosted required checks, local validation, diff review, compatibility, rollback, safe analytical framing, and next follow-up.
- `validation_plan` - narrow commands to run before broader hosted validation.
- `merge_blockers` - inherited local blockers plus the required hosted-check/review evidence reminder.
- `compatibility_notes` and `rollback_notes` - additive-consumer expectations and recovery path.
- `next_follow_up_candidate` - a concrete continuation item for the next run.

## Safe analytical framing

The decision record is repository-maintenance evidence only. It is not operational tasking, live intelligence, targeting guidance, or proof that a prediction is true. Use it to make PR handoff easier, keep validation explicit, and preserve uncertainty/caveat language in future generated artifacts.

## Compatibility and rollback

This feature is additive. The existing candidate Markdown and JSON outputs remain compatible, and the decision record is written only when `--decision-record-path` is provided.

Rollback path:

1. Revert the PR that introduced the decision-record option and tests.
2. Remove any locally generated `run-decision-record.json` files.
3. Continue using `python -m app.cli.next_increment_candidates` without `--decision-record-path`.

## Suggested validation

```bash
python -m compileall app tests
python -m unittest tests.test_next_increment_candidates
python -m unittest discover -s tests -p 'test_*.py'
python -m app.cli.next_increment_candidates --no-markdown --json-path /tmp/next-increment-candidates.json --decision-record-path /tmp/run-decision-record.json
```
