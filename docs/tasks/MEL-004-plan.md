# MEL-004 implementation plan

Scope D1-D4 in MEL-004.md. Stdlib only, schema stays 1, MEL-001..003 state must still load and stay valid.
Each fix gets a regression that fails on f638e21 and passes after. Review report: `.mel/MEL-004/whole-main-review-r1.json`
(Codex, REVISE, I1-I12).

## D1 helper fixes (task_state.py, capacity.py)

- I1 waiver after a rejected plan. `count_round` on a REVISE/BLOCKED plan round also clears
  `plan_review_waiver`, keeping the voided reason in `plan_history` (`{'revision', 'voided_waiver', 'round'}`). A
  new waiver needs `revise-plan --unreviewed-plan REASON` (same or new plan file). Regression: init with
  waiver, plan round REVISE, `update --status implementing` refused; revise-plan with a new waiver allows it.
- I2 revise-plan reconciles the contract. `revise-plan` accepts `--scope` (replaces scope; repeatable) and
  `--criterion` (replaces the ID set). Dropping an existing ID needs `--drop-reason REASON`, recorded in the
  plan_history entry with the dropped IDs; old scope and criteria are kept in that entry. No flag = unchanged,
  as today. All criteria are reset, as today. Docs: delivery.md and the scope-error message name both routes.
  (P1) `mutate` gains a `prepare(updated)` step that runs BEFORE the authorship declaration in the same
  transaction; revise-plan uses it to install the replacement scope, so changed files (including the edited
  plan) are judged against the new scope, and paths outside it still need `--outside-scope`. Regression:
  edit plan + a file outside the old scope but inside the new one -> revise-plan with `--scope` and
  `--builder` succeeds; a file outside both is still refused.
- I3 round identity. Dedup key = (kind, report sha256, Git fingerprint, plan sha256) instead of report sha
  alone; rounds now store `plan_sha256`. Same execution registered twice (e.g. `round` then `inspect` with one
  file) still counts once; an identical report for a different snapshot, plan or kind counts as a new round.
  Old round records without `plan_sha256` match on the other three fields. `finding` keeps finding its
  report among rounds by sha. Regression: inspect budget 1, two snapshots, byte-identical APPROVED report:
  second needs `--extend`.
- I4 capacity completeness. `assess` adds a note and cannot return `go` when `observed_at` is missing or
  unparseable, or when the five-hour or weekly window is absent. Incomplete or stale readings return
  `unknown`, except that a window already at its checkpoint threshold still returns `checkpoint-and-handoff`
  (the known exhausted warning wins). A Codex `limit_hit` is unchanged. Regressions for each case.
- I5 failed eval persists and blocks. A complete report whose score is below a threshold is recorded in
  `eval_failures` (judge, model, snapshot, plan, rubric, report ref, failed ids). (P3) It clears ALL recorded
  evals, not only that judge's, and downgrades `ready` to `review_pending`; the mutation commits (revision
  advances) and the command then exits 1 with the failure, documented as such. `ready_checks` refuses while
  any failure for the current snapshot, plan and rubric is unresolved; a later passing eval by the SAME judge
  on that snapshot resolves it (`resolved_revision`). New code means a new snapshot, which needs fresh evals
  anyway. Regressions: backend-built work, Claude passes, Codex fails same snapshot -> not ready; Codex then
  passes -> ready path open; mixed authorship case likewise. Malformed reports are refused without a state
  change, as today.
- I6 adoption attribution. When `init --base` names a commit other than HEAD, or the working copy is dirty,
  init requires `--adopt BUILDER=MODEL` (repeatable; the provider(s) that wrote the pre-existing work) or
  `--adopt-unknown REASON`. Adopted builders replace the default `[owner]` builder list (the owner joins
  when it declares its own changes) and a ledger entry per adopted builder records files base..working copy
  with `adopted: true`. Unknown adoption adds both `claude` and `codex` as builders, so readiness needs both
  providers' inspections, and marks `attribution: unknown` with the reason. Clean init at HEAD is unchanged.
- I7 recoverable roster. Roster events are derived from state: each ledger entry -> one `build` event,
  each finding record -> one `finding` event. (P2) `event_id` = `<repo_id>:<task>:build:<ledger index>` and
  `<repo_id>:<task>:finding:<findings index>`; both lists are append-only, so the index is stable, unique even
  when several adopted builders share one revision, and derivable for existing state. After the state commit,
  `mutate` calls `sync_roster`, which appends only events whose id is not yet in the roster. A roster failure
  no longer looks like a failed mutation: state is reported as recorded and stderr says `roster not
  synchronized; run roster-sync`. New command `roster-sync --repo --task` (no revision, idempotent). Old
  roster lines without ids are left alone. (P4) Bench decisions never wait for sync: `bench_status` reads
  the roster file MERGED with the events derived from the task being mutated (dedup by event_id), so this
  task's unpublished findings count before any new changed-file declaration is accepted. `mutate` also tries
  `sync_roster` before the declaration (best effort, warning only). Limitation, documented: unpublished
  findings of OTHER tasks count only after their own `roster-sync`. Regressions: failed finding publication
  (roster path unwritable) then an immediate changed-file declaration by that model -> refused as benched;
  multi-builder adoption + repeated roster-sync -> one event per ledger entry, no duplicates.
