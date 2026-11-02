"""Usage-window check for Mohit Engineering Loop: 5-hour and weekly limits per provider -> pacing decision.

Reads Codex limits from its own JSONL rollouts under CODEX_HOME/sessions, or any other JSONL log that carries
`rate_limits` events (`codex exec --json` output does not), and Claude limits from a JSON file the coordinator saves from Claude Code's usage report (the desktop
app's get_usage `plan` object, or the same shape written by hand from /usage). Never calls a model.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

DEFAULTS = {'five_hour': {'no_new_work': 80, 'checkpoint': 90}, 'weekly': {'no_new_work': 70, 'checkpoint': 90},
            'stale_minutes': 30}
ORDER = {'go': 0, 'no-new-large-work': 1, 'checkpoint-and-handoff': 2, 'unknown': 3}

def thresholds(path=None):
    path = Path(path or os.environ.get('MEL_CAPACITY') or Path.home() / '.mel' / 'capacity.json')
    merged = json.loads(json.dumps(DEFAULTS))
    if path.is_file():
        for key, value in json.loads(path.read_text(encoding='utf-8')).items():
            merged[key] = {**merged[key], **value} if isinstance(value, dict) else value
    return merged

def decide(used, window, limits):
    rule = limits[window]
    return 'checkpoint-and-handoff' if used >= rule['checkpoint'] else 'no-new-large-work' if used >= rule['no_new_work'] else 'go'

def parse_time(value):
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc)
    return datetime.fromisoformat(str(value).replace('Z', '+00:00'))

def window_name(minutes=None, label=''):
    label = label.lower()
    if minutes == 300 or '5-hour' in label or '5 hour' in label:
        return 'five_hour'
    if minutes == 10080 or label.startswith('weekly'):
        return 'weekly'
    return None

def limit_error(line):
    # Only Codex's own error lines count; the phrase inside a tool's output (a file it read) does not.
    if 'hit your usage limit' not in line:
        return False
    try:
        event = json.loads(line)
    except ValueError:
        return line.lstrip().startswith('ERROR:')
    payload = event.get('payload') or event.get('msg') or {}
    return event.get('type') in ('error', 'turn.failed', 'stream_error') or payload.get('type') in ('error', 'stream_error')

def codex_reading(log=None, home=None):
    # Last rate_limits event in the given log, or in the most recently written Codex rollout.
    if log:
        files = [Path(log)]
    else:
        root = Path(home or os.environ.get('CODEX_HOME') or Path.home() / '.codex') / 'sessions'
        files = sorted(root.rglob('*.jsonl'), key=lambda p: p.stat().st_mtime, reverse=True)[:5] if root.is_dir() else []
    for path in files:
        last, hit = None, None
        for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
            if limit_error(line):
                hit = line.strip()[:200]
            if '"rate_limits"' not in line:
                continue
            try:
                event = json.loads(line)
            except ValueError:
                continue
            limits = (event.get('payload') or event.get('msg') or event).get('rate_limits')
            if isinstance(limits, dict):
                last, hit = (event.get('timestamp'), limits), None
        if hit:
            # A limit error after the last reading outranks any percentage.
            return {'provider': 'codex', 'plan': None, 'observed_at': None, 'source': str(path), 'windows': [], 'limit_hit': hit}
        if last:
            stamp, limits = last
            windows = []
            for slot in ('primary', 'secondary'):
                item = limits.get(slot) or {}
                name = window_name(item.get('window_minutes'))
                if name and isinstance(item.get('used_percent'), (int, float)):
                    windows.append({'window': name, 'label': slot, 'used': float(item['used_percent']),
                                    'resets_at': parse_time(item['resets_at']).isoformat() if item.get('resets_at') else None})
            return {'provider': 'codex', 'plan': limits.get('plan_type') or limits.get('limit_id'), 'observed_at': stamp,
                    'source': str(path), 'windows': windows}
    return {'provider': 'codex', 'plan': None, 'observed_at': None, 'source': None, 'windows': []}

def claude_reading(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('Claude usage must be a JSON object.')
    plan = data['plan'] if isinstance(data.get('plan'), dict) else data
    if not isinstance(plan.get('windows'), list) or (plan.get('plan') is not None and not isinstance(plan['plan'], str)):
        raise ValueError('Claude plan needs a windows list and an optional plan name string.')
    windows = []
    for item in plan['windows']:
        if not isinstance(item, dict) or not isinstance(item.get('label'), str) \
                or not isinstance(item.get('percentUsed'), (int, float)) or isinstance(item['percentUsed'], bool):
            raise ValueError('Claude windows need a label string and numeric percentUsed.')
        name = window_name(label=item.get('label', ''))
        if name:
            windows.append({'window': name, 'label': item.get('label'), 'used': float(item['percentUsed']),
                            'resets_at': item.get('resetsAt')})
    return {'provider': 'claude', 'plan': plan.get('plan'), 'observed_at': data.get('observed_at'), 'source': str(path),
            'windows': windows}

def assess(reading, limits, now=None):
    now = now or datetime.now(timezone.utc)
    result = {**reading, 'decision': 'unknown', 'notes': []}
    if reading.get('limit_hit'):
        result['decision'] = 'checkpoint-and-handoff'
        result['notes'].append('limit hit: ' + reading['limit_hit'])
        return result
    if not reading['windows']:
        result['notes'].append('no usage reading; check by hand before dispatching')
        return result
    # `go` needs a dated reading of both windows; anything less is unknown, unless a window is already exhausted.
    try:
        observed = parse_time(reading['observed_at']) if reading.get('observed_at') else None
        age = (now - observed).total_seconds() / 60 if observed is not None and observed.utcoffset() is not None else None
    except (TypeError, ValueError, OverflowError, OSError):
        age = None
    if age is None:
        result['notes'].append('reading has no usable timestamp')
    elif age > limits['stale_minutes']:
        result['notes'].append(f'reading is {age:.0f} min old')
    present = {item['window'] for item in reading['windows']}
    result['notes'] += [f'no {name} reading' for name in ('five_hour', 'weekly') if name not in present]
    worst = 'go'
    for item in reading['windows']:
        used = item['used']
        if item['resets_at']:
            try:
                reset = parse_time(item['resets_at'])
                if reset.utcoffset() is None:
                    raise ValueError('Reset timestamp needs a timezone.')
                if reset <= now:
                    used, item['note'] = 0.0, 'window has reset since the reading'
            except (TypeError, ValueError, OverflowError, OSError):
                result['notes'].append(f"{item['window']} window has no usable reset timestamp")
        item['decision'] = decide(used, item['window'], limits)
        worst = max(worst, item['decision'], key=ORDER.get)
    if result['notes'] and worst != 'checkpoint-and-handoff':
        worst = 'unknown'
    result['decision'] = worst
    return result

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--claude', help='JSON saved from Claude Code usage (get_usage output or its plan object).')
    parser.add_argument('--codex-log', help='Codex JSONL with rate_limits events; default: newest rollout.')
    parser.add_argument('--codex-home'); parser.add_argument('--thresholds')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    try:
        limits = thresholds(args.thresholds)
        readings = [assess(codex_reading(args.codex_log, args.codex_home), limits)]
        if args.claude:
            readings.append(assess(claude_reading(args.claude), limits))
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr); return 1
    if args.json:
        print(json.dumps(readings, indent=2)); return 0
    for r in readings:
        parts = ', '.join(f"{w['window']} {w['used']:.0f}% ({w['decision']})" for w in r['windows']) or 'no data'
        print(f"{r['provider']} [{r['plan'] or 'plan unknown'}]: {r['decision']} - {parts}" + (f" - {'; '.join(r['notes'])}" if r['notes'] else ''))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
