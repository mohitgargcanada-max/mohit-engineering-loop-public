# MEL-006 implementation plan

Scope G1-G9 in MEL-006.md. Baseline: 0374717de36d753a02884b1e9faad4efe77337db;
branch: codex/mel-006-integration-fixes. Codex (gpt-6.1-sol) authors the plan and builds;
Claude reviews the plan and inspects. Sequential work, no delegated builders, stdlib unittest only.
Budgets: plan 2 / inspect 2; an additional round needs a recorded reason, never a silent reset.
This revision writes only MEL-006-plan.md with LF; MEL-006.md needs no criterion wording change.
Implementation, tests, state updates, review dispatch, commits and delivery below are future work
after plan approval.

## Baseline verification and disposition

The branch and HEAD matched the requested baseline, with no tracked diff or untracked deliverables
before these files were written. Paths below are repository-relative; `H` means
`skills/mohit-engineering-loop/scripts/task_state.py`, `R` means
`skills/mohit-engineering-loop/references/`. Findings were checked against implementation bodies,
not inferred from docstrings. No helper was executed.
Round-1 REVISE (R1 and plan-related Lows) was rechecked at HEAD 3eaff3d; the existing
`.mel/MEL-006/state.json` diff is preserved. The revision below changes no helper behavior.

- S1 confirmed: `R/unattended.md:36-39` applies onto the local base. `H:145-146` refuses a local
  target equal to the task branch; `H:788-805` requires local target ancestry or the exact GitHub
  `headRefOid == current['head']`. A re-applied snapshot PR cannot certify the local merge. G1.
- S2 confirmed: `R/unattended.md:45-50` says to record the cloud verdict like any inspection without
  checking the applied tree. `H:504` binds approval to the current local snapshot; `R/standards.md`
  Review standards says a new edit invalidates approval. G2.
- S3 confirmed: `R/unattended.md:7-25` omits task/capacity handoffs and its done fields omit model ID;
  its cloud section omits path binding. `R/standards.md` Fallback ladder and `R/capacity.md` require
  `handoff --capacity`; `H:113-114` rejects mutations from a different worktree. G3.
- S4 confirmed: `H:346` writes an `attribution` string beginning `approximate:`. `who()` at 756-766
  prints builder/model/files and unknown adoption, but drops that field; `brief()` at 730-754 also
  drops it. Positive control: `.mel/MEL-001/state.json` has builders=['codex'] and an approximate
  Codex ledger entry. `R/delivery.md#integration-review` requires both providers for approximate
  attribution. Existing pruned-tree test checks storage only; legacy-who test checks missing ledger. G4.
- README lows confirmed: Details and layout omit unattended, the task range ends at MEL-004 and
  Status omits MEL-005. This also covers Codex's one low. G5.
- VALIDATION low confirmed: MEL-004 still names only Claude and 85/85. Commit `223be0f` identifies
  Codex's F1-F5 fixes; `.mel/MEL-004/verification-004.json` records final 90/90 on that commit, with
  reciprocal reports `claude-inspection-final.json` and `final-inspection-r2.json`. No MEL-005 section
  exists; its state records Claude Opus/Sonnet ledger entries, Codex plan approval and inspection. G6.
- Provider low confirmed as a scope ambiguity: SKILL.md:51 says "one provider is out", while the
  documented runner is Codex while Claude is out. The cloud section already rejects same-provider
  inspection, but never says cloud location does not establish provider identity. G7; no new runner.
- Historical filename low confirmed but harmless: MEL-004-plan.md names
  `claude-integration-final.json`; the committed `claude-inspection-final.json` explicitly covers
  Claude's integration half and the Codex-built contribution. Leave the historical plan and report
  unchanged; use the real filename in current validation documentation. No missing-review fix.
- Finding gate low confirmed: `H:836` constructs an author from the flags, but the finding dispatch
  at 872-874 passes them as the blamed builder/model; `finding()` at 640-667 calls `mutate` without
  author. On changed code, the gate at 379 therefore asks for flags already supplied. G8 fixes the
  guidance, not the gate or finding identity. None of the reported substantive findings is rejected.

## G1-G3, G7 unattended contract

