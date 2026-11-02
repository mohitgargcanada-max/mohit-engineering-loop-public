# Bugs

No production bugs fixed in this original initial build. Behavioral findings are covered by regressions.

## 2026-10-22 - checkpoint commits invalidated their own handoffs
Symptom: committing `.mel/` evidence advanced HEAD and made acknowledgment reject
an unchanged code snapshot. Cause: comparing whole snapshots including HEAD. Fix:
include code-index content in the fingerprint, compare semantic code snapshots while
retaining actual HEAD for traceability, and still require exact GitHub merge head.
Status: local implementation; regression tests cover metadata allow/code reject.

## 2026-10-22 - Git autocrlf could alter immutable handoff bytes
Symptom: Git warned checkpoint JSON would become CRLF on checkout. Cause:
byte-digest transfers lacked a checked-in line-ending rule. Fix: init writes a
scoped task `.gitattributes` forcing JSON LF; existing conflicting policy is rejected.
Status: regression explicitly commits and checks out with core.autocrlf=true.

## 2026-10-25 - MEL-003 review rounds retained stale approvals (F1)
Symptom: REVISE/BLOCKED rounds left approved tasks ready and plan implementation allowed.
Cause: counting rounds did not invalidate approvals. Fix: unsuccessful rounds clear
inspections/evals and downgrade ready; plan rounds also clear plan approval, including
when a report is recorded again. Status: fixed in f7caf2e (Codex as builder, inspected by Claude); renewal regressions added.

## 2026-10-25 - MEL-003 finding corrections broke summary views (F2)
Symptom: roster double-counted corrected findings and crashed on retractions; brief
listed closed findings. Cause: summaries counted historical events as current findings.
Fix: count the latest severity per model/repository/task/id, ignore retracted or unknown
severities, show only current open findings in brief, and retain report hashes in roster
events. Status: fixed in f7caf2e (Codex as builder, inspected by Claude); CLI correction/retraction and provenance regressions added.

## 2026-10-25 - MEL-003 raw Claude capacity input crashed (F3)
Symptom: the advertised raw plan input raised AttributeError with a traceback.
Cause: a string plan name was mistaken for a wrapper object. Fix: distinguish the
wrapper by dictionary type, validate the plan/window shapes, and report CLI shape errors
with ERROR and exit 1. Status: fixed in f7caf2e (Codex as builder, inspected by Claude); CLI form-equivalence and malformed-input regressions added.

## 2026-10-26 - MEL-004 integration review of merged v0.3 (I1-I8)
Found by the first review of MEL-001..003 as one whole (Codex, confirmed by Claude); each task's own review
had passed. Fixed in MEL-004 by Claude, regressions in tests/test_task_state.py and tests/test_capacity.py:
- I1 a user waiver survived a REVISE/BLOCKED plan round -> the round now voids it (kept in plan_history).
- I2 revise-plan could not change scope or criteria -> `--scope`, `--criterion`, `--drop-reason`; the new
  scope judges the changes declared with it (P1).
- I3 rounds deduplicated on report bytes alone -> keyed by kind, report, snapshot and plan.
- I4 capacity said `go` for undated or one-window readings -> `unknown` unless a window is exhausted.
- I5 a failing eval was not recorded and an old pass kept `ready` -> recorded, voids evals, blocks ready
  until the same judge passes (P3).
- I6 `init --base` credited adopted work to the owner -> `--adopt BUILDER=MODEL` or `--adopt-unknown`.
- I7 roster writes after the state commit could be lost -> events derived from state with stable ids,
  `roster-sync`, and the bench counts this task's unpublished findings (P2, P4).
- I8 a no-file re-declaration of a benched model needed an override -> no bench check without changes.
Status: implemented on claude/mel-004-integration-providers; Codex final inspection and Claude
integration review pending at the time of writing.

## 2026-10-27 - MEL-006 unattended integration contract (G1-G3, G7)
Symptom: applying cloud PRs directly onto the base could not satisfy local task merge gates;
cloud verdicts could certify a different applied tree; runner guidance omitted path/model/capacity
accounting. Cause: unattended guidance did not carry the normal delivery contract through import.
Fix: separate local task worktrees and ancestry-preserving merges, pinned tree comparison, bound
post-run adoption, actual model records and native-provider independence. Status: implemented
locally; documentation walkthrough and coordinator proof required, independent inspection pending.

## 2026-10-27 - MEL-006 approximate authorship hidden in summaries (G4)
Symptom: MEL-001-shaped Codex-only state hid approximate file attribution and the need for both
integration providers. Cause: who()/brief() dropped ledger attribution. Fix: show the recorded
approximate reason and both integration builders without changing state. Status: implemented
locally; CLI regression fails on old helper, with exact-ledger and legacy-builder controls.

## 2026-10-27 - MEL-006 finding gate gave unusable flags (G8)
Symptom: finding rejected changed code even when its required builder/model flags were present.
Cause: those flags blame the defect rather than declare new edits, but the gate did not explain it.
Fix: direct other commands to a separate authorship update, retaining revise-plan scope ordering.
Status: implemented locally; CLI regression fails on old message and checks unchanged state on
rejection, separate fix-author credit and preserved defect attribution on retry; inspection pending.

## 2026-10-27 - MEL-006 tree comparison allowed diff conversions (IR1)
Symptom: cloud approval could be reused for different shipped bytes. Cause: the documented
comparison allowed textconv/external drivers and configured submodule ignoring. Fix: disable
textconv and external diff, force --ignore-submodules=none, retain the exact metadata/plan
exclusions and require exit 0. Status: implemented locally; independent inspection pending.

## 2026-10-27 - MEL-006 cloud export omitted binary payloads (IR2)
Symptom: changed binary assets could not be imported with the documented patch procedure.
Cause: plain git diff lacks applicable binary payloads. Fix: export with --binary --no-ext-diff
--no-textconv; require a successful export and retain apply exit-status/conflict checks.
Status: implemented locally; git apply --check rejected the plain export (exit 1) and accepted
the binary export (exit 0); independent inspection pending.

## 2026-10-27 - MEL-006 brief hid unknown adopted builders (IR3)
Symptom: a coordinator declaration or mixed known/unknown adoption hid recorded builders and
the unknown-authorship reason in brief(). Cause: a nonempty ledger replaced the builder list,
and adoption metadata was omitted. Fix: retain ledger models, append recorded builders missing
from the ledger and display the adoption warning. Status: implemented locally; both required
in-memory controls failed on the old helper and pass with the fix; exact-model and no-ledger
controls also pass. Independent inspection pending.
