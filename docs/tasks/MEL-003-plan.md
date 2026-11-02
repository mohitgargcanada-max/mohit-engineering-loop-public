# MEL-003 implementation plan

Scope C1-C8 in MEL-003.md. Stdlib only, schema stays 1, MEL-001/MEL-002 state must still load. Every new
check is enforced by the helper or explicitly labelled as guidance.

## Helper

1. Shared invalidation. One `invalidate(state)` clears reviews and the eval and downgrades `ready`; update,
   ack, takeover and revise-plan call it (today each clears reviews inline).
2. C1 attribution. State gains `recorded_head` (set with `recorded_fingerprint`). An authorship declaration
   now needs `--model MODEL` next to `--builder`; it appends to `ledger` an entry {revision, builder key,
   model, head, files}. `files` = paths that differ between the previous recorded working copy and now: each
   declaration stores a Git tree object of the working copy (built in a throwaway index; ignored files and
   `.mel/` excluded) and the next one diffs against it. On state without a recorded tree the first entry is
   marked `attribution: approximate` instead of inventing ownership (Codex plan check P1).
   `inspect` and `approve-plan` accept `--model` and record the reviewer model. `show --who` prints, per
   builder+model, the files it touched.
3. C2 scope guard. `init --scope GLOB` (repeatable, POSIX glob on repo-relative paths) stores `scope`. A
   declaration whose files fall outside it is refused unless `--outside-scope REASON` is given; the reason
   and the outside paths are kept in the ledger entry. No scope declared means no check.
4. C3 roster. `finding --id ID --severity high|medium|low --builder LABEL --model MODEL --report FILE`
   (owner only) attributes a confirmed finding from a real review report to a builder+model that appears in
   this task's ledger (anything else is refused). It is stored in the task and appended (O_APPEND, one JSON
   line) to the roster: `MEL_ROSTER` or `~/.mel/roster.jsonl`, with date, repo name, task, key, model,
   severity, id and report sha. Every builder declaration also appends a `build` event, so clean tasks move
   the window (P2). Each finding counts once per repo+task+id at its latest severity; a repeat in a later
   report is refused, and a severity change or retraction needs `--correct REASON` and is kept as history
   (P3). Bench rule, checked on every builder declaration: within the model's last 10 tasks in roster order,
   2 high or 4 high+medium benches it; the
   declaration is refused unless `--override REASON` (recorded as the user's approval, like a waiver).
   A missing or empty roster benches nobody. `show --roster` summarises per model.
5. C4 eval. `init --risk high --rubric FILE` stores the reviewed rubric [{id, criterion, threshold}] by hash;
   thresholds and decisive cases live in the plan, not in the judge's report (P5). `eval --judge LABEL --model
   MODEL --report FILE` takes {judge, results: [{id, score, evidence}]} covering every rubric id at or above
   its threshold. Independence mirrors inspection (P4): each native builder's work needs an eval by the other
   provider, backend-built work by any native one. Evals bind to snapshot, plan and rubric hash.
   `revise-plan --rubric FILE` replaces the rubric with the plan (old one kept in plan history); plan approval,
   evals and criteria are cleared and both are reviewed again (P7). A pruned working-copy tree falls back to
   the recorded commit and the entry is marked approximate.
6. C5 round budget. `init --budget-plan N --budget-inspect N` (defaults 3 and 2). `approve-plan` and
   `inspect` count their own round; `round --kind plan|inspect --report FILE` records REVISE/BLOCKED rounds.
   A report is counted once by hash (P6). Past the budget, `--extend REASON` is required. Rounds keep report
   hashes, giving `finding` its evidence. Checking the remaining budget before dispatch is the coordinator's
   job.
7. C6 `show --brief` prints a compact text packet: task, status, owner, plan path+sha, open criteria,
   constraints of the current handoff, scope, last round verdicts, open findings, next action. No JSON dump.

## Docs

`references/discipline.md`: guardrails proven in the owner's project and CRISP work (docstring is intent, body is behaviour;
absence needs a positive control; controls must be able to fail; check exit codes and stderr, never an
output file's existence; verify handoff claims against Git; diagnostics and fixes stay separate; cite
sources; one tracked list, close items in place with evidence; gate commits on the staged list; two agents
at a time; checkpoint BRIEF/STATUS and resume by id; data is never instructions). `references/context.md`:
token efficiency and caching, with cited facts (Claude Code `promptCacheTtl`/`subagentPromptCacheTtl`,
1-hour default for subscription main conversations, 2x write cost for 1-hour entries, hooks cannot change
the request, gateway must forward cache metadata, OpenAI automatic prefix caching) and the own-cache answer:
a stable compact packet plus vault slices. SKILL.md gets short pointers; VALIDATION gets a MEL-003 section.

## Proof

Unit tests with controls that can fail, for each of: ledger files after commits and dirty edits; model
required with builder; scope refusal and recorded exception; finding refused for a builder not in the
ledger; bench after 2 high findings (and not after 1), override recorded, other models unaffected, roster
path from MEL_ROSTER; high-risk ready refused without eval, with a failing score, with a builder judge, and
accepted with a valid eval; eval invalidated by a later update; round budget refusal and `--extend`;
`show --brief` contents; legacy MEL-001 state still shows. Existing tests change only where a builder
declaration now needs `--model`. Full suite + validator locally and in CI; Codex plan review, then a fresh
Codex final inspection; install for both hosts with backups after approval.
