# MEL-009 implementation plan

Scope K1-K7 in MEL-009.md. Baseline: main eb45602; branch claude/mel-009-single-provider. Claude (claude-sonnet-5-5) builds;
plan review and inspection by Codex, or by the single-provider rule once built. Stdlib unittest only. Budgets: plan 2 / inspect 2.
`H` = `skills/mohit-engineering-loop/scripts/task_state.py`; `R` = `skills/mohit-engineering-loop/references/`.

## Baseline verification (bodies, not docstrings)

- `independent()` (H:626-628): native builder b maps to only the other native provider; backend builder maps to `['claude','codex']`.
  `ready_checks` (H:612-614) needs a fresh `reviews[x]` for one of those: a claude-only task can never be ready.
- `inspect` (H:525): `any(builder != reviewer ...)` refuses claude reviewing a claude-only build. `reviews` is keyed by reviewer
  provider only; `model` is stored but never compared (H:528).
- `approve_plan` (H:548): refuses `reviewer == plan_author`; `--model` optional. No plan-author model is stored.
- `evaluate` (H:700): judge must not be the only builder, so high-risk tasks hard-stall too; `ready_checks` (H:619-624) uses `independent()`.
- Relabel hole: `declare` stores `provider(label)`; `claude@x` is non-native, so `independent()` lets either native provider
  review it. Today nothing checks the label is true. In the new mode the model rule is applied to ledger models regardless of label.
- `snapshot` (H:39, 51): untracked non-ignored files make `dirty` true; `ready_checks` (H:605) then refuses.
- No plan template exists in `R/delivery.md`; K4(c) adds it. README lists MEL-007 only, not MEL-008 (K7 adds both lines).

## Change

K1, in H (revised after plan review R1-R3):
- Enter/leave are their own gated operation (new commands `single-provider enter|leave`, owner_only, not `update`):
  `enter` needs `--single-provider claude|codex --reason --approved-by` and, because the plan reviewer is compared to the plan
  model, `--plan-model` (mandatory) unless `plan_review` already exists. Entering does NOT call `invalidate` (a prior
  other-provider inspection stays valid). `leave` calls `invalidate` and moves the field to `single_provider_history` with the exit
  revision. `init` also accepts the flags (same rules). The label survives in `rounds[]`, history and `state['review_label']`.
- `norm(model)`: lowercase, '.' -> '-', stripped; used for every model comparison. standards.md names canonical ids.
- `review_rule(state, command, reviewer, data, model, same_model)`, per command. Outside the mode: old checks, unchanged.
  Inside, common: reviewer native and equal to `available`; `fresh_session` and `built_nothing` true; non-empty `adversarial`;
  `same_model` needs `--same-model REASON` plus `--user-approval TEXT`, both recorded.
  - approve-plan: model required; compared to `plan_model` and ledger models; `plan_model` missing -> refuse (cannot happen
    after a correct `enter`, which demands it). Fresh task has an empty ledger, so plan_model is the real comparator here.
  - inspect / eval: model compared to ledger models; fail closed only for genuinely unknown authorship (a builder with no ledger
    entry and no adoption record).
  Stores `{'single_provider': reason, 'since': date, 'same_model': ...}` in the stored review.
- Unavailable provider (R3): while the mode is on, `transfer` (recipient), `acknowledge`, `approve_plan`, `inspect`, `evaluate`,
  `review_round` and `declare` refuse the unavailable provider with "the other provider acted; leave the mode first".
- `independent(state)`: in the mode returns `{b: [available]}` for every builder, native or backend.
- Plan model: `--plan-model` (init, revise-plan, enter); stored as `plan_model`.
- `inspect`/`approve_plan`/`evaluate`: replace the old same-provider lines by the rule's outcome; judge key and `evals` shape unchanged.
- `brief`: first line `SINGLE-PROVIDER REVIEW (<reason>, since <date>)` when on or when any stored review carries it.
  `ready`/`merged`: same line to stderr and `state['review_label']`; stdout JSON unchanged.
- `capacity.md`: `unknown`/`exhausted` leads to entering; a fresh `ok` reading for the absent provider means leave the mode.
- `acknowledge`/`takeover`/`handoff` otherwise untouched.

K4, in H `approve_plan` only: read the plan text; refuse on any `[NEEDS CLARIFICATION`; compute criterion ids with no line containing
both the id and `proof` (case-insensitive); store them only in `plan_review['unproved_criteria']` and print the warning to stderr (stdout carries parsed JSON).

K2/K5/K6: docs only, described in MEL-009.md. K7: SKILL.md version, README, VALIDATION.md.

## Tests (tests/test_task_state.py; new tests first, run against the unmodified helper to confirm each fails, except controls)

1. Walkthrough on a FRESH task: init -> enter (with --plan-model) -> approve-plan by a different-model fresh reviewer -> build/declare
   -> inspect -> ready -> merged all succeed; label present at each of ready/merged/brief.
2. CONTROL (passes today): same flow without the mode is refused at approve-plan and at inspect.
3. Reviewer model equals plan or builder model: refused; with `--same-model` + `--user-approval`: accepted and recorded; without the
   approval text: refused. Model strings normalised ('Claude-Opus-5.5' equals 'claude-opus-5-5').
4. Backend reviewer refused; backend-labelled builder with matching model refused (relabel control, must be able to fail).
5. Entering keeps an earlier other-provider inspection valid; leaving voids reviews and `independent()` demands the other provider
   again; label remains in `rounds[]`, `single_provider_history` and `review_label` of a merged task.
6. Codex-only symmetry. Codex review, handoff to codex, ack by codex and a codex declare are each refused in claude-only mode.
7. CONTROL (passes today): legacy state without the field keeps every old rule.
8. `[NEEDS CLARIFICATION` refuses approve-plan; clean plan passes.
9. Orphan criterion recorded in `plan_review['unproved_criteria']`; warning on stderr; stdout still parses as JSON (assertion).

## Risks and scope notes (please judge)

- K1 is large. Fresh-session and built-nothing are attestations the helper cannot verify; documented as such, not hidden.
- K4(b) as refuse would break every existing plan fixture and plan written before 0.5.0; chosen: warn and record, refuse only (a).
- Judge rule (`evaluate`) is not in the owner's K1 text but high-risk tasks stall without it; included, easy to drop.
- `--plan-model` is mandatory when entering the mode before plan approval; `--same-model` also needs the user's approval text (it disables the only enforced check).
- Models are free text; normalised and canonical ids named in standards.md. `approved_by` is a free-text claim, as strong as `--unreviewed-plan`.
- stderr label for ready/merged because stdout is parsed JSON.
- OmniRoute mentions in dated history (VALIDATION.md, old task plans) are left as history; only live guidance changes.
- Windows autocrlf can change plan hashes; keep LF.
