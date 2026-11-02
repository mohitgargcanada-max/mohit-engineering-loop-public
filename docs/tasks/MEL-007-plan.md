# MEL-007 implementation plan

Scope H1-H9 in MEL-007.md. Baseline: main 2a3ea7f; branch claude/mel-007-plan-author. Claude (claude-sonnet-5-5) builds;
Codex reviews this plan and inspects. Stdlib unittest only. Budgets: plan 2 / inspect 2.
`H` = `skills/mohit-engineering-loop/scripts/task_state.py`.

## Baseline verification

Checked against bodies, not docstrings. `init` (H:261-326) writes `coordinator: provider(owner)` and no plan author; adopted
ledger entries carry the full changed-file list for every adopted builder (H:292-297). `approve_plan` (H:527) refuses
`reviewer == state['coordinator']`. `revise_plan` (H:566) sets `coordinator = provider(actor)`. `acknowledge` (H:455-456) and
`takeover` (H:472-483) set only `owner`. So after adopt-plus-handoff the coordinator is whoever last revised or initiated,
unrelated to who wrote the plan: the confirmed bug.

## Change

- H: add `plan_author` param to `init` and `revise_plan` (validated by `provider()` and `native()`), written to state next to
  `coordinator`; default as in H1. Wire `--plan-author` in the argparse block for both commands. `coordinator` stays untouched
  (other code may read it).
- `init`: when `adopting` with `authors`, compute the plan path relative to the repo; if it is in the adopted `files` and no
  adopted builder equals `plan_author`, raise StateError. Unknown adoption (`--adopt-unknown`) and plans outside the adopted
  files skip the check (documented, no guess).
- `approve_plan`: `author = state.get('plan_author') or state['coordinator']`; refuse if reviewer not native, equals author, or
  report mismatch (message unchanged otherwise).
- No change to `acknowledge`, `takeover`, `inspect`, schema_version or old state files.

## Tests (tests/test_task_state.py, stdlib unittest, existing fixtures)

1. Adopted codex plan, claude owner: claude approval accepted, codex refused (at 2a3ea7f claude is refused as coordinator).
2. Same state after a handoff plus acknowledge, and after takeover: outcome identical.
3. State without `plan_author`: coordinator rule unchanged (both outcomes).
4. `revise-plan --plan-author` replaces the author; default is the actor; non-native value rejected.
5. init rejects adopt where the adopted file list contains the plan and the builders exclude `plan_author`; accepts when it matches.

## Docs

One line in `references/delivery.md` plan review and `references/handoffs.md` (plan author fixed across handoffs, set with
`--plan-author`); README task index and status line; this plan and MEL-007.md.

## Proof and risks

Run new tests first against the unmodified helper to confirm they fail, then the full suite and `scripts/validate.py`.
Risks: relative-path matching of the plan inside adopted files may miss symlinked or renamed paths (check skipped, not
guessed); old states keep the coordinator rule until the next revise-plan; Windows autocrlf can change plan hashes, keep LF.
