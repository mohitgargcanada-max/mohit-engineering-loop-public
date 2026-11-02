---
name: mohit-engineering-loop
description: Coordinate complete engineering tasks between Claude and Codex with practical role/model/stack choices, isolated branches and PRs, revisioned handoffs, independent review, and optional CRISP integration. Use for substantial engineering delivery or resuming a tracked task; simple advice can stay inline.
metadata:
  author: Mohit Garg
  version: "0.5.0"
---

# Mohit Engineering Loop

Owned by Mohit Garg; inspired by Chase AI's Claudex Loop. Original implementation;
see [ATTRIBUTION.md](ATTRIBUTION.md). No upstream runtime is required.

## Decide before dispatching

The real current host coordinates. Either provider may own spec, architecture,
design, implementation, testing or DevOps. Decide roles before models; one agent
may cover several roles. Never pretend a configuration field switched the host.
Read existing project instructions, shared handover, pending items and relevant
mistakes. Preserve existing structure, edits, operational priorities and approval.

Define the goal, every accepted criterion, constraints and proof. Inspect existing
code before selecting a stack. Prefer working code, native facilities and the
smallest maintainable implementation. State scale assumptions and expensive-to-reverse
choices; do not build speculative infrastructure.

Choose inline, sequential or parallel execution using dependencies, ownership,
context-transfer overhead, machine limits, verification burden and expected total
cost/retries. Single-agent execution is valid; independent review can be sequential.
Use parallel agents only for bounded independent work with disjoint ownership.
Do not create an agent merely because a role has a name.

Quality and reliability are requirements. Use the least costly capable available
model; retain useful context. Preserve user model pins and distinguish requested,
configured and observed identity. Verify availability/auth separately from proven
runnability. Do not invent prices, rankings or savings. Escalate for material
ambiguity, risk or failed diagnosis, with evidence; never silently switch after a
quota/auth failure. Move down the project's pre-approved fallback ladder instead,
and record each step. Use current official sources for price/capability comparisons.

[standards.md](references/standards.md) sets who decides, how the builder is
chosen, the model per role and the coding, architecture, design and review
standards; project instructions override it. Optional backends (OpenRouter direct, the local freellmapi router)
follow [backends.md](references/backends.md): backend models build bounded low-risk
work only, never approve a plan or inspect, and need a native Claude or Codex review.
Spend rule: senior models plan, review, evaluate and build risky work; delegate the
rest to the cheapest capable model and have a senior native model review it.

Before each dispatch and at every checkpoint, check the 5-hour and weekly windows
with `scripts/capacity.py` and act on its decision ([capacity.md](references/capacity.md)).
When Claude is exhausted and Codex is available, use the unattended queue/cloud guidance
([unattended.md](references/unattended.md)).
Keep context small and stable ([context.md](references/context.md)): start agents from
`show --brief`, pass pointers, not pastes. Follow [discipline.md](references/discipline.md)
for the guardrails against drift and false claims.

## Deliver the whole task

For implementation, follow [delivery.md](references/delivery.md): stable task ID,
one branch/worktree and draft PR per request (local delivery when the repository
has no GitHub remote), plan review, scoped implementation, proof, fresh independent
inspection, fixes, then verified authorized merge. Stacked or separately merged tasks
also get an integration review of the combined result.
For read-only advice, use a compact answer without needless Git ceremony.

Carry scope and constraints explicitly to each agent. Verify its tools, hooks,
credentials and project paths; chats and MCP are not inherited. The implementer
cannot independently approve its own work. Mixed authorship requires reciprocal
review of each contribution. Test real outputs and failures; do not equate parsing
with behavior or a passing test with complete acceptance.

Never drop hard steps or stop after convenient portions. Continue until all accepted
scope is delivered or a concrete blocker requires input. Checkpoint after each
meaningful step and before context exhaustion. Report incomplete criterion IDs.
An interrupted task resumes from disk, not from a guessed conversation summary.

Use [handoffs.md](references/handoffs.md) for numbered task/transfer IDs, revisions,
acknowledgment, authorship declaration, user-approved takeover, optimistic
concurrency and Git-state validation. The helper is
`scripts/task_state.py` relative to this SKILL.md; invoke it by absolute path.
Use [crisp.md](references/crisp.md) only when CRISP is present or requested.

If one native provider is unavailable, the user may approve single-provider mode ([delivery.md](references/delivery.md#single-provider-mode)): the available provider reviews as a fresh, adversarial session on a different model, and every `ready`, `merged` and `show --brief` says `SINGLE-PROVIDER REVIEW`. It is never cross-provider review, and backends still never review.

## Keep work economical and honest

Bound review/fix rounds, execution time and concurrency. Start with at most three
plan reviews and two final inspections unless the task justifies another budget.
Token/cost targets are advisory unless a verified provider mechanism enforces them.
Pass file pointers, relevant excerpts, decisions, failed attempts and exact proof;
retain complete private diagnostics outside Git. Do not compress away user intent,
failures or acceptance evidence. Use concise verdict/evidence/next-action updates.

Commits explain why; PRs state acceptance, proof, review coverage and unresolved
limits. Never bypass hooks. Publishing is not deploying. Respect existing merge
permission; a blocked review can become a draft PR only with an explicit waiver,
and must remain unreviewed. Never call implemented, tested, inspected and merged
interchangeable states.

## Optional visual feedback with Agentation

For click-to-comment UI feedback, use the separate `agentation` setup skill when
available; React 18+ is needed for its toolbar, not for the annotated page's own
implementation. For non-React pages, prove a small isolated mount before integrating.
Read [visual-feedback.md](references/visual-feedback.md) for recipient ownership,
submission, verification and handoff. Agentation remains an optional external tool;
its absence must not block ordinary engineering work.