Change `R/unattended.md` in place; retain the useful launch, lock, secrets-scan and apply lessons.
Change only the unattended pointer in `skills/mohit-engineering-loop/SKILL.md` for G7.

- G1: bring each PR home to a separate task branch/worktree cut from the then-current local base.
  Commit the task plan before clean init; use `init --local-target BASE`, review the plan, then apply
  that PR's pinned snapshot-base..head diff there with `git apply --3way`. Declare all imported
  authors/models, run coordinator proof, commit and reconcile the recorded snapshot, pass criteria,
  inspect and ready before an authorized merge into BASE. Record `merged` from the task worktree
  after Git confirms BASE contains its head; do not squash away that ancestry. A snapshot-repository
  PR URL is source/review provenance, never the local task's `--pr` merge evidence. If adopting work
  after application, use `init --base ... --adopt PROVIDER=MODEL` for its actual authors instead.
  Application order matters for per-file credit: apply each author's portion and declare it before
  applying the next. Declaring several authors after one combined apply only credits all builders;
  later no-file declarations do not partition the first declaration's files. Adoption is also coarse.
- G2: pin the reviewed PR head and report; compare its reviewed tree with the final applied tree
  before treating the cloud verdict as local inspection evidence. An equal patch or a clean apply
  is insufficient. Fetch both pinned commits and document the byte/tree comparison, e.g.
  `git diff --exit-code PR_HEAD LOCAL_HEAD -- . ':(exclude).mel/**' ':(exclude)docs/tasks/MEL-006-plan.md'`.
  Exclude only `.mel/` task metadata and the exact committed local task plan path (substitute that
  task's path in the example); name both in the review boundary. Never exclude a shipped change to
  manufacture equality. Convert a cloud verdict comment into inspect's JSON report schema:
  `verdict: APPROVED`, the actual native `reviewer`, nonempty `coverage` string list, empty `findings`
  list and `limitations` list; preserve the source comment/head and comparison evidence before
  recording it against the local snapshot. Any changed base
  content, conflict resolution or later shipped edit makes the trees differ and needs fresh review
  of the local result. Declare coordinator resolutions and cloud reviewer fix commits as authorship
  with their real models; apply reciprocal inspection where both providers built. Link the batch's
  final combined review to `delivery.md#integration-review`.
- G3: pre-dispatch, the coordinator records task/scope/plan, owner, chosen builder/model and capacity
  decision in the spec and/or its own pre-dispatch record, bound only to its own worktree if tracked.
  The runner creates a fresh worktree when the spec starts and never runs the helper: never hand off
  to it. Use `handoff --capacity` only to a recipient who will acknowledge it under the existing rules;
  a pending transfer freezes the task. Afterwards, record runner output as a new task bound to the
  runner's worktree (or a fresh coordinator worktree holding the result), referencing the pre-dispatch
  record per `handoffs.md:54`: `init --base <runner base commit> --adopt codex=<model from the done record>`.
  If that record lacks a model, use `--adopt-unknown REASON`, never guess. Do not copy state or change
  its bound path. A cloud clone receives an immutable brief and returns diff/report/model evidence;
  the bound coordinator adopts/declares returned work and records proof. Require the actual model ID
  in successful done records and retain short failures when no model ran: a required external runner
  contract, not a claim the private reference runner already emits the field or an instruction to edit it.
- G7: scope the SKILL pointer to Claude exhausted/Codex available. In unattended.md, classify cloud
  work by its actual native provider/model or backend label; a second Codex cloud session is still
  Codex and cannot inspect Codex-only work independently. Wait for the required provider when absent.

Proof: walk the rewritten flow against existing init/adoption, handoff, inspect, ready and merged
bodies. In disposable Git repos during implementation, exercise PR application on a separate local
task branch through authorized-fixture merge/record, and the target==task-branch rejection. Compare
equal trees as the positive cloud-review case and changed-base/conflict-resolved trees as negative
cases needing local review. Walk pre-dispatch spec through post-run adoption (known/missing model),
checking capacity, base, returned model, new bound path and reference to the pre-dispatch record;
assert no pending handoff to the runner is ever left in place.
Do not claim a live cloud/runner test or edit that external repository. Reuse existing merge/binding
tests; no new orchestration or documentation-string test framework.

## G4 approximate attribution output

Change `H`'s `who()` and `brief()` only for this finding: add a compact attribution warning when a
ledger entry is marked approximate, including the recorded reason and "integration builders: claude,
codex". Match the stored `approximate:` value, not only exact equality to 'approximate'. Preserve
builder/model/file details and legacy-builder output. Do not rewrite builders, readiness policy,
ledger records, schema or old state; this exposes uncertainty for the existing integration rule.

In `tests/test_task_state.py`, use existing disposable fixtures and CLI `show --who` / `show --brief`:
a MEL-001-shaped state with one Codex builder and approximate entry must expose the reason and both
integration providers in both outputs. Include the pruned-tree producer path, plus exact attribution
(no warning) and legacy recorded-builder/no-ledger controls (builder retained). New assertions must
fail at 0374717 and pass with the output change; never mutate actual `.mel/MEL-001`.

## G5-G6 current documentation

- README.md: add the unattended Details link and layout description; extend the task index through
  MEL-006 with scope/plan pointers; summarize MEL-005's unattended guidance. Keep MEL-006 labeled
  planned until implemented and reviewed; do not promote this plan into a delivery claim.
- docs/VALIDATION.md: correct MEL-004 to Claude's initial build plus Codex `223be0f`, final 90/90,
  and the actual reciprocal report filenames. Add MEL-005's documentation scope, recorded builders,
  Codex plan review/inspection and available proof. Read referenced evidence before claiming any test
  count; if its Temp logs are unavailable, say what state attests and what cannot be reproduced.
  Distinguish recorded historical proof from new MEL-006 runs and live CI/merge verification.

Proof: compare each statement to the committed reports, verification JSON and ledger; run the
validator for links/metadata. Leave docs/tasks/MEL-004-plan.md and all prior evidence bytes unchanged.

## G8 actionable finding gate

Change only `H`'s changed-code error at `mutate`, retaining the substring `declare its author`
asserted by tests at 184, 235 and 254. Direct callers to `--builder ACTUAL_AUTHOR --model ACTUAL_MODEL`
on update, handoff, takeover or revise-plan; other commands need a separate update with those flags
before retrying. Preserve revise-plan's ordering: it installs the new scope before declaring the edit,
so do not prescribe a separate update against the old scope for that path. Clarify that
`finding --builder/--model` attributes the reported defect, not the current edits. Reuse the existing
gate and update route; no bypass, implicit declaration or new CLI flag.

Add a stdlib CLI regression in `tests/test_task_state.py`: record a valid review round/ledger author,
edit a shipped file, then call finding with that blamed author. It must fail with the separate-update
instruction and leave revision/ledger/findings unchanged. Declare the edit with update using a
different actual author/model, reread revision, retry finding and assert its blamed author/model are
preserved while the new edit has its own ledger credit. Unchanged-code finding still succeeds.

## G9 proof, review and risks

After plan approval, implement within the listed files plus the required scoped `.crisp/BUGS.md`
entries for confirmed fixes; add a MISTAKES entry only for an actual new mistake. Keep the skill terse
by replacing ambiguous paragraphs, not appending a second workflow. Run targeted new regressions
first, then `python -B -m unittest discover -s tests -v` and `python -B scripts/validate.py` once the
changes settle; record actual results and limitations. No dependencies or test-count promises.

Claude reviews this exact plan, then freshly inspects the completed Codex-built task. Because the
combined MEL-001..006 stack has both native providers' authorship (including approximate MEL-001),
both Claude and Codex review the same fixed committed head against baseline 7883e28 plus every
shipped file. Codex's integration report is not self-approval of MEL-006; Claude supplies its independent
inspection. Fix material findings, rerun affected proof and renew both combined reviews on the new head.
Task state and delivery metadata are maintained only in the authorized implementation phase.

Risks: a newer local base will often prevent cloud-tree equality, requiring local reinspection;
conflict resolution can introduce a second builder; missing model records cannot be repaired by
guessing; historic Temp proof may be gone; Windows autocrlf can alter plan hashes. Preserve LF,
verify the exact plan digest at review, keep path/merge gates intact and use fresh proof where evidence
is missing. No install, external runner change, publication or merge is part of this plan-only run.
