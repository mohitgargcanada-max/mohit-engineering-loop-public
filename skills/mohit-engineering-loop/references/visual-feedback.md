# Agentation visual feedback

Use for user-selected page elements or regions and actionable UI feedback. Keep
Agentation separate from Engineering Loop and UI/UX design guidance. Follow the
installed Agentation skill for setup; enable the toolbar only in development or an
explicit isolated preview. Preserve its upstream license and notices.

## Recipient and submission

Before consuming feedback, state the page/session, active coordinator and receiving
agent. Respect the user's selected recipient; otherwise default to the current
coordinator. Agentation does not choose Codex versus Claude. A toolbar endpoint
selects a server, not a provider identity; one assigned agent owns each batch.
Use separate endpoints for separate recipients, or an explicit handoff before a
second agent consumes a shared session. Do not run competing watchers.

Local setup: Claude's user-scoped `agentation` MCP server uses localhost:4749.
The earlier isolated Codex demo used localhost:4747; this is not a permanent Codex
MCP registration. Check actual MCP configuration and listening endpoints each time.
Connect the toolbar to the selected recipient's exact endpoint. Do not claim a
Send-to-Codex/Claude selector exists unless it was implemented and verified.

Ctrl+click or drag can select multiple elements. Distinguish saving an annotation,
submitting a batch with Send Annotations when available, and the agent reading it.
If Send is not exposed by that version/mode, use explicit user submission wording
and a pending-annotation read; do not claim an absent button was installed.
Read only the assigned session/page and submitted batch. Do not execute unrelated
pending annotations. Watch mode is optional and must be explicitly requested.

## Delivery and completion

Verify one uniquely labeled browser-created annotation through the real MCP tools:
check its exact text, target selector and page URL. Toolbar visibility, connection
badges and doctor health alone are insufficient. Each provider must prove its own
connection; a standalone MCP client does not prove Claude loaded its configuration.

Carry annotation IDs, page/session, requested outcome and recipient into the existing
task work order. Acknowledge the assigned feedback, make only authorized changes,
verify in the browser, and resolve the annotation with the proof. Keep unresolved
feedback pending with its reason. Submission does not grant merge/deploy permission.
Use the existing independent reviewer when the engineering task requires it;
Agentation annotations do not replace that review.
