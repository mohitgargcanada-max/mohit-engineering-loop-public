# Unattended work: Codex available while Claude is out

Lessons from 2026-10-25/26, when Claude's limit hit mid-wave and work continued through Codex and cloud
sessions on a private project. Every result produced this way still needs the usual
independent review, the coordinator's own proof run and an authorized merge.

## A Codex queue runner while Claude is out

Write each piece of work as a self-contained spec file (`specs/NN-name.md`) and let a small detached runner
build them one at a time. A reference implementation lives in a private project (`.claude/codex-queue/run_queue.py` + `README.md`).

- **Before dispatch**, record the task ID, scope/plan, owner, chosen builder/model and the 5-hour/weekly
  capacity decision ([capacity.md](capacity.md)) in the spec or coordinator's pre-dispatch record. Any
  tracked record belongs only to its own worktree. The runner creates a fresh worktree when the spec
  starts and never runs the state helper: do not hand off to it. A pending transfer freezes mutations.
  Use `handoff --capacity NOTE` only for a recipient that will acknowledge it under [handoffs.md](handoffs.md).
- **One spec at a time, oldest first.** Each gets its own worktree and branch cut from the **current** base
  branch at the moment it starts, so later specs see earlier merges.
- **Codex builds, never commits or merges.** The runner writes `done/<name>.json` (branch, base commit,
  runner exit code, changed-file count, `reviewed_by_claude: false`, `merged: false`) and moves on. Require
  the **actual model ID** in each successful done record as an external runner contract; this is not a
  claim that the reference runner already emits it. Early
  failures (worktree add failed, no HEAD) write only a short `status` record. A done file means the spec was
  attempted, not delivered: read the exit code and the diff before trusting it.
- **Respect the project's own locks.** Wait while any job lock the project uses is held (for example scan locks).
- **Start it detached so it survives the session**: `pythonw` launched with `Start-Process -WindowStyle Hidden`.
- **Launch the Codex child with `CREATE_NO_WINDOW` (0x08000000).** Without it, children died with
  `0xC000013A` (console closed) when the launching console went away; both jobs of the first night were lost.
- **Find `codex.exe` on every run**: take the newest `%LOCALAPPDATA%\OpenAI\Codex\bin\*\codex.exe`. A Codex app
  update moved the binary and broke a hard-coded path.
- **The coordinator always runs the proof.** Codex's sandbox could not launch the project's test runner at
  all; "tests written, could not run" is not proof (see delivery.md, *Proof and review hygiene*).

After the run, read the done record and diff, then create a new task bound to that runner worktree,
referencing the pre-dispatch record. The plan file must already exist there. For local delivery in a
repository without a GitHub remote, a complete example is:

```text
# H is the absolute path to scripts/task_state.py; WT is the runner's worktree.
# BASE is the existing receiving branch, distinct from WT's task branch.
python H --repo WT --task MEL-010 init --owner claude --plan WT/docs/tasks/MEL-010-plan.md --criterion A1 --local-target BASE --base RUNNER_BASE_COMMIT --adopt codex=ACTUAL_DONE_MODEL
```

Repeat `--criterion` for every accepted ID. For GitHub delivery omit `--local-target` and use the
normal PR workflow. If the done record has no model, replace `--adopt codex=ACTUAL_DONE_MODEL` with
`--adopt-unknown "Runner did not record its model"`; never guess. Adoption credits existing work
coarsely, so retain the original diff/model evidence. Keep the runner worktree until its task merges,
or reconcile the result into a fresh coordinator worktree and initialize a new task there against its
actual baseline, referring to the pre-dispatch record. Never copy `.mel/` or edit its bound path.
Review the plan, declare any coordinator edits, then prove, inspect and deliver under [delivery.md](delivery.md).
There must be no unacknowledged handoff to the runner left behind.

## Cloud sessions for a repository GitHub cannot take whole

When history contains a file over GitHub's 100 MB limit, the repository cannot be pushed as is.

1. Push a **files-only snapshot**: one commit holding the base branch's tree, parented on the remote's main
   (`git commit-tree <base>^{tree} -p origin/main`), to a **private** repository. Cloud sessions branch from it
   and open **draft** PRs.
2. **Secrets-scan the changed files before every snapshot push.** The push publishes code, so it needs the
   user's own approval or permission rule; an agent's push was correctly classed as data exfiltration.
3. Give the cloud clone an immutable brief (task/scope/plan, builder/model, capacity decision and base),
   not the coordinator's path-bound state. It returns a pinned diff, report and actual provider/model
   evidence. The bound coordinator adopts or declares that work and records its own proof.