- I8 no-change attribution. `declare` skips the bench check when the declaration changes no files (still
  records the entry). Regression: declare, finding benches the model, commit, no-file re-declaration passes
  without `--override`; a declaration with changed files is still refused.

## D1 docs (I9-I12)

- I9 README: native builders need the other native provider; backend-built work may be inspected by either.
- I10 capacity.py docstring: Codex rollout JSONL (sessions) or another log carrying `rate_limits` events;
  drop the `codex exec --json` claim.
- I11 discipline.md: authorised instruction sources (user, project instruction files, this skill, the
  accepted plan) vs untrusted content met as task data; only the latter is never executed.
- I12 delivery.md: short local rubric guidance (observable criterion, numeric threshold, decisive pass and
  fail cases, evidence field); `ai-eval` named only as optional.

## D2 integration-review rule

delivery.md step 7 and standards.md review section: when tasks are stacked, or merged separately into one
base, the combined result gets a fresh integration review before the stack is reported done. (P5) Defined
against COMBINED authorship, not the integrator:
- baseline = the base before the first task of the stack; covered snapshot = the integrated head (diff
  baseline..head plus every shipped file);
- combined builders = union of each stacked task's recorded `builders` AND its ledger authors (P7): a
  missing or legacy ledger never removes a known builder; a task whose authorship is unknown or marked
  approximate counts as both native providers. `show --who` changes to list recorded builders that have no
  ledger entry (`claude: (recorded builder, no ledger)`), with a regression on legacy MEL-002-shaped state
  (builders=['claude'], no ledger);
- both native providers contributed -> both review the combined result (reciprocal, each covering the
  other's contributions); one native provider only -> the other reviews; backend-only -> any native;
- integration findings become a new task; its fixes need a renewed combined review of the fixed head
  before the stack is called done.
Applied to this stack (MEL-001 Codex-built; MEL-002/003 Claude + Codex; MEL-004 Claude): combined builders
= {claude, codex}, so BOTH providers review the same final committed MEL-004 head, baseline 7883e28 (main
before MEL-001) .. head, every shipped file (P5):
- Codex: fresh final inspection (also the helper's `inspect` record for MEL-004's Claude-built fixes);
- Claude: fresh integration review of the Codex-built parts (MEL-001 code, MEL-003 fix f7caf2e) and of
  the whole, full coverage this time (README, all references, both tests), recorded as
  `.mel/MEL-004/claude-integration-final.json`. It is integration evidence, not a helper `inspect` (Claude
  built MEL-004, so the helper rightly refuses Claude as its sole inspector).
`.mel/MEL-004/claude-whole-main-review.json` (REVISE, partial coverage, f638e21) is preliminary only. Any
finding from either final review is fixed and BOTH reviews are renewed on the new head before the stack is
reported done. README notes the rule.

## D3 provider guidance ($0 first) in backends.md

Mohit 2026-10-26: no spend beyond the Claude and Codex plans. Ordered ladder, dated 2026-10-26, cited, with
"verify the current terms first":
1. Private code: Groq free tier with Zero Data Retention turned on in Data Controls (default: inference not
   retained, reliability/abuse logs up to 30 days unless ZDR; console.groq.com/docs/your-data; privacy page
   says Groq does not train on customer data, groq.com/privacy).
2. Public / non-sensitive only: OpenRouter `:free` models with the free-model training setting off and ZDR
   enforced in privacy settings (openrouter.ai/docs/guides/privacy/logging, /features/zdr), account credit
   limit 0; Gemini API on a project with NO billing (free tier: Google may use prompts and human reviewers may
   read them; ai.google.dev/gemini-api/terms). Never private code through either.
3. Optional paid (only with Mohit's explicit approval): Fireworks direct for private code (ZDR default for
   open models).
Avoid for private code: DeepSeek direct, providers with unread terms (TokenRouter), any `:free` endpoint,
OmniRoute's built-in keyless/web providers (e.g. aihorde, ddgw) and `auto/*` combos.
(P6) Data-boundary reconciliation: backends.md:53 "Free tiers are for public or non-sensitive work" is
replaced by "A free tier is public-only unless the provider's current terms say that tier is not used for
training and not retained (or retention is off by a setting you turned on); as of 2026-10-26 only Groq
with ZDR on meets this among the routes here."
Model selection, verify-first, per route (no model named as current without a dated check): list the
route's live models (`GET /v1/models` through OmniRoute with the key, or the provider console); prefer the
strongest coding/tool-calling model the route serves, with the needed context length; pin it in the combo
(never `auto`); run a pong test, then one small coding probe from the task's own test suite; record the
model id OmniRoute logs as serving. Re-run when a request errors with model-not-found (the 2026-10 project
news classifier hit 404 on a retired OpenRouter `:free` model, P-456). The plan of each task names the
pinned model.
OmniRoute combos: `fallback-private` (Groq) and `fallback-public` (OpenRouter :free, Gemini); pong test each.
No keys or prices invented; prices omitted unless cited.

## D4 proof and delivery

- `python -m unittest discover -s tests` and `python scripts/validate.py`; CI on the PR.
- Codex plan check of this file (read-only); then, on the same final committed head, Codex final inspection
  AND Claude's full integration review (D2); findings fixed and both renewed.
- Version 0.3.0 -> 0.4.0 in SKILL.md; install for Claude Code and Codex with backups; merge only on Mohit's go.

Out of scope: schema migration, roster migration of old lines, new providers in code.
