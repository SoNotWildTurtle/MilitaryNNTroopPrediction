# Next Increment Candidates

`python -m app.cli.next_increment_candidates` generates an offline Markdown and JSON candidate matrix for the next cohesive repository increment. It is intended for recurring maintainers who need to avoid duplicating recent work while still choosing a functional, reviewable improvement.

The tool reads only local repository files:

- `CHANGELOG.md` for recent `Unreleased` work.
- `goals.md` for numbered roadmap demand.

It does not fetch live data, call external APIs, run prediction, inspect targets, or claim certainty about real-world activity.

## Usage

```bash
python -m app.cli.next_increment_candidates
```

By default, this writes:

- `next-increment-candidates.md`
- `next-increment-candidates.json`

Custom output paths are supported:

```bash
python -m app.cli.next_increment_candidates \
  --markdown-path /tmp/next-increment-candidates.md \
  --json-path /tmp/next-increment-candidates.json
```

JSON-only validation smoke run:

```bash
python -m app.cli.next_increment_candidates \
  --no-markdown \
  --json-path /tmp/next-increment-candidates.json
```

## Candidate fields

Each candidate recipe includes:

- `candidate_id` - stable display ID for review notes.
- `title` - suggested PR-sized increment title.
- `focus_area` - deterministic bucket such as setup validation, artifact provenance, uncertainty review, operator handoff, or scenario comparison.
- `status` - `recommended`, `watch`, or `defer` based on roadmap matches and recent overlap.
- `novelty_score` - simple score that rewards roadmap demand and penalizes recent overlap.
- `roadmap_matches` - count of inspected roadmap items matching the candidate keywords.
- `recent_overlap` - count of inspected changelog bullets matching those keywords.
- `suggested_artifact` - the kind of Markdown/JSON evidence artifact that would make the increment easy to review.
- `validation_commands` - narrow local checks to run before broader validation.
- `safety_notes` - reminders to preserve analytical framing and backwards compatibility.

## Status semantics

`recommended` means the inspected roadmap slice shows demand and the recent changelog has limited overlap. This is the best starting point for one additive PR.

`watch` means the roadmap has signal, but recent work overlaps enough that the maintainer should inspect prior PRs before implementing to avoid process-only duplication.

`defer` means the inspected roadmap slice does not strongly support that focus area. Defer it unless issues, failures, or reviewer feedback make it urgent.

## Safe analytical framing

Generated candidate recipes are repository-maintenance evidence only. They are not operational tasking, targeting guidance, live intelligence, or proof that a predictive output is true. PRs selected from this report should continue to frame outputs as analytical estimates with explicit caveats.

## Compatibility and rollback

The CLI is additive. It creates new Markdown/JSON output files only when explicitly run and does not change existing artifacts, schemas, datasets, or model behavior.

Rollback path:

1. Revert the PR that introduced the CLI and tests.
2. Remove generated `next-increment-candidates.md` and `next-increment-candidates.json` files if they were created locally.
3. Continue using `python -m app.cli.run_continuity_brief` and the existing handoff runbooks.

## Suggested validation

```bash
python -m compileall app tests
python -m unittest tests.test_next_increment_candidates
python -m unittest discover -s tests -p 'test_*.py'
python -m app.cli.next_increment_candidates --no-markdown --json-path /tmp/next-increment-candidates.json
```