4. Bring results home **one PR at a time**, each onto a separate task branch/worktree cut from the
   **then-current local base**. Commit its local plan before clean `init --local-target BASE` (with
   `--owner`, `--plan` and every `--criterion`, as above), then obtain plan review. Fetch and pin the
   snapshot base and PR head; export `git diff --binary --no-ext-diff --no-textconv SNAPSHOT_BASE..PR_HEAD`
   and apply the exported patch with `git apply --3way` in that task worktree. Check the export's exit
   status before applying. The apply uses the index and can leave conflict markers: check its exit code and
   `git status`, resolve every conflict and review the resulting diff.
   Union-resolve only append-only documents (journal, tracker, BUGS ledger), then check for duplicated
   lines. Resolve other conflicts by reading both sides.
   Declare each actual builder/model with `update --builder PROVIDER --model MODEL`. Apply each
   author's portion and declare it before the next author's portion: declaring several authors after
   one combined apply credits all builders but does not partition files (later declarations have no files).
   If tracking starts after application, use `init --base LOCAL_BASE_COMMIT --adopt PROVIDER=MODEL`
   for every actual author (or `--adopt-unknown REASON`), with the same required plan/owner/criterion/target
   flags. Adoption is also coarse; preserve the source evidence.
5. Run coordinator proof, commit the result and reconcile the recorded snapshot with an authorship
   update, then pass every criterion with proof, obtain fresh inspection and record `ready`. Only then
   perform the authorized merge into BASE, preserving task-head ancestry (no squash). From the task
   worktree, record `merged` after Git confirms BASE contains that exact head. Never initialize on BASE
   with BASE as its own target. The snapshot-repository PR URL is source/review provenance, **not** the
   local task's `--pr` merge evidence. Proceed to the next PR from the newly current base.
## A second cloud session as independent reviewer

A cloud session can review the batch's PRs, with revert-to-prove tests and a verdict comment per PR.
Classify it by its **actual native provider/model or backend label**, not its location. A second Codex
cloud session is still Codex. Only a fresh inspector of the **other native provider** of each native
builder, or any native `claude`/`codex` inspector for backend-built work, counts under delivery.md and
standards.md. When the required provider is absent, wait for it; cloud location supplies no independence.

Pin the reviewed PR head and report before bringing it home. Cloud approval counts locally only if the
reviewed and final applied trees are byte-identical across the shipped review boundary. Fetch both
pinned commits and retain the comparison, for example (substitute the exact local task plan path):

```text
git diff --exit-code --no-textconv --no-ext-diff --ignore-submodules=none PR_HEAD LOCAL_HEAD -- . ':(exclude).mel/**' ':(exclude)docs/tasks/MEL-010-plan.md'
```

Require exit 0; a difference or command failure cannot establish byte identity.
Name `.mel/` task metadata and `docs/tasks/MEL-010-plan.md` explicitly in the review boundary.
Record every snapshot exclusion using the **same repository-relative path names** as the comparison;
never leave out files silently. Only task metadata and that exact committed local plan may be excluded.
If the snapshot omitted other files, restore them for comparison or obtain fresh local review; never
exclude a shipped change to manufacture equality. Equal patches and a clean apply are insufficient:
changed base content, conflict resolutions or later shipped edits require fresh review of the local result.

Preserve the source comment, reviewed head, provider/model and comparison evidence. Convert a verdict
comment to the helper's inspection JSON schema before recording it against the local snapshot:

```json
{"verdict":"APPROVED","reviewer":"claude","coverage":["Shipped tree at pinned PR_HEAD equals LOCAL_HEAD; exact exclusions and comparison evidence attached"],"findings":[],"limitations":[]}
```

Use the actual native reviewer and truthful coverage/limitations, then `inspect --reviewer PROVIDER
--report REPORT.json`. Coordinator conflict resolutions and reviewer fix commits are new authorship:
declare their real models and obtain reciprocal inspection if both native providers built. Finally review
the combined batch under [delivery.md#integration-review](delivery.md#integration-review).

## Router-backed bounded work while both native providers are unavailable

The owner reports an OpenRouter (paid) key and a local freellmapi router (`127.0.0.1:3001`, free tiers; OmniRoute was removed 2026-11-01). Availability is model-specific and changes; free tiers are rate limited. Check the router answers and list its live models before each batch; pin the exact model id (never `auto`) and record it in the task result. freellmapi carries public / non-sensitive work only; OpenRouter direct may carry private code only where the provider terms allow ([backends.md](backends.md#data-boundary)).

Use only pre-approved, self-contained pending task specs with bounded low-risk scope. Run one task at a time in a fresh branch/worktree, honor repository locks and data-sensitivity policy, save diff + model/proof metadata, and stop with a handoff when limits or uncertainty arise. Never let the backend approve its own plan, count as independent review, commit/merge, alter production data, or claim acceptance. When both native providers are absent, work may prepare isolated changes and evidence; it must remain unmerged until a native Claude/Codex reviewer and coordinator proof/approval are available. The label is `claude@openrouter`, `codex@freellmapi` and so on, according to the actual harness and router, never native `claude`/`codex`. When only one native provider is absent, prefer single-provider mode ([delivery.md](delivery.md#single-provider-mode)) over backend building for anything risky.

Router routing is UNVERIFIED until a live probe passes; no key values belong in a task spec or log.
