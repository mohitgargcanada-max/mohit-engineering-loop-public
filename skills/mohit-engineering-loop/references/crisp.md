# Optional CRISP integration

Use the existing CRISP installation; do not vendor its code or require it for standalone
operation. Probe TEA CLI/MCP, compression tools, rollover settings and receipts per
host. Installation, configured hooks and hooks actually firing are separate facts.

Recall only a few relevant durable facts. Prefer scoped graph queries and compact
reads when available. Reuse verified TEA command wrapping and receipts; preserve
exact errors, paths, IDs, exit status and acceptance evidence. Do not fabricate savings.
Keep telemetry separate from durable decisions and private memory out of public Git.
Respect the host's memory consent rules; never publish or prune private memory by default.

Both providers use the canonical `.mel/<task>/state.json` for task revisions and
`.crisp/HANDOVER.md` for concise shared pointers. Git/PR state is re-read from Git
and GitHub, not inferred from a stale handover. Retain `.crisp/BUGS.md` and
`.crisp/MISTAKES.md` when the target project uses them. Do not create a second memory
vault, PR database or duplicate policy constants. The original skill owns task-state
semantics; CRISP owns its own integration configuration.

Carry a small self-contained context packet between agents: task/transfer IDs,
state revision, objective, scope, constraints, relevant files, accepted decisions,
proof and pending work. Tools, hooks, auth, chats and MCP never transfer automatically.
Read-only external review may disable all customizations/MCP; keep that boundary,
prepare needed evidence beforehand and disclose unavailable CRISP components.

Choose parallelism from this task's actual dependencies/resources and total overhead;
optional orchestration advice cannot override the user's reliability/cost constraints.
Private diagnostic artifacts stay local; commit sanitized evidence summaries and
hashes only. Verify task/helper behavior even when CRISP is absent.
