# Changelog note: run decision record export

## Unreleased

- Added machine-readable run decision record export to `next_increment_candidates`, with documentation, README navigation, and deterministic tests so recurring maintenance runs can capture the selected candidate, alternatives, merge evidence, validation plan, blockers, rollback, safe analytical framing, and next follow-up without changing analytical or model behavior.

## Compatibility

This is additive. Existing candidate Markdown and JSON outputs are unchanged unless a maintainer explicitly passes `--decision-record-path`.

## Rollback

Revert the related PR and remove any locally generated `run-decision-record.json` files.
