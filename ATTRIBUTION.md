# Attribution

Mohit Engineering Loop is independently authored for Mohit Garg. The people and projects below shaped it.
Where we learned from someone's work we adopted ideas only, re-written in our own words; no upstream
source, runner, skill text, templates or artwork is distributed here.

## Inspiration

- **Chase AI**, [Claudex Loop](https://github.com/chaseai-yt/claudex-loop): the core idea of independent
  Claude/Codex plan review and final inspection. Credit for that inspiration belongs to Chase AI. This
  project is not an official Claudex release.
- **Matt Pocock**, [skills](https://github.com/mattpocock/skills): feedback-loop-first debugging, test
  expectations independent of the code under test, reviewing against the spec separately from standards,
  hotspot-first architecture work with a deletion test, and one-question-at-a-time design interviews
  (`references/discipline.md`).
- **Andrej Karpathy**, whose observations on how coding agents go wrong underlie the
  [Karpathy guidelines](https://github.com/multica-ai/andrej-karpathy-skills) written by **Jiayuan Zhang**
  ([forrestchang](https://github.com/forrestchang), MIT) and now hosted by **multica-ai**:
  think before coding, simplicity first, surgical changes, goal-driven verification (`references/standards.md`,
  `references/discipline.md`).
- **Mohit Garg**, CRISP (his own memory and handover toolkit) and his own projects: handover,
  memory, compact-output and ledger practices, and the guardrails in `references/discipline.md` that came
  from real failures there. CRISP is optional, not bundled or required.

## Tools and documentation the skill relies on or describes

- **OmniRoute** by Diego Rodrigues de Sa e Souza ([diegosouzapw/OmniRoute](https://github.com/diegosouzapw/OmniRoute), now with
  [Cheaper Inference](https://github.com/cheaper-inference/OmniRoute); MIT): documented as an optional
  fallback model backend (`references/backends.md`). Not bundled, installed or required.
- **Anthropic** ([Claude Code docs](https://code.claude.com/docs), [prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching))
  and **OpenAI** ([Codex docs](https://learn.chatgpt.com/docs), [prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching)):
  CLI behaviour, usage limits and caching facts cited in `references/context.md` and `references/capacity.md`.
- **Git** ([git-scm.com](https://git-scm.com/docs)): ref and revision semantics behind the local-delivery
  merge check, as raised in Codex's inspections of MEL-002.

## Licence

The new material is licensed under the accompanying MIT license. External CLIs, models, services and
optional integrations retain their own licenses and terms; this project's license does not replace them.
