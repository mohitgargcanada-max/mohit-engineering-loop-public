# Delivery contract

1. Establish actual scope and authorization. Give the request a stable `MEL-###`
   identifier (higher numbers allowed). Verify existing tracker IDs before taking
   one; do not reuse or renumber. Record scope as acceptance criteria with stable
   IDs. Split unrelated requests; do not fragment one accepted task to hide omissions.
2. Inspect repository instructions and Git status. Use `git worktree list --porcelain`
   as worktree authority and `gh pr list/view` as PR authority. Create an isolated
   `codex/<task>` or `claude/<task>` branch/worktree from the agreed base. Never
   stash, reset, stage or commit another session's work. A branch is a branch, not
   a GitHub fork; choose an owned fork only when upstream is not writable.
3. Open a draft PR early against the agreed repository/base. If an empty diff cannot
   open a PR, first commit the original scoped plan/checkpoint. Record the PR URL
   in canonical task state. Keep private prompts, transcripts and memory out of Git.
   A repository with no GitHub remote uses local delivery instead (`init
   --local-target BASE`): no PR, the same review gates, and a merge confirmed by Git.
4. Record architecture/stack choice, role/provider/model allocation, topology,
   boundaries, scale assumptions, proof, budget and relevant uncertainty. For a
   small task, a short plan suffices; substantial projects need a spec with interfaces,
   data contracts, failure behavior, acceptance and rollout/rollback as applicable.
5. Ask the other provider to review the plan with read-only capabilities verified at
   runtime. Preserve host restrictions and context explicitly. Resolve findings on
   evidence and bind approval to exact plan bytes. Stop on quota/tool failure; only
   a user waiver permits unreviewed implementation, recorded in task state and PR.
6. Implement all scope surgically. Run meaningful regression and failure tests with
   controls that must pass and must fail. Check downstream persisted/user-visible
   output, not just producer fields. Preserve full command exit status and failure
   logs. Long runs checkpoint progress and respect live workload limits.
