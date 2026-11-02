# Backends: router fallback

A backend serves a model behind a native CLI harness. The harness is still `claude` (Claude Code) or
`codex` (Codex CLI); the backend changes which model answers. Backends are optional, not bundled, and keep
their own licenses and terms. Verify every command against the installed version before relying on it.

Configured routers (owner's setup note, 2026-11-01; availability and model ids still need a live probe):

- **OpenRouter direct**: paid API key, called directly. Private code only where the chosen provider's current
  terms allow it (see Data boundary).
- **freellmapi**: a local router at `127.0.0.1:3001` in front of free tiers. Public or non-sensitive work only.

OmniRoute was the configured router until 2026-10-29 and was removed from the owner's machine on 2026-11-01;
earlier dated notes in this repository's task records mention it as history. It is no longer a default.

## Labels

`harness@backend[:session]`, for example `claude@openrouter`, `codex@freellmapi:night1`. Record the
requested model in the plan. The helper treats any label with a backend as non-native:

- it may own a task or build;
- it may never approve a plan or record an inspection;
- its code is not ready until a native `claude` or `codex` review covers the same snapshot.

A Claude Code session pointed at a GPT, GLM or Gemini model through a router is not "Claude" for
independence. Label it `claude@openrouter` or `claude@freellmapi`, never `claude`. A native build is never
relabelled as a backend one to pass a gate; in single-provider mode the model comparison applies to backend
labels too ([delivery.md](delivery.md#single-provider-mode)).

## Run it

- Point the harness at the router for that process only; never change global config. Keep keys in the
  environment or the vault, never in a repository file, shell history, handoff or task log.
- OpenRouter direct: an OpenRouter key in the environment; Claude Code and Codex are configured per process
  with the endpoint and model the router documents. Check the account's credit limit before a batch.
- freellmapi: start the local router, confirm it answers on `127.0.0.1:3001`, list its live models, then
  launch the harness against it for that process.
- Pin the exact model id for the task. Never use `auto` or a router-chosen model where reproducibility
  matters; record the model id the router reports as serving. Router logs are evidence of identity, not proof.
- Free models are retired without notice (an OpenRouter `:free` model returned 404 on every call in October
  2026); repeat the live model list when a call fails with model-not-found.

## Prompt caching through a gateway

Claude Code's caching needs `cache_control` in the request body to reach the provider: a gateway
that strips it bills the whole history uncached. The 1-hour TTL also needs the `anthropic-beta`
header forwarded unchanged (code.claude.com/docs/en/prompt-caching). Check `ephemeral_1h_input_tokens` in
`claude -p "hello" --output-format json` before relying on caching through a router. Non-Anthropic
models use their own provider's caching rules.

## Data boundary

- Choose providers whose current terms fit the code: private or client code only to providers that do
  not train on or retain prompts, or to local models. A free tier is public-only unless the provider's
  current terms say that tier is not used for training and not retained.
- freellmapi routes to free tiers: public or non-sensitive data only.
- OpenRouter direct (paid) may carry private code only when the selected upstream provider's terms allow it
  and the account's data controls (no training, ZDR where offered) are on; verify in the privacy settings
  before the first private request (openrouter.ai/docs/guides/privacy/logging, openrouter.ai/docs/guides/features/zdr).
  OpenRouter `:free` models are public / non-sensitive only.
- Never route secrets, credentials, vault code or customer data through a backend.

## Fallback providers ($0 first)

Default: spend nothing beyond the Claude and Codex plans. Checked 2026-10-26; verify the current terms first.

| Route | Use for | Settings to turn on | Source |
|---|---|---|---|
| Groq free tier | private code | Data Controls -> Zero Data Retention (default already keeps no inference data, but reliability/abuse logs may be kept up to 30 days unless ZDR is on) | [Services Agreement section 4.2](https://console.groq.com/docs/legal/services-agreement) (no training without customer permission); [retention and ZDR](https://console.groq.com/docs/your-data) |
| OpenRouter `:free` models | public / non-sensitive only | account credit limit 0; free-model training setting off; ZDR enforced in privacy settings | openrouter.ai/docs/guides/privacy/logging; openrouter.ai/docs/guides/features/zdr |
| freellmapi (local, free tiers) | public / non-sensitive only | none can make it private | the router's own documentation and each tier's terms |
| Gemini API, project with NO billing | public / non-sensitive only | none can make it private: on the unpaid tier Google may use prompts and responses to improve its products and human reviewers may read them | ai.google.dev/gemini-api/terms |
| Fireworks (paid) | private code, only with the user's explicit approval to spend | Enable the Enterprise ZDR policy for inference; check covered features and legal/abuse exceptions | [Zero Data Retention policy](https://docs.fireworks.ai/accounts/zero-data-retention) |

Avoid for private code: DeepSeek direct, providers whose terms you have not read (e.g. TokenRouter), any
`:free` endpoint, keyless/web providers and `auto/*` routes.

Choosing the model on a route (no model is current without a dated check):
1. List the route's live models (`GET /v1/models` on the router, or the provider console).
2. Prefer the strongest coding and tool-calling model the route serves, with the context length the task needs.
3. Pin it (never `auto`) and name it in the task plan.
4. Pong test, then one small coding probe taken from the task's own test suite.
5. Record the model id the router reports as serving.

## What backend models may do

Bounded, low-risk building from an already-approved brief: fixtures, docs, mechanical refactors, test
scaffolds, summaries. Not: architecture or plan decisions, security/auth/secrets/data-migration code,
plan review, final inspection. See [standards.md](standards.md) for the fallback ladder.

## Owner-reported providers (2026-11-01)

The owner reports API credentials for **OpenRouter** (paid) and a local **freellmapi** router; earlier
setup also had Groq, NVIDIA NIM and Gemini keys. This is a user-confirmed setup note, not proof that any
route is healthy or that any model id remains available.

- Never read, print, copy, or save provider key values in this skill, a repository, shell history, handoff, or task log.
- At task dispatch, check the router answers, list its live models and record the provider/model ids with credential fields redacted. Treat a configured key as availability, not successful routing; verify with a small, non-sensitive probe.
- Use the cheapest capable pinned model for bounded low-risk builds, respecting the user's model choice and explicit spending limits. Do not silently route to paid models.
- Until data controls are verified, route only public/non-sensitive data. These runs remain non-native: label them `claude@openrouter`, `codex@openrouter`, `claude@freellmapi` or `codex@freellmapi`; they may build bounded work but cannot plan-approve or independently inspect it. A native Claude/Codex review is still required.
