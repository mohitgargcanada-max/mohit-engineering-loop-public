# Capacity: pacing work against 5-hour and weekly limits

Goal: keep work moving within plan limits, and never lose work when a limit hits. The coordinator checks
capacity before dispatching each agent and at every checkpoint.

## Read the limits

- **Claude**: in the desktop app, the `get_usage` session tool returns the plan (e.g. Max), the 5-hour and
  weekly windows (overall and per model) with percent used and reset time. In a terminal, `/usage` shows the
  same. Save it as JSON (`{"observed_at": "...", "plan": {...}}`) for the script.
- **Codex**: Codex rollout files carry `rate_limits` (primary = 300-minute window, secondary =
  10,080-minute window, plan type). The script reads the newest rollout under `CODEX_HOME/sessions`, or a log
  that contains `rate_limits` events. A normal `codex exec` run writes a rollout with them (checked
  2026-10-24); `--ephemeral` runs write none, and `exec --json` output carries no `rate_limits`, so leave
  `--ephemeral` off when you want readings. A Codex error event or `ERROR:` line saying "hit your usage limit"
  after the last reading counts as exhausted; the phrase inside a tool's output does not.

```text
python ABSOLUTE/scripts/capacity.py --claude CLAUDE_USAGE.json [--codex-log RUN.jsonl]
codex [plus]: go - five_hour 5% (go), weekly 16% (go)
claude [Max]: no-new-large-work - five_hour 82% (no-new-large-work), weekly 40% (go)
```

## Thresholds (yours to set)

`~/.mel/capacity.json` (or `MEL_CAPACITY`) overrides any of the defaults:

```json
{"five_hour": {"no_new_work": 80, "checkpoint": 90}, "weekly": {"no_new_work": 70, "checkpoint": 90}, "stale_minutes": 30}
```

## Decisions and what to do

| Decision | Meaning | Coordinator action |
|---|---|---|
| `go` | Below both thresholds | Dispatch normally |
| `no-new-large-work` | A window passed `no_new_work` | Finish the current step; route new large work to the provider with headroom, or to the fallback ladder for low-risk pieces |
| `checkpoint-and-handoff` | A window passed `checkpoint`, or the limit was hit | Commit WIP, write the checkpoint, hand off (`handoff --capacity "..."`) or pause until the reset |
| `unknown` | No reading; a reading that is stale, has no usable `observed_at`, or lacks the 5-hour or weekly window (a window already at its checkpoint threshold still gives `checkpoint-and-handoff`) | Get a fresh, complete reading before dispatching anything large |

- Work is never routed to a backend model because a native provider is busy if the work is risky; it waits.
- The 5-hour window resets often: prefer pausing a provider for its 5-hour reset over handing off a half-done
  step. The weekly window is the one that needs a handoff.
- Record the decision line in the handoff `--capacity` note so the next agent knows why work moved.
- When a provider is `unknown` or exhausted and the user approves working without it, enter single-provider mode ([delivery.md](delivery.md#single-provider-mode)) for the other provider. A fresh, complete `ok` reading for the absent provider means leave the mode (`single-provider-leave`) and use real cross-provider review again.
- The script reads usage; it does not enforce it. Pacing is the coordinator's discipline.
- When Claude is out but Codex has headroom, keep work moving with a detached Codex queue runner or cloud
  sessions: [unattended.md](unattended.md).
