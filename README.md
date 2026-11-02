# Mohit Engineering Loop

A skill for Claude Code and OpenAI Codex that runs a software task the way a careful team would: one agent
plans, a different provider reviews the plan, someone builds, the other provider inspects the result, and
nothing is called done until the evidence says so. It also keeps work moving when a usage limit hits, and
records which model built what, so models that keep making mistakes stop being given the work.

By **Mohit Garg**. Inspired by Chase AI's Claudex Loop; see [ATTRIBUTION.md](ATTRIBUTION.md) for everyone
whose work shaped it.

## Where it started, and what was added

The starting point is **Chase AI's [Claudex Loop](https://github.com/chaseai-yt/claudex-loop)**: have Claude and
Codex review each other, with one provider reviewing the plan and the other inspecting the finished work. Full
credit for that idea belongs to Chase AI. This repository is an independent re-implementation, not an official
Claudex release. No Claudex code, text or artwork is copied here.

On top of that idea, this project added:

| Area | What was added or changed | Task |
|---|---|---|
| State you can trust | A helper (`scripts/task_state.py`, standard library only) that keeps each task's state in the repo with revision checks, a lock and atomic writes, so two agents cannot overwrite each other | MEL-001, MEL-002 |
| Handoffs | Numbered, acknowledged handoffs between Claude and Codex; user-approved takeover; local delivery for repos without GitHub, with an exact-branch merge check | MEL-002 |
| Who built what | An authorship ledger built from the actual Git trees, scope globs, and a declaration gate: no state change while undeclared code is present | MEL-003 |
| Mistakes have consequences | Confirmed findings go on the responsible model's record; a model with repeat findings is benched as a builder until the user overrides | MEL-003 |
| Bounded effort | Review-round budgets, rubric-based evaluations for high-risk work, and a usage check (`scripts/capacity.py`) before dispatch | MEL-003 |
| Combined result | An integration review of stacked or separately merged tasks, because separate reviews miss what only shows when changes land together | MEL-004, MEL-006 |
| Limits without stalling | Unattended operation: a queue runner for Codex while Claude is out, cloud sessions, a router fallback ladder (OpenRouter, freellmapi) | MEL-005, MEL-006 |
| Plan ownership | The plan author is recorded and plan approval checks against it, not against whoever happens to own the task | MEL-007 |
| One provider only | **Single-provider mode**: when Claude or Codex is unavailable, the user can approve finishing with the other. A fresh session on a different model reviews, with a required adversarial section; the unavailable provider is refused, and the task is labelled `SINGLE-PROVIDER REVIEW` so it is never mistaken for cross-provider review | MEL-009 |
| Better plans | Ideas borrowed from [github/spec-kit](https://github.com/github/spec-kit), rewritten: `[NEEDS CLARIFICATION` markers block plan approval; criteria without a proof line are flagged; lean-design gates in the plan template | MEL-009 |

Each task was planned, reviewed and inspected with the skill itself. The scope and plan of each are in
[docs/tasks](docs/tasks); `docs/VALIDATION.md` records how each was verified.

## The problems it solves

| Problem | What the skill does |
|---|---|
| One model reviewing its own work | The builder can never approve itself; Claude's work is inspected by Codex and the reverse |
| Weekly or 5-hour limits stop work for days | A fallback ladder (other provider, then a pinned router model (OpenRouter, freellmapi), then a checkpointed pause; or single-provider mode when the user approves) and a usage check before every dispatch |
| Agents drift off the plan | Accepted criteria with IDs, a declared file scope, review rounds against a budget |
| "Done" claimed without proof | Readiness needs every criterion passed with a hashed proof file and a fresh independent inspection |
| Nobody knows which model touched what | Every code change is credited to a builder and a model, with the files it changed |
| The same model keeps making the same mistakes | Confirmed findings go on that model's record; repeat offenders are benched as builders |
| Work lost when a session dies | Numbered, hashed handoffs; a user-approved takeover; every agent resumes from disk |
| Long contexts burn tokens | A compact resume packet instead of replaying history; pointers, not pastes |

## How a task flows

```
 plan (coordinator)  ->  plan review (other provider)  ->  build (chosen builder)
        ^                     | REVISE                          |
        +---------------------+                                 v
                               final inspection (provider that did not build it)
                                       | REVISE -> fix -> fresh inspection
                                       v
                       ready (all criteria + proof + inspection)  ->  merge (user's go)
```

- **Coordinator**: the session you are talking to. Plans, picks the builder, arbitrates findings. Default
  decision makers are Claude Opus and GPT Sol (see [standards](skills/mohit-engineering-loop/references/standards.md)).
- **Builder**: the coordinator itself for discovery-heavy work; a cheaper model for well-specified pieces;
  a pinned router model only for low-risk work.
- **Reviewer / inspector**: always native Claude or Codex, never a backend model. Work built by a native
  provider is inspected by the other native provider; work built through a backend (`claude@openrouter`) may
  be inspected by either native provider.
- **Integration review**: when tasks are stacked or merged separately, the combined result is reviewed
  again as a whole, by both providers if both contributed
  ([delivery](skills/mohit-engineering-loop/references/delivery.md#integration-review)).

## What is enforced vs what is guidance

The state helper (`scripts/task_state.py`, Python stdlib only) **enforces**:
- revision checks, an exclusive lock and atomic writes on the task state;
- a code change must be credited (`--builder` and `--model`) before anything else is recorded;
- path scope, review-round budget, plan approval or a recorded user waiver before implementation;
- readiness: every criterion passed with unchanged proof, a fresh inspection per builder (a native builder by
  the other native provider, a backend builder by any native one), and for high-risk tasks a rubric eval
  against the rubric recorded in the plan, with no unresolved failed eval on the same snapshot;
- adopted work (`init --base` or a dirty working copy) names its authors, or counts as built by both;
- merge recorded only after GitHub (or, without a remote, the local base branch) confirms it.

It does **not** verify who an agent really is: identities, reviewer reports and user approvals are
declared by the caller. It is a discipline tool for honest agents, not a security boundary.
Everything else (which model to pick, when to hand off, how to review) is guidance in the
[references](skills/mohit-engineering-loop/references).

## Install

Copy `skills/mohit-engineering-loop/` into `~/.claude/skills/` (Claude Code) and/or `~/.agents/skills/`
(Codex), then start a new session and ask for `/mohit-engineering-loop` (Claude Code) or
`$mohit-engineering-loop` (Codex). Needs Python 3.8+ and Git; the GitHub CLI for PR workflows. Each model CLI
must be installed and signed in on its own. Router backends are optional.

## A task in commands

```text
H=<absolute path>/skills/mohit-engineering-loop/scripts/task_state.py
# In the task's own worktree, with the plan file committed. Each command prints the new revision.
python $H init   --repo WT --task MEL-010 --owner claude --plan PLAN.md --criterion A1 --scope "src/*"
python $H approve-plan --repo WT --task MEL-010 --expected 1 --actor claude --reviewer codex --report PLAN_REVIEW.json
python $H update --repo WT --task MEL-010 --expected 2 --actor claude --status implementing --pr https://github.com/OWNER/REPO/pull/N
#   ... the builder implements and commits; you run the tests and keep their log as proof ...
python $H update --repo WT --task MEL-010 --expected 3 --actor claude --builder codex --model gpt-6.1-sol --pass A1 --proof TESTS.log
python $H inspect --repo WT --task MEL-010 --expected 4 --actor claude --reviewer claude --report CLAUDE_INSPECTION.json
python $H inspect --repo WT --task MEL-010 --expected 5 --actor claude --reviewer codex --report CODEX_INSPECTION.json
python $H ready  --repo WT --task MEL-010 --expected 6 --actor claude
python $H show   --repo WT --task MEL-010 --brief      # compact resume packet; also --who, --roster
python <path>/scripts/capacity.py --claude CLAUDE_USAGE.json   # 5-hour and weekly windows -> go / pause
```

- The owner counts as a builder too (unless `init` adopted existing work, which names its own authors), so
  here each builder (claude, codex) needs the other provider's inspection. Pass every criterion before recording inspections: any later update clears them.
- No GitHub remote? Use `init --local-target BASE` (an existing branch) instead of `--pr`.

Details: [delivery](skills/mohit-engineering-loop/references/delivery.md),
[handoffs](skills/mohit-engineering-loop/references/handoffs.md),
[capacity](skills/mohit-engineering-loop/references/capacity.md),
[unattended queue and cloud work](skills/mohit-engineering-loop/references/unattended.md),
[backends (OpenRouter, freellmapi)](skills/mohit-engineering-loop/references/backends.md),
[discipline](skills/mohit-engineering-loop/references/discipline.md),
[context and caching](skills/mohit-engineering-loop/references/context.md),
[CRISP integration](skills/mohit-engineering-loop/references/crisp.md).

## Repository layout

This public copy is published as a single commit. Development happens in a private repository, so commit
hashes and pull-request numbers mentioned in `docs/` and `.crisp/` refer to that history.

| Path | What |
|---|---|
| `skills/mohit-engineering-loop/SKILL.md` | The skill the agent reads |
| `skills/mohit-engineering-loop/references/` | Delivery, handoffs, standards, discipline, capacity, unattended queue/cloud work, context, backends, CRISP |
| `skills/mohit-engineering-loop/scripts/` | `task_state.py` (state helper), `capacity.py` (usage windows) |
| `tests/` | Behaviour tests in disposable Git repos; no model calls |
| `docs/tasks/` | Each task's scope and plan (MEL-001 to MEL-009) |
| `.mel/` (git-ignored) | Where the helper keeps task state, handoffs and review reports inside your own repo; this repo's own records are not published |
| `docs/VALIDATION.md` | What was verified for each task |

Task scope / plan: [MEL-001](docs/tasks/MEL-001.md) / [plan](docs/tasks/MEL-001-plan.md),
[MEL-002](docs/tasks/MEL-002.md) / [plan](docs/tasks/MEL-002-plan.md),
[MEL-003](docs/tasks/MEL-003.md) / [plan](docs/tasks/MEL-003-plan.md),
[MEL-004](docs/tasks/MEL-004.md) / [plan](docs/tasks/MEL-004-plan.md),
[MEL-005](docs/tasks/MEL-005.md) / [plan](docs/tasks/MEL-005-plan.md),
[MEL-006](docs/tasks/MEL-006.md) / [plan](docs/tasks/MEL-006-plan.md) (integration-review fixes),
[MEL-007](docs/tasks/MEL-007.md) / [plan](docs/tasks/MEL-007-plan.md) (plan author, not coordinator, decides who may approve a plan),
[MEL-008](docs/tasks/MEL-008.md) / [plan](docs/tasks/MEL-008-plan.md) (installed-skill edits brought into the repository),
[MEL-009](docs/tasks/MEL-009.md) / [plan](docs/tasks/MEL-009-plan.md) (single-provider mode, plan-quality gates, router backends, project fit).

## Verify

```text
python -B -m unittest discover -s tests -v
python -B scripts/validate.py
```

## Status

v0.5. MEL-009 adds a user-approved single-provider mode (the available provider reviews as a fresh, adversarial session on a different model, always labelled `SINGLE-PROVIDER REVIEW`), plan-quality gates, and OpenRouter / freellmapi in place of OmniRoute. v0.4: MEL-004 fixed what a first integration review of the merged v0.3 found (Codex and Claude, I1-I12),
added the integration-review rule and $0-first fallback-provider guidance. Earlier: MEL-001 (initial
skill), MEL-002 (review fixes, OmniRoute fallback, takeover, local delivery, standards), MEL-003 (attribution,
scope guard, model roster, evals, budgets, capacity). MEL-001 was built by Codex while Claude was out of quota; its own Claude plan
review and final inspection were deferred by Mohit, and a later read-only Claude review of it produced
the fixes in MEL-002. MEL-002 and MEL-003 each had a Codex plan review and Codex final inspection of
Claude's work; in MEL-003 Codex also fixed its own findings and Claude inspected that fix.
MEL-005 added unattended Codex queue and cloud-session guidance while Claude is exhausted, including
proof and independent-review requirements. MEL-006 fixed what the combined integration review of MEL-004 and MEL-005 found. MEL-007 records the plan author so plan approval comes from the other provider after handoffs. Details: [docs/VALIDATION.md](docs/VALIDATION.md).

## Licence and credit

MIT, copyright Mohit Garg. Credits and third-party terms: [ATTRIBUTION.md](ATTRIBUTION.md).
