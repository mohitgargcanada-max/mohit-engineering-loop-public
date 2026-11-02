# MEL-002 implementation plan

Scope B1-B8 in MEL-002.md. Stdlib only; schema stays 1 and existing MEL-001 state must still load.

## Helper (`scripts/task_state.py`)

1. Agent labels: `harness[@backend][:session]`, harness `claude|codex`, backend `[a-z0-9][a-z0-9._-]*`.
   Owner, recipient and actor keep the FULL label (session included) and are compared as full labels,
   as today. A normalized key (`harness` or `harness@backend`, session dropped) is derived only for
   builders, reviewers and coordinator independence. A key without a backend is native. Old labels
   (`codex`, `codex:resume`) parse unchanged.
2. B1 authorship gate. State gains `recorded_fingerprint` (set at init and after every mutation). In
   `mutate`, if the current fingerprint differs from it, or it is absent (legacy state: authorship since the
   last record is unknown), the call must carry `authored_by` (CLI `--builder`, accepted by update, handoff,
   takeover and revise-plan, because plan files live in the repo); otherwise refuse: "Code changed since the
   last record; declare its author with --builder." The declared key is added to builders. Only `ack` is
   exempt: it already requires the exact snapshot recorded in the transfer. `.mel/` stays outside the
   fingerprint, so metadata commits never trigger it.
3. B5 independence. `approve-plan` and `inspect` need a native reviewer; plan reviewer != coordinator key.
   `ready` needs, per builder: native builder -> review by the other native provider; backend builder ->
   review by any native provider. Reviews keep binding to the exact snapshot and report hash.
4. B6 `takeover --actor NEW --reason TEXT [--builder KEY]`: actor differs from owner, reason non-empty,
   task not merged. Marks any pending transfer superseded (never deletes its file), sets owner, clears
   reviews, downgrades `ready` to `review_pending`, records revision/from/to/reason/fingerprint. Reason is an attestation that the
   user approved it, like the plan waiver. `handoff --capacity TEXT` (repeatable) stores capacity notes.
5. B3 `show` loads without the worktree binding check. All mutations keep it.
6. B4 `init --local-target BRANCH` records `delivery: {mode: local, target}`; init requires
   `refs/heads/BRANCH` to exist and differ from the task branch. Local `ready` does not need a PR. Local
   `merged` resolves `refs/heads/BRANCH^{commit}` to an OID (never the short name, so a same-named tag
   cannot answer), checks `git merge-base --is-ancestor HEAD <OID>`, and records target ref and OID.
   GitHub mode is unchanged and remains the default.

## Docs

SKILL.md: short pointers only (fallback ladder rule, standards, backends). New `references/standards.md`
(roles -> models, coding/architecture/design/review standards, builder decision, change control) and
`references/backends.md` (OmniRoute: install/self-host, per-process launch, labels, data boundary,
memory sizing, review gate, identity limits). Update delivery.md, handoffs.md (B2), README, ATTRIBUTION
(OmniRoute credited as optional external MIT tool, not bundled), VALIDATION (MEL-001 L1 + MEL-002).

## Proof

`python -B -m unittest discover -s tests -v` and `python -B scripts/validate.py` on Windows locally and
CI (Ubuntu + Windows). New regressions, each with a control that must fail:
- undeclared code change refused; declared builder then needs the other provider (repro from review H1);
- metadata-only commit does not trip the gate; legacy state (no `recorded_fingerprint`) still loads and
  shows, but its first mutation, including an inspect after an undeclared commit, needs `--builder`;
- session labels: after `codex` hands off to `codex:s2` and it acks, `codex` can no longer mutate;
- takeover of a ready task: reviews cleared, status review_pending, ready fails until a fresh inspection;
- local target: a tag named like the target branch pointing at HEAD does not make merged pass;
- backend label parsing; backend reviewer refused for plan and inspection; backend builder not ready
  without a native review, ready with one;
- takeover: refused for current owner/empty reason/merged; archives pending transfer; new owner can act;
- show from a second worktree works while update from it is refused;
- local delivery: ready without PR; merged refused before the target contains HEAD, accepted after;
  GitHub-mode task still needs a PR.
Existing tests changed only where a code change now needs `--builder` (the gate's intended effect).

Review: Codex plan review (read-only sandbox), then fresh Codex final inspection of the full diff.
Install to ~/.claude/skills and ~/.agents/skills only after inspection, with backups of current copies.
