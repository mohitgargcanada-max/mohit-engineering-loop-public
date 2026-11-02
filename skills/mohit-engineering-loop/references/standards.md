# Engineering standards

These defaults apply to every project unless its own AGENTS.md/CLAUDE.md says otherwise; the project
file wins. Model names are dated starting points (October 2026): check what the account can actually
run, and record requested and observed identity separately. No price or ranking claim without a
current official source.

Listed is not runnable. Observed 2026-10-24: the npm Codex CLI 0.153.4 on PATH refused `gpt-6.1-sol`
for a ChatGPT account (HTTP 400 `model_not_found`) while the Codex app's bundled CLI 0.163.0-alpha ran
it. Check the exact binary and a failing exit code before concluding a model is unavailable, and never
count a call with an error in its stderr as a review.

**Spend rule.** Senior models (Opus, Sol at high effort, Fable, Astra) for planning, plan review, final
inspection, evals and risky building. Everything well specified or mechanical goes to the cheapest model
that can do it with checks (Sonnet, Sol at medium, Haiku, Luna, a pinned router model), and a senior native model
reviews the result.

## Who decides

- **Coordinator** (the real host session) owns the plan, allocates roles, decides the builder, arbitrates
  findings and keeps the user's scope. Default: Claude Opus 5.5 in Claude Code, GPT-6.1 Sol (high effort)
  in Codex. These two are the decision makers and senior reviewers.
- **The plan reviewer may challenge the allocation** as a finding, like any other part of the plan.
- **The user overrides** any allocation, model pin or standard.
- One decision, one owner: the coordinator records it in the plan; disagreement gets one evidence-backed
  counter, then the coordinator decides. Irreversible, security-sensitive or costly decisions go to the user.

## Choosing the builder

Answer in the plan, in this order:

1. **Can the brief be written without carrying the discovery?** If finding the fix *is* the work
   (root cause unclear, premise needs testing), the coordinator builds it. Otherwise delegate.
2. **Risk.** Security, auth, secrets, data loss, money, migrations, concurrency or anything hard to
   reverse: a native Claude or Codex builder at senior tier only, never a backend model.
3. **Capacity.** Prefer the provider with weekly headroom; see the fallback ladder.
4. **Ownership.** One writer per set of files. Parallel builders only on disjoint files.

## Models by role (defaults)

| Role | Default | Escalate to | Not allowed |
|---|---|---|---|
| Coordinator / architect | Opus 5.5 or GPT-6.1 Sol high | Fable 5.1 / GPT-6 Astra for ambiguous, high-stakes design | Backend (router) models |
| Plan reviewer | The other native provider: Sol high reviews Claude plans, Opus 5.5 reviews Codex plans | Astra / Fable | The plan's author provider (`plan_author`, set by `init`/`revise-plan --plan-author`; legacy state falls back to the coordinator), so a coordinator may review an adopted plan written by the other native provider; backend models |
| Builder, well-specified brief | GPT-6.1 Sol medium or Claude Sonnet 5.5 | Opus / Sol high when the brief proves incomplete | - |
| Builder, narrow mechanical work (fixtures, docs, renames, test scaffolds) | GPT-6 Luna, Claude Haiku 5.5 or a pinned router model | - | Risky work (above) on a backend model |
| Final inspector | The other native provider of each builder: Opus 5.5 or Sol high | Fable / Astra for security or irreversible changes | The builder's own provider; backend models |
| Inspector of backend-built work | Opus 5.5 or Sol high | Fable / Astra for security or irreversible changes | Another backend model |
| Plan reviewer, single-provider mode | The available provider as a fresh session on a different model than the plan model (Fable / Opus reviews a Sonnet plan; Astra / Sol reviews a Luna plan) | A same-model fresh session only with `--same-model` and the user's approval | A session that built or planned; a backend model |
| Final inspector, single-provider mode | The available provider as a fresh session on a different model than every builder model (Fable / Opus inspects Sonnet work) | As above | The builder session; the unavailable provider; a backend model |

Enforced by the helper: reviewers of plans and inspections must be native `claude` or `codex`, and
`ready` needs, per builder, a review by the other native provider (native builder) or by any native
provider (backend builder). Not enforced: the risk limits on what a backend model may build; the
coordinator and inspector apply them.

## Fallback ladder (pre-authorized, never silent)

1. Native provider with headroom (Claude <-> Codex swap roles: the other one builds, the original
   inspects later).
