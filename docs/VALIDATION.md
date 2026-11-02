# Validation - MEL-001

Final code commit: a5fa2f41ef640d851b6654492b6fce46b0c61a90 (helper last changed in f100d934).
Corrected 2026-10-24 (MEL-001 review L1): this header previously named f100d934, run
39893669233 and 28 tests; `.mel/MEL-001/verification-001.json` records the final run.
CI: run in the private development repository.

- Windows and Ubuntu CI both passed the complete 29-test suite and metadata/link/
  syntax/credit validation. Tests use disposable Git repositories and fake GitHub
  responses; they consume no model quota and perform no live merge.
- Local execution passed the original 23-test suite plus five added targeted
  regressions. A recursive test mock was corrected before the passing runs.
- Coverage includes concurrent writers, atomic-save failure, stale revisions,
  ownership, handoff tampering/acknowledgment, plan/proof/report changes, mixed
  authorship, incomplete readiness, real-head merge readback, preserved baseline,
  and metadata-only checkpoint commits versus real code changes.
- An additional local regression passed a real commit/checkout with core.autocrlf=true.
  Per-task attributes now preserve immutable JSON byte digests; the suite contains 29 tests.
  Check the draft PR for the latest full cross-platform rerun.
- Both installed copies of the original eight-file skill were byte/hash verified
  against the source. No existing upstream skill was replaced.
- Original metadata, local links, Python syntax, owner copyright and Chase AI
  inspiration credit validated. No upstream code, assets, runtime or skill text is
  distributed. External tools/services retain their own terms.

## Limits

No independent Claude plan review or final inspection completed. Claude login was
verified, but the restricted review returned quota exhaustion. The user explicitly
authorized implementation and draft publication while review and merge are deferred.
No proof of a live two-provider delivery is claimed. State/report truth depends on
honest coordinator attestations; this is not an OS sandbox or cryptographic model
identity service. CRISP integration is optional operational guidance, not a bundled
telemetry adapter. GitHub branch-protection enforcement has not been configured by
this task. The draft PR must remain unmerged until the outstanding review is resolved.

A1-A6 evidence: skill/references, helper, regression suite, both installation checks
and a draft PR in the private development repository.
A7 remains open in canonical task state. This summary is sanitized; private raw
review diagnostics and local test logs are not committed.

# Validation - MEL-002

Builder: Claude (Opus 5.5). Plan review and final inspection: Codex (GPT-6.1 Sol, high, read-only sandbox,
Codex app CLI 0.163.0-alpha; the npm CLI 0.153.4 refused the model). Reports: `.mel/MEL-002/`.

- Plan: round 1 REVISE (P1-P4 accepted), round 2 APPROVED for plan sha 1b4d817f.
- Final inspection 1 on b0c92f0: REVISE, F1 high (local target accepted revision expressions such as
  `branch~0`, so a task could be recorded as merged into itself). Fixed: exact branch names only
  (`check-ref-format --branch`, `show-ref --verify`), with negative controls for `~0`, `^0`, `@{-1}`,
  `HEAD@{0}`, `main~0` and `refs/heads/main`. Low notes fixed: README status, standards wording.
- Local (Windows): 41 tests OK, validator passed. CI and the second inspection are recorded in the PR.

Limits: actor, reviewer, backend identity and takeover approval are caller attestations. OmniRoute was
not installed or contacted; its commands come from its README (v3.8.53, read 2026-10-24).

# Validation - MEL-003

Builder: Claude (Opus 5.5). Plan review waived by Mohit until Codex's limit reset (recorded in
`.mel/MEL-003/state.json`); Codex plan check and final inspection run before any install or merge.

- Helper: model-attributed authorship ledger (tree-object diffs), scope guard, review rounds with budget,
  findings attributed to builder+model, cross-project roster with benching, rubric eval for high-risk tasks,
  `show --brief/--who/--roster`. New `scripts/capacity.py` for 5-hour and weekly windows per provider.
- New references: discipline.md, context.md, capacity.md; standards.md gains the spend rule, parallel work
  and test-expectation rule. Matt Pocock's and the multica Karpathy skills were compared (the local
  karpathy-guidelines copy is identical upstream); five ideas were re-written in our own words.
- Plan: Codex rounds 1-2 REVISE (P1-P7, all accepted), round 3 APPROVED (plan sha 996e9e4c).
- Final inspection: Codex r1 REVISE (F1-F3 medium, attributed in the roster to claude/claude-opus-5-5); Codex fixed
  them as builder (f7caf2e), Claude inspected that fix, Codex r2 APPROVED. Reports in `.mel/MEL-003/`.
