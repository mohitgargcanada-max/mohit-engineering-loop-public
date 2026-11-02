# Numbered, versioned handoffs

One canonical task file holds current state; do not clone it into competing trackers.
Use one `.crisp/HANDOVER.md` per project with session-owned sections pointing at task
IDs and revisions. Transfer evidence is immutable and independently numbered within
the task; Git history preserves committed revisions. Private evidence stays outside Git.

A transfer records schema version, task ID, increasing handoff number, unique transfer
ID, state revision, predecessor, sender/recipient, repo/branch/HEAD/dirty fingerprint,
plan digest, all accepted/pending criteria, proof references, blockers, constraints,
permitted actions and exact next action. The helper requires explicit constraints,
permission scope and next action. Do not send credentials or entire chat histories.

```text
python ABSOLUTE_HELPER handoff --repo WORKTREE --task MEL-001 --expected 3 --actor codex --to claude --constraint "Project repo read-only" --permission "Read and inspect only" --next "Inspect criterion A2"
python ABSOLUTE_HELPER ack --repo WORKTREE --task MEL-001 --expected 4 --actor claude --handoff MEL-001-H001-UNIQUE --digest SHA256
```

Read the actual returned transfer ID and digest; do not type the placeholders above.
The recipient checks that the transfer is current, validates its content digest and
Git fingerprint, and acknowledges that exact transfer before taking ownership.
A pending transfer freezes every state change except `ack`, `handoff --replace` and
`takeover`; `show` stays available (read-only, from any worktree). Record reviews
after acknowledgment. The plan author (`--plan-author`) stays fixed across transfers, so the plan reviewer is always the other provider. Reissue a stale transfer from the current snapshot with
`handoff --replace`; retain old evidence and link the predecessor. No silent
takeovers or auto-removal of locks.

When the owner cannot continue (for example its weekly quota is exhausted) and the
user approves, the new agent runs `takeover --actor NEW --reason "Mohit approved: ..."`.
It marks any pending transfer superseded (its file is kept), records who, why and
the code fingerprint, clears reviews and downgrades `ready`. The reason is an
attestation of the user's approval, like a plan waiver; never take over on your own.
Add `--capacity "codex weekly 90%, resets Oct 31"` to a handoff so the next agent
knows why it moved.

In single-provider mode the task state holds the mode (reason, who approved, date). A handoff, acknowledgment or takeover involving the unavailable provider is refused until `single-provider-leave`; the mode and its label survive handoffs to the available provider and are repeated in `show --brief`.

Code that changed since the last record must be credited before anything else is
recorded: pass `--builder LABEL --model MODEL` (on update, handoff, takeover or
revise-plan) naming who wrote it. `--builder` requires `--model`. An undeclared
change is refused, so a new owner cannot edit code and then inspect it as though
someone else wrote it. Legacy task state has no record
and needs one declaration on its first mutation.

Updates use expected revisions, a cooperative exclusive lock and atomic state-file
replacement. A concurrent writer gets an explicit failure; reread and reconcile.
A crash can leave a lock or orphan transfer file: inspect process state and contents,
then recover deliberately. Never delete a lock automatically on a time heuristic.
The lock protects cooperating helper invocations, not arbitrary editors or Git.

Cross-session continuation by the same provider also uses a transfer. Labels are
`harness[@backend][:session]`, e.g. `codex:session8` or `claude@openrouter:night1`.
Ownership compares the full label; builders and reviewers use the label without
its session. Model identity is separately recorded in the plan; provider labels
alone do not prove independent inspection.
For a new machine/worktree, do not edit the bound repo path: reconcile a new task
record referencing the old checkpoint, verify Git state and carry unfinished criteria.

A session checkpoint must distinguish done, open, blocked and superseded items.
Completion requires every accepted criterion; blocked items retain their number.
Handoff acknowledgment proves an unchanged snapshot was accepted, not that the
recipient understood every constraint. The coordinator remains responsible for proof.

Checkpoint commits containing only `.mel/` metadata may advance HEAD without
invalidating a transfer or inspection. The fingerprint includes the code index,
staged/unstaged differences and untracked deliverable bytes, while recording actual
HEAD for traceability. A changed committed code tree still invalidates evidence.
GitHub merge readback always checks the actual local HEAD, not a prior snapshot HEAD.

Each task initializes a `.gitattributes` rule forcing its JSON to LF so an
immutable handoff digest survives Windows autocrlf checkout. Retain that rule
with the state and transfer files. Existing conflicting attributes cause init to
fail rather than silently overwriting project policy.