2. Router backend (`claude@openrouter` / `claude@freellmapi`, `codex@...` likewise) for bounded low-risk building only, on the
   $0-first provider routes in [backends.md](backends.md#fallback-providers-0-first).
3. Pause with a checkpoint.

- Approve the ladder per project once (in the plan or project instructions). Every step down is
  logged in the task state (handoff with a `--capacity` note, or a takeover with a reason).
- Watch both the 5-hour and the weekly window before each dispatch with `scripts/capacity.py`; the
  thresholds are yours to set ([capacity.md](capacity.md)). Record the decision in the handoff.
- Work done lower on the ladder is not ready until a native review covers it. Reviews never move to a
  backend model.

## Parallel work across Claude, Codex and backends

Running pieces at the same time on different providers adds throughput and spreads load over separate
limits. It is worth it only when the pieces are truly independent.

- **Split by files, not by role.** Each piece is its own task with a disjoint `--scope`, its own branch or
  worktree and its own criteria. Two writers never touch the same files.
- **Pick the provider per piece** by the builder rules above and by headroom from `capacity.py`; a backend
  model only for low-risk pieces.
- **Two agents at a time** by default; raise it only when the user does and the machine has the memory.
- **Every piece gets its own native review** under the usual rules; the coordinator integrates the pieces,
  reruns the whole suite on the combined result, and that combination gets a final inspection too.
- **`show --who` per task** shows who touched what; any overlap between pieces is a planning error to fix
  before merging, not something to resolve by "keeping both".

## Coding standards

- Read the existing code first; match its naming, structure, comment density and idiom.
- Smallest working change: reuse, stdlib, platform, then a dependency only with a reason.
- No speculative abstractions, flags or configurability. Mark deliberate shortcuts with the reason and
  the condition for removing them.
- Secrets only from the project's secret store or environment, never in code, logs or prompts.
- Every behavior change ships with a test that fails without it; fix a bug with a regression first.
- Test expectations come from a literal, worked example or the spec, never from the code under test; test
  through the public interface ([discipline.md](discipline.md)).
- Errors are explicit: no silent success, no empty input treated as measured input.

## Architecture standards

- State scale assumptions and the expensive-to-reverse choices in the plan.
- Data contracts and failure behavior are written down before the code that depends on them.
- Prefer existing components over new services; a new store, queue or process needs a stated reason.
- Long or heavy work runs off the request path; caches are keyed and invalidated explicitly.
- Record an ADR only for a non-obvious, hard-to-reverse trade-off.

## Design (UI/UX) standards

- Follow the project's existing design system and tokens; no new palette or font without approval.
- Check real rendering (headless browser or screenshot), not just that markup parses.
- Accessible by default: contrast, keyboard reach, labels; responsive at phone width.

## Review standards

- Severity: **high** = wrong result, data loss, security hole, broken gate; **medium** = real defect with
  a workaround or limited reach; **low** = drift, clarity, missing test for an edge.
- Every finding cites file:line and the evidence (command, output, quoted code). Opinions without
  evidence are suggestions, not findings.
- Read the body, not the docstring; an absence claim needs a positive control found the same way.
- A review lists what it actually covered and what it did not.
- Approval means no unresolved material defect, bound to the exact plan or snapshot. A new edit
  invalidates it.
- Approvals of separate pieces do not approve their combination: stacked or separately merged tasks get an
  integration review of the combined head, by both providers when both contributed
  ([delivery.md](delivery.md#integration-review)).

Canonical model ids for single-provider comparison (the helper lowercases and reads `.` as `-`, nothing more): `claude-fable-5-1`, `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5`, `gpt-6-2-astra`, `gpt-6-1-sol`, `gpt-6-luna`. A different spelling of one model (an alias, a date suffix) is not detected; write the id you ran.

## Changing a standard

A project may tighten or relax a default in its own instructions. Changing this file is a task of its
own: proposed by a coordinator, reviewed by the other native provider, approved by the user.

## Product and decision-support design standards

Apply these standards to every project and adapt the language, evidence and interaction model to that project's actual users and domain. The project's own instructions may add domain-specific requirements; do not copy one project's persona or terminology into another.

- Start from the target user's task, knowledge level and next decision or action. State the problem the screen solves and the observable success criteria before arranging components. Organize the page around the user's mental model and information priority, not around the order in which fields or backend modules happen to exist.
- For research and analytical products, make the reasoning legible: takeaway, supporting evidence, substantive counterevidence or limitations, then next observable check. If no counterevidence is found, state what was checked; an empty heading or generic caveat is not evidence.
- Keep primary tables focused on the columns needed for the user's task. Preserve useful depth and make supporting detail accessible in a clearly labeled drill-down; avoid exposing internal IDs, diagnostics or raw payload fields as primary content unless the user needs them to act.
- Use a visualization only when it makes a real relationship, comparison or change easier to understand. Ground it in actual data, label relevant units/timeframe/basis, expose stale or missing inputs, and explain what it does and does not show. Never present placeholders as live information or add decorative charts to satisfy a screen count.
- Before sign-off, explain one real user journey and trace one populated example through the applicable source, transformation/calculation, payload and rendered output. Explain the purpose of every primary table column or visual encoding; label unverified links as unknown rather than implying correctness.
- Inspect actual populated and sparse/error states at desktop and phone widths. Judge task completion, content hierarchy, relevance, readability, duplicate information, interaction and accessibility at each width, not just layout reflow. A route loading or valid markup is not product or visual acceptance.