- Local (Windows): 74/74 tests and the validator, run independently by Claude after Codex's own run.
- Known low: committing already-declared changes alters the fingerprint, so a no-file re-declaration follows a commit.

# Validation - MEL-004

Initial builder: Claude (Opus 5.5); Codex (GPT-6.1 Sol) built the final F1-F5 fixes in
`223be0f4e61b1d5059b3f6450e68d836fbe42acb`. Codex checked the plan and inspected Claude's work;
Claude inspected Codex's contribution. Reports: `.mel/MEL-004/`.

- Origin: the first review of the merged MEL-001..003 as one whole (Codex `whole-main-review-r1.json`, REVISE
  I1-I12; Claude's preliminary half `claude-whole-main-review.json`). Each task's own review had passed.
- Plan: Codex r1 REVISE (P1-P6), r2 REVISE (P5, P7), r3 APPROVED (plan sha b40146d6).
- Helper fixes I1-I8 with regressions (see `.crisp/BUGS.md`); docs I9-I12; integration-review rule
  (delivery.md, standards.md, SKILL.md, README); $0-first provider guidance (backends.md, dated 2026-10-26).
- Deliberate contract changes, tests updated: `init --base` with existing work needs `--adopt` or
  `--adopt-unknown`; a complete failing eval is recorded and advances the revision.
- Initial local proof: 85/85 tests in 886 s. Final recorded proof on `223be0f`: **90/90** in 955 s
  (Windows), run by Claude after Codex's own 90/90, plus the validator, per
  `.mel/MEL-004/verification-004.json`. Before the contract-test updates, the old suite against the
  new helper failed exactly those three tests (60/63).
- Reciprocal final reports: `.mel/MEL-004/claude-inspection-final.json` (Codex's F1-F5 contribution and
  Claude's integration half) and `.mel/MEL-004/final-inspection-r2.json` (Codex's final inspection and
  integration half), both APPROVED at `223be0f`. Codex's final inspection did not rerun the suite in its
  read-only sandbox; its 90/90 reference is coordinator evidence. The historical plan's different
  proposed Claude report filename is unchanged; `claude-inspection-final.json` is the actual report.

# Validation - MEL-005

Documentation task: unattended Codex queue operation while Claude is exhausted, files-only cloud
snapshots and independent cloud review. The committed ledger in `.mel/MEL-005/state.json` records
Claude Opus 5.5 for the initial work and Claude Sonnet 5.5 for the revision; no helper code changed.

- Codex plan round 1 REVISE (P1-P3), round 2 APPROVED for plan SHA
  `cba681ff024dc887c599c6c7ae277b1918813e993923711242606893e6982894`.
- Codex's recorded APPROVED inspection (`inspect_r2.json`) covers the scoped documentation at
  `43b20271f3ef419e82cfe5b57f42a6bf755031f2` and reports a passing validator. It explicitly did not run
  the full suite, queue, cloud push or merge, and does not approve combined-stack integration.
- Coordinator `proof.log` records **90 tests OK in 1034.468 s**, plus a passing validator, at
  `848b52687b1c9150aa0e3db6e18045fba5960c19` on 2026-10-26. During MEL-006 these Temp evidence files
  (`plan_r2.json`, `inspect_r2.json`, `proof.log`) were available and their SHA256 values matched the
  references in the committed state. These are historical results, not new MEL-006 runs.

Limits: Temp evidence is private and may later be unavailable; the committed state retains its paths
and digests. No live runner/cloud execution, current CI, installation or merge verification was
performed for this documentation correction. MEL-006 proof and fresh combined reviews are separate.

# Validation - MEL-009

Helper (`task_state.py`) and documentation task: single-provider mode, plan-quality gates, router backends, project fit.
Plan: Fable review round 1 REVISE (R1-R4), round 2 approved (see `docs/tasks/MEL-009-plan.md`).

- New tests: `SingleProviderTests` in `tests/test_task_state.py`. Run against a copy of the pre-change helper (`main` eb45602),
  every new test fails except the two labelled controls (no-mode refusal, legacy state), which pass on both.
- Not verified: the attested fields (`fresh_session`, `built_nothing`, `--approved-by`, `--user-approval`) cannot be checked by the
  helper; model equality is the one enforced discriminator and compares normalised strings only. No live provider, router or
  CI was exercised; backend routes remain unverified until a live probe.
