"""Original stdlib task state for Mohit Engineering Loop. No model or merge execution."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from copy import deepcopy
from datetime import date
from fnmatch import fnmatchcase
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import uuid

class StateError(Exception):
    pass

def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + '\n').encode()

def digest(data):
    return hashlib.sha256(data).hexdigest()

def git(repo, *args):
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, check=True)
    return result.stdout

def snapshot(repo):
    repo = Path(repo).resolve()
    if Path(git(repo, 'rev-parse', '--show-toplevel').decode().strip()).resolve() != repo:
        raise StateError('Use the worktree root, not a subdirectory.')
    paths = ['--', '.', ':(exclude).mel']
    tracked = git(repo, 'diff', '--no-ext-diff', '--no-textconv', '--binary', 'HEAD', *paths)
    staged = git(repo, 'diff', '--no-ext-diff', '--no-textconv', '--cached', '--binary', 'HEAD', *paths)
    untracked = git(repo, 'ls-files', '--others', '--exclude-standard', '-z', *paths)
    index = git(repo, 'ls-files', '--stage', '-z', *paths)
    extra = []
    for raw in untracked.split(b'\0'):
        if not raw:
            continue
        name = os.fsdecode(raw)
        path = repo / name
        data = os.fsencode(os.readlink(path)) if path.is_symlink() else path.read_bytes()
        extra.append([name, digest(data)])
    return {'repo': str(repo), 'branch': git(repo, 'symbolic-ref', '--short', 'HEAD').decode().strip(),
            'head': git(repo, 'rev-parse', 'HEAD').decode().strip(),
            'dirty': bool(tracked or staged or extra),
            'fingerprint': digest(index + b'\0' + tracked + b'\0' + staged + b'\0' + encoded(extra))}

def same_snapshot(left, right):
    # Metadata-only checkpoint commits may advance HEAD without changing reviewed code.
    return {k: v for k, v in left.items() if k != 'head'} == {k: v for k, v in right.items() if k != 'head'}

def reference(path):
    path = Path(path).resolve()
    if not path.is_file():
        raise StateError(f'Evidence file missing: {path}')
    return {'path': str(path), 'sha256': digest(path.read_bytes())}

def unchanged(ref):
    return reference(ref['path']) == ref

LABEL = re.compile(r'(claude|codex)(@[a-z0-9][a-z0-9._-]*)?(:[A-Za-z0-9._-]+)?')

def provider(label):
    # Key is harness or harness@backend; a backend (e.g. omniroute) serves a non-native model.
    match = LABEL.fullmatch(label or '')
    if not match:
        raise StateError('Agent must be claude or codex, optionally @backend and :session.')
    return match.group(1) + (match.group(2) or '')

def native(key):
    return '@' not in key

def harness(key):
    return key.partition('@')[0].partition(':')[0]

def norm(model):
    # Free-text model ids compare equal across case and dots: Claude-Opus-5.5 == claude-opus-5-5.
    return (model or '').strip().lower().replace('.', '-')

OTHER = 'The other provider acted; leave the single-provider mode first (single-provider-leave).'

def refuse_other(state, key):
    # While the mode is on, the unavailable provider may not act, review, build or receive work.
    mode = state.get('single_provider')
    if mode and harness(key) != mode['available']:
        raise StateError(OTHER)

def new_mode(available, reason, approved_by, revision):
    if available not in ('claude', 'codex') or not (reason or '').strip() or not (approved_by or '').strip():
        raise StateError('Single-provider mode needs the available provider (claude|codex), --reason and --approved-by (the user\'s approval).')
    return {'available': available, 'reason': reason.strip(), 'approved_by': approved_by.strip(),
            'entered_revision': revision, 'date': date.today().isoformat()}

def review_label(state):
    # Never let single-provider review pass for cross-provider review: derived from the live mode or any stored evidence.
    mode = state.get('single_provider')
    if not mode:
        stored = [state.get('plan_review')] + list((state.get('reviews') or {}).values()) + list((state.get('evals') or {}).values()) + list(state.get('rounds', []))
        mode = next((x['single_provider'] for x in stored if x and x.get('single_provider')), None)
    if not mode:
        return ''
    return f"SINGLE-PROVIDER REVIEW ({mode['reason']}, since {mode.get('since') or mode.get('date')})"

def authorship_models(state):
    # Models that built anything in this task. Fails closed where authorship is unknown: a reviewer's model
    # cannot be compared to a builder that was never recorded. An owner with no ledger entry on a tracked task is fine.
    if state.get('adoption'):
        raise StateError('Single-provider review cannot cover adopted work of unknown authorship; use both providers or revise the task.')
    if 'recorded_fingerprint' not in state:
        raise StateError('Legacy state has no recorded working copy, so authorship is unknown; single-provider review is refused.')
    return {norm(e['model']) for e in state.get('ledger', [])}

def review_rule(state, command, reviewer, data, model, same_model='', user_approval=''):
    # None outside the mode (callers keep the old checks). Inside: the available provider reviews, but only as a fresh,
    # adversarial session on a different model. fresh_session/built_nothing are attestations the helper cannot verify;
    # the model comparison is the one enforced discriminator, and --same-model (with the user's approval) waives it.
    mode = state.get('single_provider')
    if not mode:
        return None
    if not native(reviewer) or harness(reviewer) != mode['available']:
        raise StateError(OTHER if native(reviewer) else 'Backend models never review, even in single-provider mode.')
    for field in ('fresh_session', 'built_nothing'):
        if data.get(field) is not True:
            raise StateError(f'A single-provider report must state {field}: true (reviewer attestation).')
    adversarial = data.get('adversarial')
    if not isinstance(adversarial, list) or not adversarial or not all(isinstance(x, str) and x.strip() for x in adversarial):
        raise StateError('A single-provider report needs a non-empty adversarial list: what could be wrong, a control that could fail.')
    if not (model or '').strip():
        raise StateError('Pass --model: the reviewer model must be recorded and differ from the builder and plan models.')
    if command == 'approve-plan':
        if not state.get('plan_model'):
            raise StateError('Single-provider plan approval needs the plan model (--plan-model) to compare with.')
        known = {norm(state['plan_model'])} | {norm(e['model']) for e in state.get('ledger', [])}
    else:
        known = authorship_models(state)
    used = None
    if norm(model) in known:
        if not (same_model or '').strip() or not (user_approval or '').strip():
            raise StateError('Reviewer model equals a builder or plan model; use a different model, or --same-model REASON with --user-approval TEXT.')
        used = {'reason': same_model.strip(), 'user_approval': user_approval.strip()}
    return {'reason': mode['reason'], 'since': mode['date'], 'same_model': used}

def location(repo, task):
    if not re.fullmatch(r'MEL-[0-9]{3,}', task):
        raise StateError('Task must be MEL- followed by at least three digits.')
    return Path(repo).resolve() / '.mel' / task

@contextmanager
def locked(folder):
    folder.mkdir(parents=True, exist_ok=True)
    lock = folder / 'state.lock'
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise StateError('Task is locked; inspect the writer before manual recovery.') from exc
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield
    finally:
        lock.unlink()

def atomic(path, value):
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temp.open('xb') as stream:
            stream.write(encoded(value)); stream.flush(); os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)

def load(repo, task, bind=True):
    state = json.loads((location(repo, task) / 'state.json').read_text(encoding='utf-8'))
    if state['schema_version'] != 1 or state['task'] != task:
        raise StateError('Unsupported schema or mismatched task.')
    # Reading is allowed from any worktree; only mutations are bound to the recorded one.
    if bind and state['repo'] != str(Path(repo).resolve()):
        raise StateError('Task belongs to a different worktree; reconcile an explicit handoff.')
    return state

def bound(state, repo):
    current = snapshot(repo)
    if current['branch'] != state['branch']:
        raise StateError('Branch changed; do not mutate another task.')
    return current

def local_branch(repo, name):
    # An exact, stored, non-symbolic branch, never a revision expression (main~0, @{-1}), a
    # case alias resolved by the filesystem (MAIN) or a symref to the task branch. The commit
    # comes from Git's own listing, so the name is never resolved a second time. Records are
    # split on raw LF (forbidden in ref names) and refs compared in full, so neither Unicode
    # line separators nor a tag shortening HEAD to heads/<name> can stand in for another branch.
    try:
        clean = git(repo, 'check-ref-format', '--branch', name).decode().strip()
        task_ref = git(repo, 'symbolic-ref', '-q', 'HEAD').decode().strip()
        raw = git(repo, 'for-each-ref', '--format=%(refname)%00%(symref)%00%(objectname)', 'refs/heads/')
        listed = {}
        for record in raw.split(b'\n'):
            if record:
                fields = record.split(b'\0')
                if len(fields) != 3:
                    raise StateError('Unexpected branch listing from Git.')
                listed[fields[0]] = fields[1:]
        if task_ref.encode() not in listed:
            # Windows can keep a case alias of the stored branch in HEAD; fail closed rather than guess.
            raise StateError('HEAD names a branch spelling Git does not list; check out the branch by its exact name.')
        target_ref = f'refs/heads/{name}'
        entry = listed.get(target_ref.encode())
        if clean != name or target_ref == task_ref or not entry or entry[0]:
            raise StateError('Local target must be another existing branch, named exactly, not a symbolic ref.')
        return entry[1].decode()
    except subprocess.CalledProcessError as exc:
        raise StateError(f'Local target must be an existing branch name: {name}') from exc

def pending(state):
    handoff = state['handoff']
    return bool(handoff and not handoff['acknowledged'] and not handoff.get('superseded_by'))

def invalidate(state):
    # Anything that changes ownership, code or evidence voids earlier approvals.
    state['reviews'] = {}
    state.pop('evals', None)
    if state['status'] == 'ready':
        state['status'] = 'review_pending'

def work_tree(repo):
    # Tree object of the working copy (tracked + untracked, ignored files and .mel excluded), built in a
    # throwaway index so the real index is untouched. Only adds objects; refs and the index never change.
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, 'GIT_INDEX_FILE': str(Path(tmp) / 'index')}
        for args in (('read-tree', 'HEAD'), ('add', '-A', '--', '.', ':(exclude).mel')):
            subprocess.run(['git', '-C', str(repo), *args], env=env, check=True, capture_output=True)
        return subprocess.run(['git', '-C', str(repo), 'write-tree'], env=env, check=True, capture_output=True).stdout.decode().strip()

def changed_files(repo, since, tree):
    # Paths that differ between the last recorded working copy (tree or commit) and now; never .mel.
    raw = git(repo, 'diff', '--name-only', '-z', since, tree, '--', '.', ':(exclude).mel')
    return sorted(os.fsdecode(x) for x in raw.split(b'\0') if x)

BENCH_WINDOW, BENCH_HIGH, BENCH_SERIOUS = 10, 2, 4

def roster_path():
    return Path(os.environ.get('MEL_ROSTER') or Path.home() / '.mel' / 'roster.jsonl')

def roster():
    path = roster_path()
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]

def repo_id(repo):
    return sorted(git(repo, 'rev-list', '--max-parents=0', 'HEAD').decode().split())[0]

def roster_append(repo, record):
    # One line per event; the roster spans projects so a model's record follows it.
    record = {'date': date.today().isoformat(), 'repo_id': repo_id(repo), **record}
    path = roster_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(record, sort_keys=True) + '\n')

def task_events(state, rid):
    # Roster events derived from task state. Ids use list positions: ledger and findings are append-only,
    # so an id never changes and stays unique when several entries share one revision.
    task, events = state['task'], []
    for n, e in enumerate(state.get('ledger', [])):
        events.append({'event_id': f'{rid}:{task}:build:{n}', 'repo_id': rid, 'kind': 'build', 'task': task,
                       'builder': e['builder'], 'model': e['model']})
    for n, f in enumerate(state.get('findings', [])):
        events.append({'event_id': f'{rid}:{task}:finding:{n}', 'repo_id': rid, 'kind': 'finding', 'task': task,
                       'builder': f['builder'], 'model': f['model'], 'severity': f['severity'], 'id': f['id'], 'report': f['report']})
    return events

def sync_roster(repo, state):
    # Idempotent: appends only this task's events the roster does not hold yet. Returns how many.
    have = {e.get('event_id') for e in roster()}
    missing = [e for e in task_events(state, repo_id(repo)) if e['event_id'] not in have]
    if missing:
        path = roster_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as stream:
            for event in missing:
                stream.write(json.dumps({'date': date.today().isoformat(), **event}, sort_keys=True) + '\n')
    return len(missing)

def try_sync(repo, state, when):
    # A roster failure never undoes or hides a recorded state change; roster-sync repairs it later.
    try:
        sync_roster(repo, state)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f'WARNING: roster not synchronized {when} ({exc}); run roster-sync.', file=sys.stderr)

def bench_status(model, pending=()):
    # Window = the model's last 10 tasks in roster order (every build counts, clean ones too); each finding
    # counts once per task and id, at its latest (possibly corrected) severity. `pending` = events of the
    # task being changed, so its unpublished findings count before the roster has them.
    tasks, latest = [], {}
    entries = roster()
    published = {e.get('event_id') for e in entries}
    for entry in entries + [e for e in pending if e['event_id'] not in published]:
        if entry.get('model') != model:
            continue
        key = (entry.get('repo_id'), entry.get('task'))
        if key not in tasks:
            tasks.append(key)
        if entry.get('kind') == 'finding':
            latest[key + (entry.get('id'),)] = entry.get('severity')
    window = set(tasks[-BENCH_WINDOW:])
    found = [severity for key, severity in latest.items() if key[:2] in window]
    high, serious = found.count('high'), found.count('high') + found.count('medium')
    if high >= BENCH_HIGH or serious >= BENCH_SERIOUS:
        return f'{model} is benched: {high} high and {serious} high+medium findings in its last {len(window)} tasks.'
    return None

def author_of_plan(explicit, fallback):
    # An explicit author must be native; a backend owner/actor defaults to its harness (claude@omniroute -> claude),
    # so the other native provider reviews the plan and backend planning gains no extra approver.
    if explicit is not None:
        key = provider(explicit)
        if not native(key):
            raise StateError('The plan author must be native claude or codex.')
        return key
    return provider(fallback).partition('@')[0].partition(':')[0]

def adopted_authors(adopt):
    # BUILDER=MODEL pairs naming who wrote work that exists before tracking starts.
    pairs = []
    for item in adopt or []:
        builder, _, model = item.partition('=')
        if not model.strip():
            raise StateError('Use --adopt BUILDER=MODEL, e.g. claude=claude-opus-5-5.')
        pairs.append((provider(builder), model.strip()))
    return pairs

def init(repo, task, owner, plan, criteria, waiver='', baseline=None, local_target=None, scope=None, risk='normal', budget_plan=3, budget_inspect=2, rubric=None, adopt=None, adopt_unknown='', plan_author=None, single_provider=None, reason='', approved_by='', plan_model=None):
    provider(owner)
    mode = new_mode(single_provider, reason, approved_by, 1) if single_provider else None
    if mode and (harness(owner) != single_provider or not (plan_model or '').strip()):
        raise StateError('Single-provider mode: the owner must be the available provider and --plan-model is required.')
    plan_author = author_of_plan(plan_author, owner)
    authors = adopted_authors(adopt)
    if not criteria or len(set(criteria)) != len(criteria) or any(not x.strip() for x in criteria):
        raise StateError('Provide nonempty unique acceptance criterion IDs.')
    if risk not in ('normal', 'high') or budget_plan < 1 or budget_inspect < 1 or any(not g.strip() for g in scope or []):
        raise StateError('Risk is normal or high, budgets at least 1, scope globs non-empty.')
    if risk == 'high' and not rubric:
        raise StateError('A high-risk task needs --rubric: the reviewed rubric file its eval is scored against.')
    rubric_ref = reference(rubric) if rubric else None
    if rubric_ref:
        rubric_items(rubric_ref)
    folder = location(repo, task)
    current = snapshot(repo)
    if local_target is not None:
        local_branch(repo, local_target)
    baseline = git(repo, 'rev-parse', '--verify', baseline + '^{commit}').decode().strip() if baseline else current['head']
    git(repo, 'merge-base', '--is-ancestor', baseline, current['head'])
    unknown = (adopt_unknown or '').strip()
    adopting = baseline != current['head'] or current['dirty']
    if adopting and not authors and not unknown:
        raise StateError('Work already exists since the baseline (commits or uncommitted files); name its authors with '
                         '--adopt BUILDER=MODEL, or record --adopt-unknown REASON so both providers must inspect it.')
    if (authors or unknown) and not adopting:
        raise StateError('Nothing to adopt: the baseline is HEAD and the working copy is clean.')
    with locked(folder):
        if (folder / 'state.json').exists():
            raise StateError('Task already exists; never overwrite it.')
        tree = work_tree(repo)
        if authors and plan_author not in [key for key, _ in authors]:
            # Only checkable when the plan file is among the adopted files; otherwise the caller's --plan-author stands.
            try:
                top = Path(git(repo, 'rev-parse', '--show-toplevel').decode().strip()).resolve()
                relative = Path(plan).resolve().relative_to(top).as_posix()
            except (ValueError, subprocess.CalledProcessError):
                relative = None
            if relative and relative in changed_files(repo, baseline, tree):
                raise StateError(f'The adopted work includes the plan file but no adopted builder is its author {plan_author}; '
                                 'pass --plan-author with the provider that wrote it.')
        builders = [provider(owner)]
        ledger = []
        if adopting:
            # Adopted authors replace the default owner-builder; the owner joins when it declares its own changes.
            files = changed_files(repo, baseline, tree)
            builders = list(dict.fromkeys([key for key, _ in authors] + (['claude', 'codex'] if unknown else [])))
            ledger = [{'revision': 1, 'builder': key, 'model': model, 'head': current['head'], 'files': files, 'adopted': True}
                      for key, model in authors]
        state = {'schema_version': 1, 'task': task, 'revision': 1, 'owner': owner,
                 'repo': current['repo'], 'branch': current['branch'], 'base': baseline,
                 'plan': reference(plan), 'plan_review': None, 'coordinator': provider(owner), 'plan_author': plan_author, 'plan_review_waiver': waiver,
                 'criteria': {x: {'passed': False, 'proof': None} for x in criteria},
                 'builders': builders, 'blockers': [], 'status': 'planned', 'pr': None,
                 'handoff_number': 0, 'handoff': None, 'reviews': {}, 'recorded_fingerprint': current['fingerprint'],
                 'recorded_head': current['head'], 'recorded_tree': tree, 'risk': risk, 'budget': {'plan': budget_plan, 'inspect': budget_inspect}}
        if ledger:
            state['ledger'] = ledger
        if unknown:
            state['adoption'] = {'attribution': 'unknown', 'reason': unknown, 'files': files}
        if mode:
            state['single_provider'] = mode
        if (plan_model or '').strip():
            state['plan_model'] = plan_model.strip()
        if scope:
            state['scope'] = list(scope)
        if rubric_ref:
            state['rubric'] = rubric_ref
        if local_target is not None:
            state['delivery'] = {'mode': 'local', 'target': local_target}
        attributes = folder / '.gitattributes'
        policy = b'*.json text eol=lf\n'
        if attributes.exists() and attributes.read_bytes().replace(b'\r\n', b'\n') != policy:
            raise StateError('Existing task attributes conflict with immutable LF JSON; reconcile manually.')
        if not attributes.exists():
            with attributes.open('xb') as stream:
                stream.write(policy)
        atomic(folder / 'state.json', state)
    if ledger:
        try_sync(repo, state, 'after recording adopted authors')
    return state

def declare(repo, state, current, author):
    # author: {'builder', 'model', optional 'outside' reason, optional 'override' reason}.
    key = provider(author.get('builder'))
    refuse_other(state, key)
    model = (author.get('model') or '').strip()
    if not model:
        raise StateError('Declare the model with --model alongside --builder.')
    tree = work_tree(repo)
    previous = state.get('recorded_tree')
    # The recorded tree is an unreferenced object; if Git pruned it, fall back and say so.
    if previous and subprocess.run(['git', '-C', str(repo), 'cat-file', '-e', previous + '^{tree}'], capture_output=True).returncode:
        previous = None
    files = changed_files(repo, previous or state.get('recorded_head') or state['base'], tree)
    legacy = not previous
    state['recorded_tree'] = tree
    scope = state.get('scope') or []
    outside = [f for f in files if scope and not any(fnmatchcase(f, glob) for glob in scope)]
    entry = {'revision': state['revision'] + 1, 'builder': key, 'model': model, 'head': current['head'], 'files': files}
    if legacy:
        # No earlier working-copy record: these files may include other authors' earlier work.
        entry['attribution'] = 'approximate: no recorded working copy to diff against (legacy state or pruned tree)'
    if outside:
        if not (author.get('outside') or '').strip():
            raise StateError(f'Changes outside the declared scope: {", ".join(outside)}. Revise the plan with --scope, or pass --outside-scope REASON.')
        entry['outside_scope'] = {'paths': outside, 'reason': author['outside']}
    # A declaration that changes no files credits existing work; it authorizes no new build, so no bench check.
    benched = bench_status(model, task_events(state, repo_id(repo))) if files else None
    if benched:
        if not (author.get('override') or '').strip():
            raise StateError(benched + ' Use another model, or record the user\'s approval with --override REASON.')
        entry['bench_override'] = {'status': benched, 'reason': author['override']}
    if key not in state['builders']:
        state['builders'].append(key)
    state.setdefault('ledger', []).append(entry)
    return entry

def mutate(repo, task, expected, actor, operation, author=None, gate=True, prepare=None):
    folder = location(repo, task)
    with locked(folder):
        state = load(repo, task)
        if state['revision'] != expected:
            raise StateError('Stale revision; reread state and reconcile.')
        current = bound(state, repo)
        try_sync(repo, state, 'before this change')
        updated = deepcopy(state)
        if prepare:
            # Runs before the declaration so it is judged by what this change installs (revise-plan's scope).
            prepare(updated)
        # Code that changed since the last record must be credited before anything else is recorded.
        # Legacy state has no record, so its authorship is unknown and must be declared once.
        recorded = state.get('recorded_fingerprint')
        entry = declare(repo, updated, current, author) if author else None
        if not entry and gate and recorded != current['fingerprint']:
            raise StateError('Code changed since the last record; declare its author with --builder ACTUAL_AUTHOR --model ACTUAL_MODEL '
                             'on update, handoff, takeover or revise-plan (which installs the new scope before declaration). '
                             'For other commands, run a separate update --builder ACTUAL_AUTHOR --model ACTUAL_MODEL before retrying. '
                             'finding --builder/--model attributes the reported defect, not the current edits.')
        operation(updated, current, folder)
        if snapshot(repo) != current:
            raise StateError('Git changed during mutation; reread before retrying.')
        updated['recorded_fingerprint'] = current['fingerprint']
        updated['recorded_head'] = current['head']
        updated['revision'] += 1
        atomic(folder / 'state.json', updated)
    try_sync(repo, updated, 'after recording the change')
    return updated

def owner_only(state, actor):
    refuse_other(state, actor)
    if state['owner'] != actor:
        raise StateError('Actor does not own this task.')
    if pending(state):
        raise StateError('Transfer pending; acknowledge or explicitly replace it first.')
    if state['status'] == 'merged':
        raise StateError('Merged task is immutable; create a new task for new work.')

def update(repo, task, expected, actor, status=None, passed=None, proof=None, blockers=None, pr=None, author=None):
    def apply(state, current, folder):
        owner_only(state, actor)
        if status:
            if status not in ('planned', 'implementing', 'blocked', 'review_pending'):
                raise StateError('Use the ready/merged commands for gated states.')
            if status == 'implementing':
                plan_check(state)
            state['status'] = status
        if passed:
            if passed not in state['criteria'] or not proof:
                raise StateError('Known criterion and an existing proof file required.')
            state['criteria'][passed] = {'passed': True, 'proof': reference(proof)}
        if blockers is not None:
            state['blockers'] = blockers
        if pr:
            if not re.fullmatch(r'https://github.com/[^/]+/[^/]+/pull/[0-9]+', pr):
                raise StateError('PR must be a canonical GitHub pull request URL.')
            state['pr'] = pr
        invalidate(state)
    return mutate(repo, task, expected, actor, apply, author=author)

def transfer(repo, task, expected, actor, recipient, constraints, permissions, next_action, replace=False, capacity=None, author=None):
    provider(recipient)
    if not constraints or not permissions or not all(x.strip() for x in constraints + permissions) or not next_action.strip():
        raise StateError('Explicit constraints, permissions and next action are required.')
    def apply(state, current, folder):
        if state['owner'] != actor or state['status'] == 'merged':
            raise StateError('Only the current owner can hand off an active task.')
        refuse_other(state, recipient)
        if pending(state) and not replace:
            raise StateError('Transfer pending; use --replace to supersede deliberately.')
        number = state['handoff_number'] + 1
        identity = f'{task}-H{number:03d}-{uuid.uuid4().hex[:12]}'
        record = {'schema_version': 1, 'id': identity, 'number': number, 'task': task,
                  'state_revision': expected + 1, 'predecessor': state['handoff']['id'] if state['handoff'] else None,
                  'sender': actor, 'recipient': recipient, 'snapshot': current, 'plan': state['plan'],
                  'base': state['base'], 'status': state['status'], 'builders': state['builders'],
                  'criteria': state['criteria'], 'blockers': state['blockers'], 'pr': state['pr'],
                  'constraints': constraints, 'permissions': permissions, 'next_action': next_action}
        if capacity:
            record['capacity'] = capacity
        data = encoded(record)
        with (folder / (identity + '.json')).open('xb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        state['handoff_number'] = number
        state['handoff'] = {'id': identity, 'sha256': digest(data), 'recipient': recipient,
                            'acknowledged': False, 'state_revision': expected + 1}
    return mutate(repo, task, expected, actor, apply, author=author)

def acknowledge(repo, task, expected, actor, identity, claimed_digest):
    def apply(state, current, folder):
        refuse_other(state, actor)
        handoff = state['handoff']
        if not pending(state) or handoff['id'] != identity or handoff['recipient'] != actor:
            raise StateError('Transfer identity, recipient or acknowledgment state mismatch.')
        raw = (folder / (handoff['id'] + '.json')).read_bytes()
        record = json.loads(raw)
        if digest(raw) != claimed_digest or claimed_digest != handoff['sha256']:
            raise StateError('Transfer content digest mismatch.')
        if record['state_revision'] != expected or not same_snapshot(record['snapshot'], current) or not unchanged(record['plan']):
            raise StateError('Transfer revision, Git snapshot or plan is stale; request replacement.')
        state['owner'] = actor
        handoff['acknowledged'] = True
        handoff['ack_revision'] = expected + 1
        invalidate(state)
    # The transfer's own snapshot check is stricter than the authorship gate and names the right fix.
    return mutate(repo, task, expected, actor, apply, gate=False)

def takeover(repo, task, expected, actor, reason, author=None):
    provider(actor)
    if not reason or not reason.strip():
        raise StateError('Record why the user approved this takeover.')
    def apply(state, current, folder):
        refuse_other(state, actor)
        if state['owner'] == actor or state['status'] == 'merged':
            raise StateError('Takeover needs a different actor and an active task.')
        superseded = state['handoff']['id'] if pending(state) else None
        if superseded:
            state['handoff']['superseded_by'] = 'takeover'
        state.setdefault('takeovers', []).append({'revision': expected + 1, 'from': state['owner'], 'to': actor,
                                                  'reason': reason, 'superseded_handoff': superseded,
                                                  'fingerprint': current['fingerprint']})
        state['owner'] = actor
        invalidate(state)
    return mutate(repo, task, expected, actor, apply, author=author)

def inspect(repo, task, expected, actor, reviewer, report, model=None, extend='', same_model='', user_approval=''):
    reviewer = provider(reviewer)
    def apply(state, current, folder):
        owner_only(state, actor)
        if not native(reviewer):
            raise StateError('Inspections must come from native claude or codex, never a backend model.')
        data = json.loads(Path(report).read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            raise StateError('Report must be a JSON object.')
        required = {'verdict', 'reviewer', 'coverage', 'findings', 'limitations'}
        if not required <= data.keys() or data['reviewer'] != reviewer or data['verdict'] != 'APPROVED':
            raise StateError('Report must identify the reviewer and an APPROVED verdict.')
        if not isinstance(data['coverage'], list) or not data['coverage'] or not all(isinstance(x, str) and x.strip() for x in data['coverage']):
            raise StateError('Actual inspection coverage is required.')
        if not isinstance(data['findings'], list) or data['findings'] or not isinstance(data['limitations'], list):
            raise StateError('Resolve findings before recording approval; limitations must be listed.')
        if not unchanged(state['plan']):
            raise StateError('Plan changed; use revise-plan and obtain review or an explicit waiver.')
        single = review_rule(state, 'inspect', reviewer, data, model, same_model, user_approval)
        # Mixed authorship requires each provider to inspect the other contribution.
        if not single and not any(builder != reviewer for builder in state['builders']):
            raise StateError('Reviewer cannot approve only its own implementation.')
        count_round(state, current, 'inspect', report, extend)
        state['reviews'][reviewer] = {'snapshot': current, 'plan': state['plan'], 'report': reference(report), 'model': model}
        if single:
            state['reviews'][reviewer]['single_provider'] = single
        state['status'] = 'review_pending'
    return mutate(repo, task, expected, actor, apply)

def plan_check(state):
    if not unchanged(state['plan']):
        raise StateError('Plan changed; use revise-plan and obtain review or an explicit waiver.')
    if state['plan_review_waiver']:
        return
    review = state.get('plan_review')
    if not review or review['plan'] != state['plan'] or not unchanged(review['report']):
        raise StateError('Independent plan approval or explicit user waiver required.')

def approve_plan(repo, task, expected, actor, reviewer, report, model=None, extend='', same_model='', user_approval=''):
    reviewer = provider(reviewer)
    notes = []
    def apply(state, current, folder):
        owner_only(state, actor)
        data = json.loads(Path(report).read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            raise StateError('Report must be a JSON object.')
        single = review_rule(state, 'approve-plan', reviewer, data, model, same_model, user_approval)
        if not native(reviewer) or (not single and reviewer == (state.get('plan_author') or state['coordinator'])) or data.get('reviewer') != reviewer or data.get('verdict') != 'APPROVED':
            raise StateError('Plan approval must come from the other native provider.')
        if data.get('plan_sha256') != state['plan']['sha256'] or not unchanged(state['plan']):
            raise StateError('Plan approval hash does not match.')
        if not isinstance(data.get('coverage'), list) or not data['coverage'] or data.get('findings') != [] or not isinstance(data.get('limitations'), list):
            raise StateError('Approval needs coverage, no unresolved findings and listed limitations.')
        text = Path(state['plan']['path']).read_text(encoding='utf-8')
        if '[NEEDS CLARIFICATION' in text:
            raise StateError('The plan still contains [NEEDS CLARIFICATION: ...] markers; resolve them and revise the plan before approval.')
        # Textual only: a criterion is proved when some line names its id and the word proof.
        unproved = [x for x in sorted(state['criteria'])
                    if not any(re.search(r'(?<![A-Za-z0-9])' + re.escape(x) + r'(?![A-Za-z0-9])', line) and 'proof' in line.lower() for line in text.splitlines())]
        count_round(state, current, 'plan', report, extend)
        state['plan_review'] = {'reviewer': reviewer, 'plan': state['plan'], 'report': reference(report), 'model': model, 'unproved_criteria': unproved}
        if single:
            state['plan_review']['single_provider'] = single
        state['plan_review_waiver'] = ''
        notes.extend(unproved)
    result = mutate(repo, task, expected, actor, apply)
    if notes:
        print(f'WARNING: plan has no proof line for criteria: {", ".join(notes)}.', file=sys.stderr)
    return result

def revise_plan(repo, task, expected, actor, plan, waiver='', author=None, rubric=None, scope=None, criteria=None, drop_reason='', plan_author=None, plan_model=None):
    # A revised plan may carry a revised rubric, scope and criterion set; all are reviewed again together.
    replacement = reference(rubric) if rubric else None
    if replacement:
        rubric_items(replacement)
    if scope is not None and (not scope or any(not g.strip() for g in scope)):
        raise StateError('Scope globs must be non-empty.')
    if criteria is not None and (not criteria or len(set(criteria)) != len(criteria) or any(not x.strip() for x in criteria)):
        raise StateError('Provide nonempty unique acceptance criterion IDs.')
    new_author = author_of_plan(plan_author, actor)
    previous = {}
    def prepare(state):
        # The new scope is installed before the declaration, so changed files are judged against it.
        previous['scope'] = state.get('scope')
        if scope is not None:
            state['scope'] = list(scope)
    def apply(state, current, folder):
        owner_only(state, actor)
        if state.get('single_provider') and not (plan_model or '').strip():
            raise StateError('Single-provider mode: revise-plan needs --plan-model, the model that wrote the revised plan.')
        entry = {'revision': expected, 'plan': state['plan'], 'rubric': state.get('rubric'), 'review': state['plan_review'],
                 'waiver': state['plan_review_waiver'], 'scope': previous['scope'], 'criteria': sorted(state['criteria'])}
        dropped = sorted(set(state['criteria']) - set(criteria)) if criteria is not None else []
        if dropped:
            if not (drop_reason or '').strip():
                raise StateError(f'The revision drops criteria {", ".join(dropped)}; record why with --drop-reason REASON.')
            entry['dropped'] = {'criteria': dropped, 'reason': drop_reason}
        state.setdefault('plan_history', []).append(entry)
        if replacement:
            state['rubric'] = replacement
        state['plan'] = reference(plan)
        state['coordinator'] = provider(actor)
        state['plan_author'] = new_author
        if (plan_model or '').strip():
            state['plan_model'] = plan_model.strip()
        else:
            state.pop('plan_model', None)
        state['plan_review'] = None
        state['plan_review_waiver'] = waiver
        invalidate(state)
        state['status'] = 'planned'
        state['criteria'] = {x: {'passed': False, 'proof': None} for x in (criteria if criteria is not None else state['criteria'])}
    return mutate(repo, task, expected, actor, apply, author=author, prepare=prepare)

def single_provider_enter(repo, task, expected, actor, available, reason, approved_by, plan_model=None, author=None):
    # Gated, user-attested. Entering keeps earlier reviews valid; only leaving voids them.
    def apply(state, current, folder):
        owner_only(state, actor)
        if state.get('single_provider'):
            raise StateError('Single-provider mode is already on.')
        if harness(actor) != available:
            raise StateError('Only the available provider can enter single-provider mode.')
        if not state.get('plan_review') and not (plan_model or '').strip():
            raise StateError('Pass --plan-model: the plan is not yet approved, so its reviewer model must be compared with the plan model.')
        state['single_provider'] = new_mode(available, reason, approved_by, expected + 1)
        if (plan_model or '').strip():
            state['plan_model'] = plan_model.strip()
    return mutate(repo, task, expected, actor, apply, author=author)

def single_provider_leave(repo, task, expected, actor, author=None):
    def apply(state, current, folder):
        owner_only(state, actor)
        mode = state.get('single_provider')
        if not mode:
            raise StateError('Single-provider mode is not on.')
        state.setdefault('single_provider_history', []).append({**mode, 'left_revision': expected + 1, 'left_date': date.today().isoformat()})
        del state['single_provider']
        invalidate(state)
    return mutate(repo, task, expected, actor, apply, author=author)

def local(state):
    return (state.get('delivery') or {}).get('mode') == 'local'

def fresh(review, current):
    return bool(review) and same_snapshot(review['snapshot'], current) and unchanged(review['report'])

def ready_checks(state, current):
    plan_check(state)
    if current['dirty']:
        raise StateError('Commit the code before final inspection and readiness.')
    if (not state['pr'] and not local(state)) or state['blockers'] or not unchanged(state['plan']):
        raise StateError('PR (unless local delivery), unchanged plan and no blockers are required.')
    for value in state['criteria'].values():
        if not value['passed'] or not value['proof'] or not unchanged(value['proof']):
            raise StateError('Every criterion needs passing, unchanged proof.')
    for builder in independent(state):
        if not any(fresh(state['reviews'].get(x), current) for x in independent(state)[builder]):
            raise StateError('Fresh other-provider inspection required for each builder.')
    for failure in state.get('eval_failures', []):
        if not failure.get('resolved_revision') and same_snapshot(failure['snapshot'], current) \
                and failure['plan'] == state['plan'] and failure['rubric'] == state.get('rubric'):
            raise StateError(f"{failure['judge']} failed the eval of this snapshot; it needs a passing eval by the same judge.")
    if state.get('risk') == 'high':
        # Each contribution is judged by the provider that did not write it, like inspection.
        evals = state.get('evals') or {}
        for builder, wanted in independent(state).items():
            if not any(fresh(evals.get(x), current) and evals[x]['plan'] == state['plan'] and unchanged(evals[x]['rubric']) for x in wanted):
                raise StateError('High-risk task needs a fresh passing rubric eval for each builder (eval command).')

def independent(state):
    # A native builder needs the other provider; backend-built work needs any native one. In single-provider
    # mode the available provider also counts (its review already passed review_rule); an earlier other-provider one still does.
    mode = state.get('single_provider')
    if mode:
        return {b: sorted({'claude', 'codex'} if not native(b) else {'claude' if b == 'codex' else 'codex', mode['available']}) for b in state['builders']}
    return {b: [('claude' if b == 'codex' else 'codex')] if native(b) else ['claude', 'codex'] for b in state['builders']}

def count_round(state, current, kind, report, extend=''):
    # Every review round counts once against the plan's budget, whatever its verdict.
    data = json.loads(Path(report).read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('verdict') not in ('APPROVED', 'REVISE', 'BLOCKED') or not isinstance(data.get('findings'), list):
        raise StateError('Round report needs a verdict and a findings list.')
    refuse_other(state, provider(data.get('reviewer')))
    evidence = reference(report)
    if data['verdict'] != 'APPROVED':
        if kind == 'plan':
            state['plan_review'] = None
            # A waiver given while the plan was unreviewed does not survive the reviewer rejecting it.
            if state.get('plan_review_waiver'):
                state.setdefault('plan_history', []).append({'revision': state['revision'] + 1, 'voided_waiver': state['plan_review_waiver'], 'round': evidence})
                state['plan_review_waiver'] = ''
        invalidate(state)
    rounds = state.setdefault('rounds', [])
    plan_sha = state['plan']['sha256']
    # One review execution = one report for one kind, snapshot and plan; registering it twice counts once.
    if any(r['kind'] == kind and r['report']['sha256'] == evidence['sha256'] and r.get('fingerprint') == current['fingerprint']
           and r.get('plan_sha256', plan_sha) == plan_sha for r in rounds):
        return
    used = sum(1 for r in rounds if r['kind'] == kind)
    limit = (state.get('budget') or {}).get(kind, 3 if kind == 'plan' else 2)
    if used >= limit and not (extend or '').strip():
        raise StateError(f'The {kind} review budget ({limit}) is used; pass --extend REASON to go further.')
    rounds.append({'kind': kind, 'number': used + 1, 'verdict': data['verdict'], 'reviewer': provider(data.get('reviewer')),
                   'report': evidence, 'fingerprint': current['fingerprint'], 'plan_sha256': plan_sha, 'extend': extend or None}
                  | ({'single_provider': {'reason': state['single_provider']['reason'], 'since': state['single_provider']['date']}} if state.get('single_provider') else {}))

def review_round(repo, task, expected, actor, kind, report, extend=''):
    # For REVISE/BLOCKED reports; approve-plan and inspect count their own round.
    def apply(state, current, folder):
        owner_only(state, actor)
        if kind not in ('plan', 'inspect'):
            raise StateError('Round kind is plan or inspect.')
        count_round(state, current, kind, report, extend)
    return mutate(repo, task, expected, actor, apply)

def finding(repo, task, expected, actor, ident, severity, builder, model, report, correct=''):
    # Attributes a confirmed finding from a recorded review round to the builder and model that wrote it.
    # It counts once per task and id; a later report of the same finding is not a second mistake.
    key = provider(builder)
    if severity not in ('high', 'medium', 'low', 'retracted'):
        raise StateError('Severity is high, medium, low or retracted.')
    def apply(state, current, folder):
        owner_only(state, actor)
        if not any(e['builder'] == key and e['model'] == model for e in state.get('ledger', [])):
            raise StateError('Attribute findings only to a builder and model recorded in this task ledger.')
        evidence = reference(report)
        if not any(r['report']['sha256'] == evidence['sha256'] for r in state.get('rounds', [])):
            raise StateError('The report must be a recorded review round (round command).')
        earlier = [f for f in state.get('findings', []) if f['id'] == ident]
        if earlier and (earlier[-1]['severity'] == severity or not (correct or '').strip()):
            raise StateError('This finding is already recorded; change its severity only with --correct REASON.')
        if not earlier and (severity == 'retracted' or correct):
            raise StateError('Only a recorded finding can be corrected or retracted.')
        if severity != 'retracted':
            listed = [f for f in json.loads(Path(report).read_text(encoding='utf-8'))['findings'] if isinstance(f, dict) and f.get('id') == ident]
            if not listed or listed[0].get('severity', severity) != severity:
                raise StateError('The report must contain this finding id with the same severity.')
        record = {'id': ident, 'severity': severity, 'builder': key, 'model': model, 'report': evidence, 'revision': expected + 1}
        if earlier:
            record['corrects'] = {'severity': earlier[-1]['severity'], 'reason': correct}
        state.setdefault('findings', []).append(record)
    # mutate publishes the finding to the roster after the state commit (see sync_roster).
    return mutate(repo, task, expected, actor, apply)

def evaluate(repo, task, expected, actor, judge, model, report, same_model='', user_approval=''):
    # Scores come from the judge; the rubric, its thresholds and decisive cases come from the reviewed plan.
    judge = provider(judge)
    def apply(state, current, folder):
        owner_only(state, actor)
        if not native(judge) or (not state.get('single_provider') and not any(builder != judge for builder in state['builders'])):
            raise StateError('The judge must be native claude or codex and not the only builder.')
        rubric = state.get('rubric')
        if not rubric or not unchanged(rubric):
            raise StateError('Evaluate against the rubric recorded at init (--rubric); it is missing or changed.')
        data = json.loads(Path(report).read_text(encoding='utf-8'))
        if not isinstance(data, dict) or data.get('judge') != judge or not isinstance(data.get('results'), list):
            raise StateError('The eval report must be a JSON object naming this judge with a results list.')
        single = review_rule(state, 'eval', judge, data, model, same_model, user_approval)
        results = {r.get('id'): r for r in data['results'] if isinstance(r, dict)}
        failed = []
        for item in rubric_items(rubric):
            result = results.get(item['id'])
            score = result.get('score') if result else None
            if not isinstance(score, (int, float)) or isinstance(score, bool) or not math.isfinite(score) \
                    or not str(result.get('evidence', '')).strip():
                raise StateError(f'Rubric item {item["id"]} needs a numeric score and evidence.')
            if score < item['threshold']:
                failed.append(f'Eval failed on {item["id"]}: {score} < {item["threshold"]}.')
        if not unchanged(state['plan']):
            raise StateError('Plan changed; use revise-plan and obtain review or an explicit waiver.')
        failures = state.setdefault('eval_failures', [])
        if failed:
            # A complete failing eval is evidence too: it is recorded, voids every earlier passing eval and
            # blocks readiness on this snapshot until the same judge passes it.
            failures.append({'judge': judge, 'model': model, 'snapshot': current, 'plan': state['plan'], 'rubric': rubric,
                             'report': reference(report), 'failed': failed, 'revision': state['revision'] + 1})
            state.pop('evals', None)
            if state['status'] == 'ready':
                state['status'] = 'review_pending'
            outcome.extend(failed)
            return
        for failure in failures:
            if failure['judge'] == judge and not failure.get('resolved_revision') and same_snapshot(failure['snapshot'], current) \
                    and failure['plan'] == state['plan'] and failure['rubric'] == rubric:
                failure['resolved_revision'] = state['revision'] + 1
        state.setdefault('evals', {})[judge] = {'model': model, 'snapshot': current, 'plan': state['plan'],
                                                 'rubric': rubric, 'report': reference(report)}
        if single:
            state['evals'][judge]['single_provider'] = single
    outcome = []
    result = mutate(repo, task, expected, actor, apply)
    if outcome:
        raise StateError(' '.join(outcome) + f' Recorded at revision {result["revision"]}; earlier evals voided.')
    return result

def rubric_items(ref):
    items = json.loads(Path(ref['path']).read_text(encoding='utf-8'))
    if not isinstance(items, list) or not items:
        raise StateError('A rubric is a non-empty JSON list.')
    for item in items:
        if not isinstance(item, dict) or not str(item.get('id', '')).strip() or not str(item.get('criterion', '')).strip() \
                or not isinstance(item.get('threshold'), (int, float)) or isinstance(item.get('threshold'), bool) \
                or not math.isfinite(item['threshold']):
            raise StateError('Each rubric item needs an id, a criterion and a numeric threshold.')
    if len({i['id'] for i in items}) != len(items):
        raise StateError('Rubric item ids must be unique.')
    return items

def brief(state, folder):
    # Compact, stable resume packet: read this instead of replaying history.
    open_criteria = [k for k, v in state['criteria'].items() if not v['passed']]
    review = state.get('plan_review')
    ledger = state.get('ledger', [])
    builders = sorted({e['builder'] + '/' + e['model'] for e in ledger})
    in_ledger = {e['builder'] for e in ledger}
    builders += [b for b in state['builders'] if b not in in_ledger]
    lines = [f"{state['task']} status={state['status']} owner={state['owner']} rev={state['revision']} risk={state.get('risk', 'normal')}",
             f"plan: {state['plan']['path']} sha={state['plan']['sha256'][:12]} "
             + (f"approved by {review['reviewer']}" if review else f"waiver: {state['plan_review_waiver']}" if state['plan_review_waiver'] else 'NOT approved'),
             f"open criteria: {', '.join(open_criteria) or 'none'}",
             f"builders: {', '.join(builders)}",
             f"scope: {', '.join(state.get('scope', [])) or 'unrestricted'}",
             f"blockers: {'; '.join(state['blockers']) or 'none'}"]
    lines += [f"attribution warning: {e['attribution']}; integration builders: claude, codex"
              for e in state.get('ledger', []) if e.get('attribution', '').startswith('approximate:')]
    if state.get('adoption'):
        lines.append(f"unknown authorship (adopted): {state['adoption']['reason']}")
    handoff = state['handoff']
    if handoff:
        record = json.loads((folder / (handoff['id'] + '.json')).read_text(encoding='utf-8'))
        status = 'superseded' if handoff.get('superseded_by') else 'acknowledged' if handoff['acknowledged'] else 'PENDING'
        lines.append(f"handoff {handoff['id']} -> {handoff['recipient']} ({status}); next: {record['next_action']}")
        lines.append(f"constraints: {'; '.join(record['constraints'])}")
    rounds = state.get('rounds', [])
    if rounds:
        lines.append('rounds: ' + ', '.join(f"{r['kind']}{r['number']} {r['verdict']}" for r in rounds))
    latest = {f['id']: f for f in state.get('findings', [])}
    for f in latest.values():
        if f['severity'] in ('high', 'medium', 'low'):
            lines.append(f"finding {f['id']} {f['severity']} by {f['builder']}/{f['model']}")
    label = review_label(state)
    return '\n'.join(([label] if label else []) + lines)

def who(state):
    touched = {}
    for entry in state.get('ledger', []):
        touched.setdefault(f"{entry['builder']}/{entry['model']}", set()).update(entry['files'])
    lines = [f"{name}: {', '.join(sorted(files)) or '(no files)'}" for name, files in sorted(touched.items())]
    # A missing (legacy) ledger never hides a known builder.
    in_ledger = {e['builder'] for e in state.get('ledger', [])}
    lines += [f'{b}: (recorded builder, no ledger)' for b in state['builders'] if b not in in_ledger]
    lines += [f"attribution warning: {e['attribution']}; integration builders: claude, codex"
              for e in state.get('ledger', []) if e.get('attribution', '').startswith('approximate:')]
    if state.get('adoption'):
        lines.append(f"unknown authorship (adopted): {state['adoption']['reason']}")
    return '\n'.join(lines) or 'No authorship recorded.'

def roster_summary():
    summary = {}
    for entry in roster():
        row = summary.setdefault(entry.get('model'), {'tasks': set(), 'findings': {}, 'high': 0, 'medium': 0, 'low': 0})
        task = (entry.get('repo_id'), entry.get('task'))
        row['tasks'].add(task)
        if entry.get('kind') == 'finding':
            row['findings'][task + (entry.get('id'),)] = entry.get('severity')
    for row in summary.values():
        for severity in row['findings'].values():
            if severity in ('high', 'medium', 'low'):
                row[severity] += 1
    return '\n'.join(f"{model}: {len(r['tasks'])} tasks, {r['high']} high, {r['medium']} medium, {r['low']} low"
                     + (' BENCHED' if bench_status(model) else '') for model, r in sorted(summary.items())) or 'Roster empty.'

def announce(state):
    # stdout carries the JSON state; the label goes to stderr so it is seen but never breaks parsing.
    if state.get('review_label'):
        print(state['review_label'], file=sys.stderr)
    return state

def ready(repo, task, expected, actor):
    def apply(state, current, folder):
        owner_only(state, actor); ready_checks(state, current); state['status'] = 'ready'
        if review_label(state):
            state['review_label'] = review_label(state)
    return announce(mutate(repo, task, expected, actor, apply))

def merged(repo, task, expected, actor):
    def apply(state, current, folder):
        owner_only(state, actor); ready_checks(state, current)
        if review_label(state):
            state['review_label'] = review_label(state)
        if local(state):
            target = state['delivery']['target']
            target_head = local_branch(repo, target)
            contained = subprocess.run(['git', '-C', str(repo), 'merge-base', '--is-ancestor', current['head'], target_head], capture_output=True)
            if contained.returncode != 0:
                raise StateError(f'Local target {target} does not contain this head.')
            state['status'] = 'merged'; state['merge'] = {'mode': 'local', 'target': target, 'target_head': target_head, 'head': current['head']}
            return
        result = subprocess.run(['gh', 'pr', 'view', state['pr'], '--json', 'state,mergedAt,mergeCommit,headRefOid'],
                                check=True, capture_output=True, text=True)
        data = json.loads(result.stdout)
        if data.get('state') != 'MERGED' or not data.get('mergedAt') or not data.get('mergeCommit', {}).get('oid') or data.get('headRefOid') != current['head']:
            raise StateError('GitHub must confirm this exact head was merged.')
        state['status'] = 'merged'; state['merge'] = data
    return announce(mutate(repo, task, expected, actor, apply))

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['init', 'show', 'update', 'handoff', 'ack', 'takeover', 'inspect', 'approve-plan', 'revise-plan', 'round', 'finding', 'eval', 'ready', 'merged', 'roster-sync', 'single-provider-enter', 'single-provider-leave'])
    parser.add_argument('--repo', required=True); parser.add_argument('--task', required=True)
    parser.add_argument('--expected', type=int); parser.add_argument('--actor')
    parser.add_argument('--base', help='Existing ancestor commit when adopting work already started.'); parser.add_argument('--owner'); parser.add_argument('--plan'); parser.add_argument('--criterion', action='append')
    parser.add_argument('--unreviewed-plan', default='', help='Explicit user waiver reason, never model approval.')
    parser.add_argument('--local-target', help='Local branch that receives the merge when the repository has no GitHub remote.')
    parser.add_argument('--status'); parser.add_argument('--pass', dest='passed'); parser.add_argument('--proof')
    parser.add_argument('--blocker', action='append'); parser.add_argument('--clear-blockers', action='store_true')
    parser.add_argument('--pr'); parser.add_argument('--builder', help='Author of code changed since the last record.'); parser.add_argument('--to', dest='recipient')
    parser.add_argument('--constraint', action='append'); parser.add_argument('--permission', action='append')
    parser.add_argument('--next', dest='next_action'); parser.add_argument('--replace', action='store_true')
    parser.add_argument('--capacity', action='append', help='Capacity note, e.g. "claude weekly 90%%, resets Oct 31".')
    parser.add_argument('--reason', help='Why the user approved a takeover.')
    parser.add_argument('--handoff', dest='identity'); parser.add_argument('--digest'); parser.add_argument('--reviewer'); parser.add_argument('--report')
    parser.add_argument('--model', help='Model behind --builder, --reviewer or --judge, e.g. claude-opus-5-5.')
    parser.add_argument('--outside-scope', help='Why a declared change leaves the plan scope.'); parser.add_argument('--override', help="User's approval to use a benched model.")
    parser.add_argument('--scope', action='append', help='Repo-relative glob the work may touch (init; revise-plan replaces scope).')
    parser.add_argument('--risk', default='normal', choices=['normal', 'high']); parser.add_argument('--budget-plan', type=int, default=3); parser.add_argument('--budget-inspect', type=int, default=2)
    parser.add_argument('--kind', choices=['plan', 'inspect']); parser.add_argument('--extend', default='', help='Why another review round beyond the budget.')
    parser.add_argument('--id', dest='ident'); parser.add_argument('--severity'); parser.add_argument('--judge')
    parser.add_argument('--rubric', help='Reviewed rubric JSON [{id, criterion, threshold}] for a high-risk task (init; revise-plan replaces rubric).')
    parser.add_argument('--correct', default='', help='Why a recorded finding changes severity or is retracted.')
    parser.add_argument('--adopt', action='append', help='BUILDER=MODEL that wrote work existing before init (repeatable).')
    parser.add_argument('--adopt-unknown', default='', help='Why the authors of pre-existing work are unknown (both providers must inspect).')
    parser.add_argument('--plan-author', choices=['claude', 'codex'], help='Native provider that wrote the plan (init; revise-plan). Default: the owner/actor.')
    parser.add_argument('--single-provider', choices=['claude', 'codex'], help='Provider still available when the other is not (init; single-provider-enter). Needs --reason, --approved-by, --plan-model.')
    parser.add_argument('--approved-by', default='', help="The user's approval for single-provider mode (free-text attestation).")
    parser.add_argument('--plan-model', help='Model that wrote the plan (init, revise-plan, single-provider-enter).')
    parser.add_argument('--same-model', default='', help='Why a fresh session of the builder model reviews in single-provider mode (needs --user-approval).')
    parser.add_argument('--user-approval', default='', help="The user's approval text for --same-model.")
    parser.add_argument('--drop-reason', default='', help='Why revise-plan drops acceptance criteria.')
    parser.add_argument('--brief', action='store_true'); parser.add_argument('--who', action='store_true'); parser.add_argument('--roster', action='store_true')
    args = parser.parse_args(argv)
    author = {'builder': args.builder, 'model': args.model, 'outside': args.outside_scope, 'override': args.override} if args.builder else None
    try:
        if args.command == 'init':
            if not args.owner or not args.plan: raise StateError('--owner and --plan required.')
            result = init(args.repo,args.task,args.owner,args.plan,args.criterion,args.unreviewed_plan,args.base,args.local_target,args.scope,args.risk,args.budget_plan,args.budget_inspect,args.rubric,args.adopt,args.adopt_unknown,args.plan_author,args.single_provider,args.reason or '',args.approved_by,args.plan_model)
        elif args.command == 'roster-sync':
            print(f'{sync_roster(args.repo, load(args.repo, args.task, bind=False))} roster event(s) appended.'); return 0
        elif args.command == 'show':
            if args.roster: print(roster_summary()); return 0
            result = load(args.repo,args.task,bind=False)
            if args.brief: print(brief(result,location(args.repo,args.task))); return 0
            if args.who: print(who(result)); return 0
        else:
            if args.expected is None or not args.actor: raise StateError('--expected and --actor required.')
            base = (args.repo,args.task,args.expected,args.actor)
            if args.command == 'update':
                if args.clear_blockers and args.blocker: raise StateError('Choose blockers or --clear-blockers.')
                result = update(*base,args.status,args.passed,args.proof,[] if args.clear_blockers else args.blocker,args.pr,author)
            elif args.command == 'handoff':
                if not args.recipient or not args.next_action: raise StateError('--to and --next required.')
                result = transfer(*base,args.recipient,args.constraint,args.permission,args.next_action,args.replace,args.capacity,author)
            elif args.command == 'ack':
                if not args.identity or not args.digest: raise StateError('--handoff and --digest required.')
                result = acknowledge(*base,args.identity,args.digest)
            elif args.command == 'takeover':
                result = takeover(*base,args.reason,author)
            elif args.command == 'revise-plan':
                if not args.plan: raise StateError('--plan required.')
                result = revise_plan(*base,args.plan,args.unreviewed_plan,author,args.rubric,args.scope,args.criterion,args.drop_reason,args.plan_author,args.plan_model)
            elif args.command in ('inspect', 'approve-plan'):
                if not args.reviewer or not args.report: raise StateError('--reviewer and --report required.')
                operation = inspect if args.command == 'inspect' else approve_plan
                result = operation(*base,args.reviewer,args.report,args.model,args.extend,args.same_model,args.user_approval)
            elif args.command == 'round':
                if not args.kind or not args.report: raise StateError('--kind and --report required.')
                result = review_round(*base,args.kind,args.report,args.extend)
            elif args.command == 'finding':
                if not (args.ident and args.severity and args.builder and args.model and args.report): raise StateError('--id, --severity, --builder, --model and --report required.')
                result = finding(*base,args.ident,args.severity,args.builder,args.model,args.report,args.correct)
            elif args.command == 'eval':
                if not (args.judge and args.model and args.report): raise StateError('--judge, --model and --report required.')
                result = evaluate(*base,args.judge,args.model,args.report,args.same_model,args.user_approval)
            elif args.command == 'single-provider-enter':
                if not args.single_provider: raise StateError('--single-provider required.')
                result = single_provider_enter(*base,args.single_provider,args.reason or '',args.approved_by,args.plan_model,author)
            elif args.command == 'single-provider-leave': result = single_provider_leave(*base,author)
            elif args.command == 'ready': result = ready(*base)
            else: result = merged(*base)
        print(json.dumps(result,indent=2)); return 0
    except (StateError, OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        print(f'ERROR: {exc}',file=sys.stderr); return 1

if __name__ == '__main__':
    raise SystemExit(main())