7. Have a fresh other-provider session inspect all changes and tests against the
   accepted plan, including staged, unstaged and untracked deliverables. Record
   snapshot/plan hashes, actual coverage and limitations. Fix findings, rerun affected
   proof, then obtain another fresh inspection. A new edit invalidates old approval.
   Stacked or separately merged tasks also need an [integration review](#integration-review) of the
   combined result before the stack is reported done.
8. Only after every accepted criterion, proof, inspection and blocker is resolved,
   mark ready. Check actual GitHub CI, required approvals, branch protection and
   mergeability; do not bypass them. Merge only with authorization. Re-read actual
   GitHub `state`/`mergedAt` and record the merge SHA before marking merged. A helper
   flag or agent statement is not evidence of a merge. Remove worktrees only after
   verifying they contain no uncommitted/unpushed work and cleanup is authorized.

## Task state

The helper stores `.mel/<task>/state.json` plus immutable numbered handoffs. Reserve
`.mel/` for workflow metadata, never executable deliverables; Git fingerprints
exclude it so checkpoint writes do not invalidate themselves. A task is bound to
its repository/worktree path, baseline commit and branch for every mutation; `show`
reads it from any worktree. Acceptance checks and
review reports are attestations the coordinator must verify, not proof generated
by the helper. Never pass a criterion merely to get a gate green.

```text
python ABSOLUTE_HELPER init --repo WORKTREE --task MEL-001 --owner codex --plan PLAN --criterion A1 --criterion A2
python ABSOLUTE_HELPER show --repo WORKTREE --task MEL-001
python ABSOLUTE_HELPER approve-plan --repo WORKTREE --task MEL-001 --expected 1 --actor codex --reviewer claude --report PLAN_REVIEW.json
python ABSOLUTE_HELPER update --repo WORKTREE --task MEL-001 --expected 2 --actor codex --status implementing
python ABSOLUTE_HELPER update --repo WORKTREE --task MEL-001 --expected 3 --actor codex --pass A1 --proof LOG
```

Every mutation supplies expected state revision and the active owner. Pass/block
criteria individually. PR pointers are references; GitHub remains authoritative.
Task IDs use project prefixes only if the helper supports them; this edition uses
`MEL-###`. Proof paths must exist and their hashes are stored; changed proof or plan
invalidates readiness. A fresh independent inspection with a real report is required
for readiness. Review identity is declared by the caller, not cryptographically
attested. No cost or autonomous orchestration claim follows from this mechanism.

## Plan and final inspection records

Plans follow a short template. Answer each lean gate yes or no; every "no" needs a one-line reason: smallest change that meets the criteria; reuse before adding; no speculative infrastructure. Give every criterion id a line containing the id and the word `proof`. Mark open questions `[NEEDS CLARIFICATION: ...]`: `approve-plan` refuses while any remain, and it records (stderr warning, `plan_review.unproved_criteria`) any criterion id with no proof line.

The plan's reviewer must be the native provider that did not write it: `init` and `revise-plan` record `plan_author` (`--plan-author claude|codex`, default the owner/actor), and handoffs, acks and takeovers never change it.

Use `approve-plan --expected REV --actor OWNER --reviewer OTHER --report FILE`
with a real JSON report containing `verdict`, `reviewer`, nonempty `coverage`,
empty resolved `findings`, `limitations`, and `plan_sha256`. It must match the exact
plan digest. A user-authorized waiver instead uses `init --unreviewed-plan REASON`;
it is never labeled approved. `update --status implementing` enforces this gate.

A final `inspect` report has the same review fields except plan_sha256; the helper
binds it to the current plan and Git snapshot. See the explicitly marked
[example](review-report.example.json) for the shape, never for real evidence.
`ready` requires clean committed code, all unchanged proof, no blockers and a fresh
other-provider report per builder. A native builder needs the other native provider;
a backend builder (`claude@openrouter`) needs at least one native `claude` or `codex`
report. Backend labels can never approve a plan or record an inspection. `merged`
only records a merge confirmed by `gh pr view` for the exact local head; it never
merges or overrides GitHub checks. In local delivery, `merged` resolves
`refs/heads/BASE` to a commit and requires the task head to be its ancestor; merge
the branch yourself first, with authorization, then record it before committing
the `.mel/` change.

CLI evidence paths are local references. Commit sanitized summaries rather than raw
logs; moving an evidence file requires deliberate reconciliation, not silent rewrite.
This edition does not migrate task records across paths automatically.

Use `revise-plan --plan FILE --expected REV --actor OWNER` to keep the stable
task ID while versioning a revised plan. It preserves old plan/review hashes, clears
acceptance/proof and final-inspection attestations, and requires renewed plan review
or an explicit new user waiver before implementation. Recheck every criterion; do
not silently carry passing evidence across a changed contract. The revision can
also change the contract: `--scope GLOB` (repeatable) replaces the scope and is the
scope that judges the changes declared with it; `--criterion ID` (repeatable)
replaces the criterion set, and dropping an existing ID needs `--drop-reason REASON`.
Old scope, criteria and any dropped IDs stay in `plan_history`. A REVISE or BLOCKED
plan round also voids an earlier `--unreviewed-plan` waiver; record a new one with
`revise-plan --unreviewed-plan REASON` if the user still waives review.

When adopting existing authorized work, `init --base COMMIT` records the original
ancestor baseline instead of pretending tracking began before implementation.
Verify the comparison baseline yourself; the helper checks it is an ancestor.
Whenever work already exists at init (a baseline other than HEAD, or uncommitted
files), name who wrote it with `--adopt BUILDER=MODEL` (repeatable; ledger entries
marked `adopted`), or `--adopt-unknown REASON`, which counts both `claude` and
`codex` as builders so both must inspect. The owner becomes a builder when it
declares its own changes. Commit the plan before `init` to start clean.

## Single-provider mode

When one native provider is unavailable (capacity `unknown` or `exhausted`, see [capacity.md](capacity.md)) and the user approves, the available provider may own the task end to end. Enter with `init --single-provider claude|codex --reason R --approved-by "USER SAID ..." --plan-model M`, or on an existing task with `single-provider-enter` (same flags; `--plan-model` is required unless the plan is already approved). Entering keeps earlier reviews; `single-provider-leave` ends the mode and voids reviews. While it is on:

- The available provider may approve the plan and inspect, only as a fresh session that built nothing, on a model different from every recorded builder model and the plan model (`--model` required; models compare case-insensitively with `.` read as `-`). The report must carry `fresh_session: true`, `built_nothing: true` and a non-empty `adversarial` list (what could be wrong, a control that could fail). The first two are reviewer attestations the helper cannot verify; the model comparison is the enforced check.
- If the builder is already the strongest available model, `--same-model REASON --user-approval TEXT` allows a fresh same-model session; both are recorded and shown.
- High-risk `eval` judges follow the same rule. Backend reviewers are still refused, and a native build declared as `harness@backend` gets no relaxation: the model comparison runs on every ledger model.
- Refused: any action by the unavailable provider (review, plan approval, eval, round, build declaration, handoff to it, acknowledgment, takeover). Leave the mode first.
- Unknown adopted authorship, or legacy state without a recorded working copy, is refused (fail closed); an owner with no ledger entry on a tracked task is accepted.
- `revise-plan` requires `--plan-model`. Every `ready`, `merged` (stderr, plus `review_label` in state) and `show --brief` prints `SINGLE-PROVIDER REVIEW (<reason>, since <date>)`; the label stays on the task after the mode ends. The approval text (`--approved-by`) is a free-text claim, as strong as `--unreviewed-plan`.

Single-provider review shares the author's blind spots; use the real other provider whenever it returns.

## Project conventions

- A project may name its own merge script and proof runner (for example a project's own `integrate_into_master.py` and a serial test runner). Local delivery then uses them; `merged` still only records the Git-confirmed result.
- Map each task to the project's own tracker id, and when the project has a definition of done (journal entry, tracker row, spec update) treat it as a `ready` criterion with its own proof line.
- `init` and `ready` treat every untracked, non-ignored file as uncommitted work. Run each task from a fresh worktree so unrelated untracked files (logs, scratch output) are not in it; the helper has no opt-in ignore, because one would weaken the clean-tree proof.

## Integration review

Separate reviews of stacked tasks miss what only shows in the combined result:
documents that contradict each other, behavior a later task changed, features that
interact badly. Before a stack (tasks built on each other, or merged separately into
one base) is reported done:

- Baseline: the base before the stack's first task. Covered snapshot: the integrated
  head, i.e. the diff baseline..head plus every shipped file.
- Combined builders: each stacked task's recorded `builders` plus its ledger authors
  (`show --who`; a missing or legacy ledger never removes a known builder). A task
  whose authorship is unknown or approximate counts as both native providers.
- Reviewers: both native providers contributed -> both review the combined result,
  each covering the other's contributions; one native provider -> the other reviews;
  backend-only -> any native provider.
- Findings become a new task. Its fixes need a renewed combined review of the fixed
  head, by the same reviewer rule, before the stack is called done. An integration
  review by a provider that built the fixing task is integration evidence, not that
  task's `inspect` record.

## Proof and review hygiene

Lessons from 2026-10-25/26 (a private project):

- **The coordinator runs the proof.** A builder's "tests written, could not run" (Codex's sandbox could not
  start the test runner at all) is not proof. Run it yourself before passing a criterion.
- **Proof queue for large repos:** the changed tests plus the importers of each changed module, one test
  process per file. Narrow away a god-module whose change is local, and compare every failure against a
  clean-base checkout before calling it a regression.
- **Resume vs fresh build:** a builder session cannot resume once the coordinator has committed in between (the
  checkout changed). Run the fix list as a fresh build on the clean committed worktree instead.
- **Briefs are written by a script with raw strings,** never by `sed` path substitution: it mangled Windows
  backslashes twice.
- **Never `--no-verify`,** and keep reviewing: independent review of builder work caught a high false alert
  (whole-process peak memory compared with one step's own peak) and a medium liveness hole (a status banner
  written before the job launched hid failed launches).
- Unattended work while a provider is out (queue runner, cloud sessions): [unattended.md](unattended.md).

## Framework records (attribution, scope, rounds, findings, evals)

```text
python ABSOLUTE_HELPER init ... --scope "src/*" --scope "tests/*" --risk high --rubric RUBRIC.json --budget-plan 3 --budget-inspect 2
python ABSOLUTE_HELPER update ... --builder codex --model gpt-6.1-sol [--outside-scope REASON] [--override REASON]
python ABSOLUTE_HELPER round ... --kind inspect --report REVIEW.json [--extend REASON]
python ABSOLUTE_HELPER finding ... --id F1 --severity high --builder codex --model gpt-6.1-sol --report REVIEW.json
python ABSOLUTE_HELPER eval ... --judge claude --model claude-opus-5-5 --report EVAL.json
python ABSOLUTE_HELPER show --repo WORKTREE --task MEL-003 --brief | --who | --roster
python ABSOLUTE_HELPER roster-sync --repo WORKTREE --task MEL-003
```

- Every authorship declaration names the model. The ledger records the files that changed since the last
  record (diffed against a tree object of the previous working copy), so `show --who` answers "which model
  touched which file".
- With `--scope`, a declared change outside the globs is refused until a reason is recorded or the plan is
  revised.
- Record every review round, whatever its verdict. Past the budget, `--extend` needs a reason. A round is
  one report for one kind, snapshot and plan: registering the same file twice counts once, the same bytes
  for another snapshot count again. Record a round before editing the plan or code it reviewed (or declare
  the edit first with `update --builder`).
  REVISE or BLOCKED clears final inspections and evals and downgrades `ready`; a plan round also clears
  plan approval and any earlier waiver, so implementation needs renewed approval or a new user waiver.
- `finding` attributes a confirmed finding from a recorded round to a builder and model in this task's
  ledger; the roster (`MEL_ROSTER`, default `~/.mel/roster.jsonl`) receives it after the state is saved.
  Roster events come from task state with stable ids, so a failed roster write only prints a warning and
  `roster-sync` appends what is missing, never twice. A model with 2 high, or 4 high+medium, findings in its
  last 10 tasks is benched as a builder; using it needs `--override` with the user's approval. The bench
  check counts this task's findings even before they reach the roster; other tasks' unsynced findings count
  once their own `roster-sync` runs. A declaration that changes no files (crediting work already declared,
  e.g. after a commit) is never refused for a bench.
- `--risk high` needs `--rubric FILE` at init: the reviewed rubric `[{id, criterion, threshold}]`, part of the
  plan, recorded by hash; `revise-plan --rubric` replaces it with the plan, and both are reviewed again.
  `ready` then needs an eval per contribution, like inspection: each native builder's work judged by the other
  provider, backend work by any native one. The judge's report gives `{judge, results: [{id, score,
  evidence}]}` for every rubric id, each at or above the rubric's threshold. Evals bind to snapshot, plan and
  rubric and are cleared by code, ownership or proof changes and unsuccessful review rounds. A complete eval
  that scores below a threshold is recorded (`eval_failures`), voids every earlier eval and blocks `ready` on
  that snapshot until the same judge passes it; the command exits 1 but the revision has advanced, so
  reread state before the next call.
- Writing a rubric item: one observable criterion (what a reader can check in the code or output, not
  "good quality"), a numeric threshold on a stated scale (e.g. 0-5, pass at 4), and in the plan the decisive
  pass case and fail case for it; the judge must cite evidence (file:line, command, output) per score. The
  `ai-eval` skill, where installed, has more patterns; it is optional.
- A finding counts once per task and id; a severity change or retraction needs `finding --correct REASON`.
  `approve-plan` and `inspect` count their own round; use `round` for REVISE or BLOCKED reports.
- `show --brief` is the resume packet for agents and new sessions (see [context.md](context.md)).
