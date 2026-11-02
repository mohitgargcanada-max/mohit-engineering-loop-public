# Context, tokens and caching

Facts here were checked against official docs on 2026-10-24; re-check before relying on numbers.

## Prompt caching (provider side)

- Anthropic caches a prompt prefix for 5 minutes by default or 1 hour on request. Writing a 1-hour entry costs
  2x base input and a 5-minute one 1.25x; reading costs about 0.1x (0.05x on Opus 5.5 and Sonnet 5.5;
  check the page for your model)
  ([prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)).
- Claude Code chooses the TTL itself. Documented controls: `promptCacheTtl` / `subagentPromptCacheTtl`
  settings (`5m` or `1h`), `CLAUDE_CODE_PROMPT_CACHE_TTL`, `CLAUDE_CODE_SUBAGENT_PROMPT_CACHE_TTL`,
  `ENABLE_PROMPT_CACHING_1H`, `FORCE_PROMPT_CACHING_5M`. On a subscription within plan limits the main
  conversation already gets 1 hour; subagents get 5 minutes; API-key use and overage get 5 minutes
  ([Claude Code prompt caching](https://code.claude.com/docs/en/prompt-caching),
  [env vars](https://code.claude.com/docs/en/env-vars)).
- Hooks can add context (`additionalContext`) but cannot change the request's caching metadata, model or
  system prompt; caching is changed only through those settings ([hooks](https://code.claude.com/docs/en/hooks)).
- A router gateway (OpenRouter, freellmapi) must pass `cache_control` and the `anthropic-beta` header through; see
  [backends.md](backends.md).
- OpenAI caches stable prefixes automatically (about 1,024 tokens minimum on current models)
  ([OpenAI prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching)).

**When 1-hour subagent caching pays:** only for subagents resumed after more than 5 minutes but within the
hour. Short one-shot agents pay the 2x write for nothing.

## Keeping the cache warm in long sessions

- Keep model and effort fixed; do not connect or disconnect MCP servers or plugins mid-session.
- CLAUDE.md edits take effect only after `/clear`, `/compact` or a restart; batch them.
- Compact at natural breaks, not mid-task. Check hit rate with `/usage`.

## Our own cache: send less, more stably

Provider caching only discounts what is re-sent. The bigger saving is not sending it:

1. **Context packet.** Start every agent and every resumed session from `task_state.py show --brief`
   (length grows with open findings) plus the plan path, not from the conversation. Keep the packet's
   order fixed so it forms a stable prefix.
2. **Pointers, not pastes.** Pass file paths and line ranges; let the agent read what it needs.
3. **Small memory slices.** Recall about 10 relevant facts from the CRISP vault, never a dump.
4. **Compact outputs.** Verdict, evidence, next action. Logs to files; quote only the failing lines.
5. **Graph before grep** on codebases that have one.
6. **Spend by role**: senior models only where judgement is the work (see [standards.md](standards.md)).
