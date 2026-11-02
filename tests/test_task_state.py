"""Behavioral regressions in disposable Git repos. No model calls or live GitHub writes."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/mohit-engineering-loop/scripts/task_state.py'
spec = importlib.util.spec_from_file_location('task_state', SCRIPT)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

def A(builder, model='fixture-model'):
    return {'builder': builder, 'model': model}

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.parent = Path(self.tmp.name).resolve(); self.repo = self.parent/'repo'; self.repo.mkdir()
        # Never touch the real cross-project roster.
        roster = patch.dict(os.environ, {'MEL_ROSTER': str(self.parent/'roster.jsonl')}); roster.start(); self.addCleanup(roster.stop)
        self.run_git('init','-b','codex/test')
        self.run_git('config','user.name','Test'); self.run_git('config','user.email','test@example.invalid')
        self.plan = self.repo/'plan.md'; self.plan.write_text('A1 and A2 must work.\n')
        self.run_git('add','.'); self.run_git('commit','-m','fixture baseline')
        self.proof = self.parent/'proof.txt'; self.proof.write_text('A1 and A2 independently verified in fixture')
        self.report = self.parent/'inspection.json'
        self.state = m.init(self.repo,'MEL-001','codex',self.plan,['A1','A2'],'User explicitly allowed draft implementation without plan review.')
    def run_git(self,*args):
        return subprocess.run(['git','-C',str(self.repo),*args],check=True,capture_output=True,text=True).stdout
    def current(self): return m.load(self.repo,'MEL-001')
    def update(self, **kwargs):
        state=self.current(); return m.update(self.repo,'MEL-001',state['revision'],state['owner'],**kwargs)
    def report_for(self,reviewer='claude',**kwargs):
        data={'verdict':'APPROVED','reviewer':reviewer,'coverage':['A1','A2'],'findings':[],'limitations':['Fixture report; not a real model review.']}
        data.update(kwargs); self.report.write_text(json.dumps(data)); return self.report
    def inspect(self,reviewer='claude',**kwargs):
        self.report_for(reviewer,**kwargs)
        state=self.current(); return m.inspect(self.repo,'MEL-001',state['revision'],state['owner'],reviewer,self.report)
    def prepare(self):
        self.update(pr='https://github.com/example/project/pull/1')
        self.update(passed='A1',proof=self.proof); self.update(passed='A2',proof=self.proof)
        self.inspect()
    def ready(self):
        state=self.current();return m.ready(self.repo,'MEL-001',state['revision'],state['owner'])
    def handoff(self,recipient='claude',replace=False,builder=None):
        state=self.current(); return m.transfer(self.repo,'MEL-001',state['revision'],state['owner'],recipient,['No external writes'],['Read only'],'Inspect A2',replace,author=A(builder) if builder else None)
    def ack(self,state=None,actor='claude',identity=None,sha=None):
        state=state or self.current(); handoff=state['handoff']
        return m.acknowledge(self.repo,'MEL-001',state['revision'],actor,identity or handoff['id'],sha or handoff['sha256'])

    def test_init_rejects_duplicate_task_without_overwrite(self):
        with self.assertRaises(m.StateError): m.init(self.repo,'MEL-001','claude',self.plan,['A1'])
        self.assertEqual(self.current()['revision'],1)
    def test_invalid_task_ids_and_duplicate_criteria(self):
        for task in ('../../bad','MEL-1','MEL-001/child'):
            with self.assertRaises(m.StateError):m.location(self.repo,task)
        with self.assertRaises(m.StateError):m.init(self.repo,'MEL-002','codex',self.plan,['A1','A1'])
    def test_update_accepts_owner_and_rejects_stale_or_foreign_actor(self):
        self.update(status='implementing')
        for revision, actor in ((1,'codex'),(2,'claude')):
            with self.assertRaises(m.StateError):m.update(self.repo,'MEL-001',revision,actor,status='blocked')
        self.assertEqual(self.current()['revision'],2)
    def test_no_plan_review_requires_explicit_waiver(self):
        m.init(self.repo,'MEL-002','codex',self.plan,['A1'])
        with self.assertRaises(m.StateError):m.update(self.repo,'MEL-002',1,'codex',status='implementing')
        self.report_for(plan_sha256=m.reference(self.plan)['sha256'])
        m.approve_plan(self.repo,'MEL-002',1,'codex','claude',self.report)
        result=m.update(self.repo,'MEL-002',2,'codex',status='implementing')
        self.assertEqual(result['status'],'implementing')
    def test_plan_approval_rejects_same_provider_and_wrong_hash(self):
        self.report_for('codex',plan_sha256=m.reference(self.plan)['sha256'])
        with self.assertRaises(m.StateError):m.approve_plan(self.repo,'MEL-001',1,'codex','codex',self.report)
        self.report_for(plan_sha256='wrong')
        with self.assertRaises(m.StateError):m.approve_plan(self.repo,'MEL-001',1,'codex','claude',self.report)
    def test_cooperative_lock_rejects_second_writer(self):
        with m.locked(m.location(self.repo,'MEL-001')):
            with self.assertRaises(m.StateError):self.update(status='blocked')
        self.update(status='blocked')
    def test_competing_processes_cannot_both_claim_revision(self):
        command=[sys.executable,'-B',str(SCRIPT),'update','--repo',str(self.repo),'--task','MEL-001','--expected','1','--actor','codex','--status','blocked']
        first=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        second=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        first.communicate(timeout=30);second.communicate(timeout=30)
        self.assertEqual(sorted([first.returncode,second.returncode]),[0,1]);self.assertEqual(self.current()['revision'],2)
    def test_atomic_failure_keeps_prior_state(self):
        before=(m.location(self.repo,'MEL-001')/'state.json').read_bytes()
        with patch.object(m.os,'replace',side_effect=OSError('simulated disk failure')):
            with self.assertRaises(OSError): self.update(status='blocked')
        self.assertEqual((m.location(self.repo,'MEL-001')/'state.json').read_bytes(),before)
        self.assertFalse(list(m.location(self.repo,'MEL-001').glob('*.tmp')))
    def test_handoff_round_trip_freezes_sender_and_changes_owner(self):
        state=self.handoff()
        self.assertIn('MEL-001-H001-',state['handoff']['id'])
        with self.assertRaises(m.StateError):self.update(status='blocked')
        result=self.ack(state)
        self.assertEqual(result['owner'],'claude');self.assertEqual(result['revision'],3)
        with self.assertRaises(m.StateError):self.ack(result)
        new=self.handoff('codex:next-session')
        self.assertIn('-H002-',new['handoff']['id'])
    def test_handoff_rejects_wrong_identity_recipient_and_digest(self):
        state=self.handoff()
        for kwargs in ({'identity':'other'}, {'actor':'codex'}, {'sha':'wrong'}):
            with self.assertRaises(m.StateError): self.ack(state,**kwargs)
    def test_tampered_handoff_is_rejected(self):
        state=self.handoff();path=m.location(self.repo,'MEL-001')/(state['handoff']['id']+'.json')
        path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaises(m.StateError):self.ack(state)
    def test_stale_git_handoff_requires_explicit_replacement(self):
        state=self.handoff();(self.repo/'new.py').write_text('change')
        with self.assertRaises(m.StateError):self.ack(state)
        with self.assertRaises(m.StateError):self.handoff(builder='codex')
        new=self.handoff(replace=True,builder='codex');self.ack(new)
        self.assertEqual(len(list(m.location(self.repo,'MEL-001').glob('MEL-001-H*.json'))),2)
    def test_plan_change_invalidates_handoff(self):
        state=self.handoff(); self.plan.write_text('Different accepted scope')
        with self.assertRaises(m.StateError):self.ack(state)
    def test_branch_change_rejected(self):
        self.run_git('switch','-c','claude/other')
        with self.assertRaises(m.StateError):self.update(status='blocked')
    def test_state_writes_do_not_invalidate_git_fingerprint(self):
        before=m.snapshot(self.repo);self.update(status='blocked');self.assertEqual(before,m.snapshot(self.repo))
    def test_ready_success_and_actual_github_merge_readback(self):
        self.prepare();self.assertEqual(self.ready()['status'],'ready')
        current=self.current();head=m.snapshot(self.repo)['head']
        payload={'state':'MERGED','mergedAt':'2026-10-22T12:00:00Z','mergeCommit':{'oid':'abc'},'headRefOid':head}
        original=subprocess.run
        with patch.object(m.subprocess,'run',wraps=original) as run:
            def fake(args,**kwargs):
                if args[0]=='gh':return subprocess.CompletedProcess(args,0,json.dumps(payload),'')
                return original(args,**kwargs)
            run.side_effect=fake
            result=m.merged(self.repo,'MEL-001',current['revision'],current['owner'])
        self.assertEqual(result['status'],'merged')
        with self.assertRaises(m.StateError):self.update(status='implementing')
    def test_unmerged_pr_never_becomes_merged(self):
        self.prepare();state=self.ready();original=subprocess.run
        def fake(args,**kwargs):
            if args[0]=='gh':return subprocess.CompletedProcess(args,0,json.dumps({'state':'OPEN'}),'')
            return original(args,**kwargs)
        with patch.object(m.subprocess,'run',side_effect=fake):
            with self.assertRaises(m.StateError):m.merged(self.repo,'MEL-001',state['revision'],'codex')
        self.assertEqual(self.current()['status'],'ready')
    def test_readiness_rejects_incomplete_blocked_or_unreviewed(self):
        with self.assertRaises(m.StateError):self.ready()
        self.prepare();self.update(blockers=['review quota'])
        with self.assertRaises(m.StateError):self.ready()
    def test_builder_cannot_self_approve_and_material_findings_rejected(self):
        with self.assertRaises(m.StateError):self.inspect('codex')
        with self.assertRaises(m.StateError):self.inspect(findings=[{'severity':'high'}])
        with self.assertRaises(m.StateError):self.inspect(coverage=[])
    def test_report_or_proof_changes_invalidate_readiness(self):
        self.prepare();self.report.write_text('{}')
        with self.assertRaises(m.StateError):self.ready()
        self.inspect();self.proof.write_text('different evidence')
        with self.assertRaises(m.StateError):self.ready()
    def test_code_or_plan_changes_invalidate_inspection(self):
        self.prepare();(self.repo/'code.py').write_text('print(1)')
        with self.assertRaises(m.StateError):self.ready()
        self.run_git('add','code.py');self.run_git('commit','-m','fixture change')
        with self.assertRaises(m.StateError):self.ready()
        self.update(author=A('codex'));self.inspect();self.plan.write_text('new contract')
        with self.assertRaises(m.StateError):self.ready()
    def test_mixed_authorship_needs_both_reviewers(self):
        self.update(author=A('claude'));self.prepare()
        with self.assertRaises(m.StateError):self.ready()
        other_report=self.parent/'codex-report.json'
        self.report_for('codex');other_report.write_bytes(self.report.read_bytes())
        self.report_for('claude')
        state=self.current();m.inspect(self.repo,'MEL-001',state['revision'],'codex','codex',other_report)
        self.assertEqual(self.ready()['status'],'ready')
    def test_cli_rejects_missing_fields_without_traceback(self):
        for command in ('ack','handoff','inspect'):
            result=subprocess.run([sys.executable,'-B',str(SCRIPT),command,'--repo',str(self.repo),'--task','MEL-001','--expected','1','--actor','codex'],capture_output=True,text=True)
            self.assertEqual(result.returncode,1);self.assertNotIn('Traceback',result.stderr)

    def test_plan_revision_preserves_task_identity_and_clears_proof(self):
        self.prepare()
        old=self.current()
        self.plan.write_text('Revised plan with same criterion IDs')
        with self.assertRaisesRegex(m.StateError,'declare its author'):m.revise_plan(self.repo,'MEL-001',old['revision'],'codex',self.plan)
        result=m.revise_plan(self.repo,'MEL-001',old['revision'],'codex',self.plan,author=A('codex'))
        self.assertEqual(result['task'],'MEL-001')
        self.assertEqual(result['plan_history'][0]['plan'],old['plan'])
        self.assertFalse(any(x['passed'] for x in result['criteria'].values()))
        self.assertEqual(result['reviews'],{})
        with self.assertRaises(m.StateError):self.update(status='implementing')

    def test_json_array_cannot_be_review_evidence(self):
        self.report.write_text('[]')
        with self.assertRaises(m.StateError):m.inspect(self.repo,'MEL-001',1,'codex','claude',self.report)
        with self.assertRaises(m.StateError):m.approve_plan(self.repo,'MEL-001',1,'codex','claude',self.report)

    def test_adopting_existing_work_preserves_original_baseline(self):
        initial=m.snapshot(self.repo)['head']
        (self.repo/'code.py').write_text('print(1)')
        self.run_git('add','code.py');self.run_git('commit','-m','fixture work before tracker')
        result=m.init(self.repo,'MEL-002','codex',self.plan,['A1'],baseline=initial,adopt=['codex=fixture-model'])
        self.assertEqual(result['base'],initial)
        self.assertNotEqual(result['base'],m.snapshot(self.repo)['head'])

    def test_committing_handoff_metadata_does_not_stale_transfer(self):
        state=self.handoff()
        self.run_git('add','.mel');self.run_git('commit','-m','fixture checkpoint')
        self.assertEqual(self.ack(state)['owner'],'claude')

    def test_metadata_commit_preserves_review_but_code_commit_does_not(self):
        self.prepare()
        self.run_git('add','.mel');self.run_git('commit','-m','fixture task evidence')
        self.assertEqual(self.ready()['status'],'ready')
        (self.repo/'code.py').write_text('real code change')
        self.run_git('add','code.py');self.run_git('commit','-m','fixture code')
        with self.assertRaises(m.StateError):self.ready()

    def test_autocrlf_checkout_preserves_handoff_digest(self):
        self.run_git('config','core.autocrlf','true')
        state=self.handoff()
        path=m.location(self.repo,'MEL-001')/(state['handoff']['id']+'.json')
        original=path.read_bytes()
        self.run_git('add','.mel');self.run_git('commit','-m','fixture immutable transfer')
        path.unlink()
        self.run_git('checkout','--',path.relative_to(self.repo).as_posix())
        self.assertEqual(path.read_bytes(),original)
        self.assertEqual(self.ack(state)['owner'],'claude')

    # MEL-002: authorship gate, backends, takeover, unbound show, local delivery.
    def commit_code(self,text='changed'):
        (self.repo/'code.py').write_text(text);self.run_git('add','code.py');self.run_git('commit','-m','fixture code')
    def test_undeclared_code_change_after_handoff_cannot_self_review(self):
        self.update(pr='https://github.com/example/project/pull/1')
        state=self.ack(self.handoff());self.commit_code('claude edit')
        with self.assertRaisesRegex(m.StateError,'declare its author'):m.update(self.repo,'MEL-001',state['revision'],'claude',passed='A1',proof=self.proof)
        state=m.update(self.repo,'MEL-001',state['revision'],'claude',author=A('claude'))
        self.assertEqual(state['builders'],['codex','claude'])
        for criterion in ('A1','A2'):state=m.update(self.repo,'MEL-001',state['revision'],'claude',passed=criterion,proof=self.proof)
        self.report_for('claude');state=m.inspect(self.repo,'MEL-001',state['revision'],'claude','claude',self.report)
        with self.assertRaisesRegex(m.StateError,'Fresh other-provider'):m.ready(self.repo,'MEL-001',state['revision'],'claude')
        other=self.parent/'codex-report.json';other.write_text(json.dumps({'verdict':'APPROVED','reviewer':'codex','coverage':['A1'],'findings':[],'limitations':[]}))
        state=m.inspect(self.repo,'MEL-001',state['revision'],'claude','codex',other)
        self.assertEqual(m.ready(self.repo,'MEL-001',state['revision'],'claude')['status'],'ready')
    def test_review_binds_to_snapshot_even_without_gate(self):
        self.prepare();self.commit_code()
        with self.assertRaisesRegex(m.StateError,'Fresh other-provider'):m.ready_checks(self.current(),m.snapshot(self.repo))
    def test_metadata_commit_does_not_trip_authorship_gate(self):
        self.update(status='blocked');self.run_git('add','.mel');self.run_git('commit','-m','fixture metadata')
        self.assertEqual(self.update(status='implementing')['status'],'implementing')
    def test_legacy_state_without_recorded_fingerprint_still_loads(self):
        path=m.location(self.repo,'MEL-001')/'state.json';state=json.loads(path.read_text())
        del state['recorded_fingerprint'];path.write_bytes(m.encoded(state));self.commit_code()
        self.assertEqual(self.current()['task'],'MEL-001')
        with self.assertRaisesRegex(m.StateError,'declare its author'):self.inspect()
        result=self.update(status='blocked',author=A('codex'))
        self.assertEqual(result['recorded_fingerprint'],m.snapshot(self.repo)['fingerprint'])
        self.commit_code('second change')
        with self.assertRaises(m.StateError):self.update(status='implementing')
    def test_backend_labels_parse_and_never_review(self):
        self.assertEqual(m.provider('claude@omniroute:night1'),'claude@omniroute');self.assertEqual(m.provider('codex:resume'),'codex')
        for bad in ('gemini','claude@','claude@Omni Route','omniroute'):
            with self.assertRaises(m.StateError):m.provider(bad)
        with self.assertRaisesRegex(m.StateError,'native'):self.inspect('claude@omniroute')
        self.report_for('codex@omniroute',plan_sha256=m.reference(self.plan)['sha256'])
        with self.assertRaises(m.StateError):m.approve_plan(self.repo,'MEL-001',self.current()['revision'],'codex','codex@omniroute',self.report)
    def test_backend_builder_needs_native_review(self):
        owner='claude@omniroute:fallback'
        state=m.init(self.repo,'MEL-002',owner,self.plan,['A1'],'User waived plan review in fixture.')
        self.assertEqual(state['builders'],['claude@omniroute'])
        self.commit_code('backend edit')
        state=m.update(self.repo,'MEL-002',state['revision'],owner,passed='A1',proof=self.proof,pr='https://github.com/example/project/pull/2',author=A(owner))
        with self.assertRaisesRegex(m.StateError,'Fresh other-provider'):m.ready(self.repo,'MEL-002',state['revision'],owner)
        self.report_for('claude@omniroute')
        with self.assertRaisesRegex(m.StateError,'native'):m.inspect(self.repo,'MEL-002',state['revision'],owner,'claude@omniroute',self.report)
        self.report_for('claude');state=m.inspect(self.repo,'MEL-002',state['revision'],owner,'claude',self.report)
        self.assertEqual(m.ready(self.repo,'MEL-002',state['revision'],owner)['status'],'ready')
    def test_takeover_supersedes_pending_transfer_with_reason(self):
        state=self.handoff('codex:resume')
        for actor,reason in (('codex','user approved'),('claude','  ')):
            with self.assertRaises(m.StateError):m.takeover(self.repo,'MEL-001',state['revision'],actor,reason)
        result=m.takeover(self.repo,'MEL-001',state['revision'],'claude','Mohit approved: codex weekly quota exhausted')
        self.assertEqual(result['owner'],'claude');self.assertEqual(result['handoff']['superseded_by'],'takeover')
        self.assertEqual(result['takeovers'][0]['superseded_handoff'],state['handoff']['id'])
        self.assertTrue((m.location(self.repo,'MEL-001')/(state['handoff']['id']+'.json')).exists())
        with self.assertRaises(m.StateError):self.ack(result,actor='codex:resume')
        self.assertEqual(m.update(self.repo,'MEL-001',result['revision'],'claude',status='blocked')['status'],'blocked')
        self.commit_code()
        state=self.current()
        with self.assertRaises(m.StateError):m.takeover(self.repo,'MEL-001',state['revision'],'codex','back to codex')
        self.assertEqual(m.takeover(self.repo,'MEL-001',state['revision'],'codex','back to codex',author=A('claude'))['owner'],'codex')
    def test_session_labels_keep_ownership_distinct(self):
        state=self.handoff('codex:s2');self.assertEqual(self.ack(state,actor='codex:s2')['owner'],'codex:s2')
        with self.assertRaises(m.StateError):m.update(self.repo,'MEL-001',self.current()['revision'],'codex',status='blocked')
        self.assertEqual(m.update(self.repo,'MEL-001',self.current()['revision'],'codex:s2',status='blocked')['owner'],'codex:s2')
    def test_takeover_of_ready_task_needs_fresh_inspection(self):
        self.prepare();state=self.ready()
        result=m.takeover(self.repo,'MEL-001',state['revision'],'claude','Mohit approved: codex quota exhausted')
        self.assertEqual((result['status'],result['reviews']),('review_pending',{}))
        with self.assertRaises(m.StateError):m.ready(self.repo,'MEL-001',result['revision'],'claude')
        self.report_for('claude');state=m.inspect(self.repo,'MEL-001',result['revision'],'claude','claude',self.report)
        self.assertEqual(m.ready(self.repo,'MEL-001',state['revision'],'claude')['status'],'ready')
    def test_handoff_records_capacity_note(self):
        state=self.current();result=m.transfer(self.repo,'MEL-001',state['revision'],'codex','claude',['c'],['p'],'n',capacity=['codex weekly 92%'])
        record=json.loads((m.location(self.repo,'MEL-001')/(result['handoff']['id']+'.json')).read_text())
        self.assertEqual(record['capacity'],['codex weekly 92%'])
    def test_show_works_from_another_worktree_but_mutation_does_not(self):
        self.run_git('add','.mel');self.run_git('commit','-m','fixture state')
        other=self.parent/'other';self.run_git('worktree','add','-b','claude/review',str(other))
        shown=subprocess.run([sys.executable,'-B',str(SCRIPT),'show','--repo',str(other),'--task','MEL-001'],capture_output=True,text=True)
        self.assertEqual(shown.returncode,0,shown.stderr);self.assertEqual(json.loads(shown.stdout)['task'],'MEL-001')
        changed=subprocess.run([sys.executable,'-B',str(SCRIPT),'update','--repo',str(other),'--task','MEL-001','--expected','1','--actor','codex','--status','blocked'],capture_output=True,text=True)
        self.assertEqual(changed.returncode,1);self.assertIn('different worktree',changed.stderr)
    def test_local_delivery_merges_by_git_ancestry(self):
        self.run_git('branch','main')
        self.run_git('symbolic-ref','refs/heads/alias','refs/heads/codex/test');self.run_git('symbolic-ref','refs/heads/alias2','refs/heads/alias')
        # Case aliases (CODEX/TEST, Main) resolve on case-insensitive filesystems; symrefs resolve to the task branch.
        for target in ('codex/test','CODEX/TEST','Main','alias','alias2','codex/test~0','codex/test^0','@{-1}','HEAD@{0}','main~0','refs/heads/main'):
            with self.assertRaises(m.StateError,msg=target):m.init(self.repo,'MEL-003','codex',self.plan,['A1'],'waived',local_target=target)
            with self.assertRaises(m.StateError,msg=target):m.local_branch(self.repo,target)
        self.assertEqual(m.local_branch(self.repo,'main'),m.snapshot(self.repo)['head'])
        # A tag named like the task branch shortens HEAD to heads/codex/test; full refs still match.
        self.run_git('tag','codex/test')
        with self.assertRaises(m.StateError):m.local_branch(self.repo,'codex/test')
        with self.assertRaises(m.StateError):m.init(self.repo,'MEL-003','codex',self.plan,['A1'],'waived',local_target='codex/test')
        self.run_git('tag','-d','codex/test')
        # On Windows HEAD may hold a case alias of the stored task branch; the helper must fail closed.
        self.run_git('symbolic-ref','HEAD','refs/heads/CODEX/TEST')
        if subprocess.run(['git','-C',str(self.repo),'rev-parse','--verify','HEAD'],capture_output=True).returncode==0:
            with self.assertRaisesRegex(m.StateError,'exact name'):m.local_branch(self.repo,'main')
        self.run_git('symbolic-ref','HEAD','refs/heads/codex/test')
        # A Unicode line separator inside a real branch name must not fabricate a second record.
        if subprocess.run(['git','-C',str(self.repo),'branch','x refs/heads/ghost'],capture_output=True).returncode==0:
            with self.assertRaises(m.StateError):m.local_branch(self.repo,'ghost')
            self.assertEqual(m.local_branch(self.repo,'x refs/heads/ghost'),m.snapshot(self.repo)['head'])
            self.run_git('branch','-D','x refs/heads/ghost')
        # On a case-sensitive filesystem a separately stored Codex/Test is a distinct branch and stays allowed.
        if subprocess.run(['git','-C',str(self.repo),'branch','Codex/Test'],capture_output=True).returncode==0 and 'refs/heads/Codex/Test' in self.run_git('for-each-ref','--format=%(refname)','refs/heads/').split():
            self.assertEqual(m.local_branch(self.repo,'Codex/Test'),m.snapshot(self.repo)['head'])
        state=m.init(self.repo,'MEL-002','codex',self.plan,['A1'],'User waived plan review in fixture.',local_target='main')
        self.commit_code()
        state=m.update(self.repo,'MEL-002',state['revision'],'codex',passed='A1',proof=self.proof,author=A('codex'))
        self.report_for('claude');state=m.inspect(self.repo,'MEL-002',state['revision'],'codex','claude',self.report)
        state=m.ready(self.repo,'MEL-002',state['revision'],'codex');self.assertIsNone(state['pr'])
        with self.assertRaisesRegex(m.StateError,'does not contain'):m.merged(self.repo,'MEL-002',state['revision'],'codex')
        self.run_git('tag','main','HEAD')
        with self.assertRaisesRegex(m.StateError,'does not contain'):m.merged(self.repo,'MEL-002',state['revision'],'codex')
        with self.assertRaises(m.StateError):m.init(self.repo,'MEL-004','codex',self.plan,['A1'],'waived',local_target='missing')
        self.run_git('branch','-f','main','HEAD')
        result=m.merged(self.repo,'MEL-002',state['revision'],'codex')
        self.assertEqual((result['status'],result['merge']['mode'],result['merge']['target']),('merged','local','main'))
        self.update(passed='A1',proof=self.proof,author=A('codex'));self.update(passed='A2',proof=self.proof);self.inspect()
        with self.assertRaisesRegex(m.StateError,'PR'):self.ready()

    # MEL-003: attribution ledger, scope guard, roster and bench, rubric eval, round budget, show views.
    def round_report(self,name,verdict='REVISE',findings=None,reviewer='claude'):
        path=self.parent/name;path.write_text(json.dumps({'verdict':verdict,'reviewer':reviewer,'findings':findings or [],'coverage':[name],'limitations':[]}));return path
    def cli(self,*args):
        return subprocess.run([sys.executable,'-B',str(SCRIPT),*args,'--repo',str(self.repo),'--task','MEL-001'],capture_output=True,text=True)
    def test_ledger_records_model_and_files_touched(self):
        self.commit_code('committed');(self.repo/'dirty.py').write_text('x')
        with self.assertRaisesRegex(m.StateError,'--model'):self.update(author={'builder':'codex','model':' '})
        entry=self.update(author=A('codex','gpt-6.1-sol'))['ledger'][-1]
        self.assertEqual((entry['builder'],entry['model'],entry['files']),('codex','gpt-6.1-sol',['code.py','dirty.py']))
        self.run_git('add','dirty.py');self.run_git('commit','-m','fixture');(self.repo/'later.py').write_text('y')
        self.assertEqual(self.update(author=A('claude','claude-opus-5-5'))['ledger'][-1]['files'],['later.py'])
        self.assertIn('claude/claude-opus-5-5: later.py',self.cli('show','--who').stdout)
    def test_scope_guard_refuses_drift_unless_reason_recorded(self):
        state=m.init(self.repo,'MEL-002','codex',self.plan,['A1'],'waived in fixture',scope=['src/*'])
        (self.repo/'src').mkdir();(self.repo/'src'/'a.py').write_text('a');(self.repo/'other.py').write_text('b')
        with self.assertRaisesRegex(m.StateError,'outside the declared scope: other.py'):m.update(self.repo,'MEL-002',state['revision'],'codex',author=A('codex'))
        result=m.update(self.repo,'MEL-002',state['revision'],'codex',author={**A('codex'),'outside':'Mohit asked for other.py too'})
        self.assertEqual(result['ledger'][-1]['outside_scope'],{'paths':['other.py'],'reason':'Mohit asked for other.py too'})
        (self.repo/'src'/'b.py').write_text('c')
        self.assertNotIn('outside_scope',m.update(self.repo,'MEL-002',result['revision'],'codex',author=A('codex'))['ledger'][-1])
    def test_finding_needs_ledger_round_and_matching_report(self):
        self.commit_code();self.update(author=A('codex','weak-model'))
        report=self.round_report('r1.json',findings=[{'id':'F1','severity':'high'}])
        with self.assertRaisesRegex(m.StateError,'recorded review round'):m.finding(self.repo,'MEL-001',self.current()['revision'],'codex','F1','high','codex','weak-model',report)
        state=m.review_round(self.repo,'MEL-001',self.current()['revision'],'codex','inspect',report)
        for args,pattern in ((('F1','high','codex','other-model'),'ledger'),(('F1','high','claude','weak-model'),'ledger'),(('F2','high','codex','weak-model'),'finding id'),(('F1','low','codex','weak-model'),'same severity')):
            with self.assertRaisesRegex(m.StateError,pattern):m.finding(self.repo,'MEL-001',state['revision'],'codex',*args,report)
        state=m.finding(self.repo,'MEL-001',state['revision'],'codex','F1','high','codex','weak-model',report)
        self.assertEqual(state['findings'][0]['model'],'weak-model')
        with self.assertRaisesRegex(m.StateError,'already recorded'):m.finding(self.repo,'MEL-001',state['revision'],'codex','F1','high','codex','weak-model',report)
        self.assertEqual([e['kind'] for e in m.roster()],['build','finding'])
    def bench_with(self,count,severity='high',start=900):
        for n in range(start,start+count):
            m.roster_append(self.repo,{'kind':'build','task':f'MEL-{n}','builder':'codex','model':'weak-model'})
            m.roster_append(self.repo,{'kind':'finding','task':f'MEL-{n}','builder':'codex','model':'weak-model','severity':severity,'id':'F1'})
    def test_one_high_finding_does_not_bench(self):
        self.bench_with(1);self.commit_code()
        self.assertIsNone(m.bench_status('weak-model'));self.update(author=A('codex','weak-model'))
    def test_repeated_mistakes_bench_a_model_until_user_overrides(self):
        self.bench_with(2);self.commit_code()
        with self.assertRaisesRegex(m.StateError,'benched'):self.update(author=A('codex','weak-model'))
        self.assertEqual(self.update(author=A('codex','good-model'))['ledger'][-1]['model'],'good-model')
        (self.repo/'more.py').write_text('m')
        entry=self.update(author={**A('codex','weak-model'),'override':'Mohit approved one more try'})['ledger'][-1]
        self.assertEqual(entry['bench_override']['reason'],'Mohit approved one more try')
        self.assertIn('weak-model: 3 tasks, 2 high, 0 medium, 0 low BENCHED',self.cli('show','--roster').stdout)
    def test_medium_findings_bench_at_four_and_old_tasks_age_out(self):
        self.bench_with(3,'medium');self.assertIsNone(m.bench_status('weak-model'))
        self.bench_with(1,'medium',start=903);self.assertIsNotNone(m.bench_status('weak-model'))
        for n in range(10):m.roster_append(self.repo,{'kind':'build','task':f'MEL-{950+n}','builder':'codex','model':'weak-model'})
        self.assertIsNone(m.bench_status('weak-model'))
    def rubric(self):
        path=self.parent/'rubric.json'
        path.write_text(json.dumps([{'id':'R1','criterion':'merge record cannot be faked','threshold':4},{'id':'R2','criterion':'old state still loads','threshold':3}]));return path
    def eval_report(self,judge='claude',scores=(5,4),name='eval.json',**extra):
        path=self.parent/name
        path.write_text(json.dumps({'judge':judge,'results':[{'id':f'R{n+1}','score':s,'evidence':'test cited'} for n,s in enumerate(scores)],**extra}));return path
    def test_high_risk_needs_rubric_at_init(self):
        with self.assertRaisesRegex(m.StateError,'--rubric'):m.init(self.repo,'MEL-002','codex',self.plan,['A1'],'waived',risk='high')
        bad=self.parent/'bad.json';bad.write_text(json.dumps([{'id':'R1','criterion':'x'}]))
        with self.assertRaisesRegex(m.StateError,'threshold'):m.init(self.repo,'MEL-002','codex',self.plan,['A1'],'waived',risk='high',rubric=bad)
    def test_nonfinite_thresholds_are_refused_without_state_changes(self):
        path=m.location(self.repo,'MEL-001')/'state.json';before=path.read_bytes()
        bad=self.parent/'bad-rubric.json'
        for number in ('NaN','Infinity','-Infinity','1e999','true'):
            with self.subTest(number=number):
                bad.write_text('[{"id":"R1","criterion":"x","threshold":'+number+'}]')
                with self.assertRaisesRegex(m.StateError,'numeric threshold'):
                    m.init(self.repo,'MEL-002','codex',self.plan,['A1'],'waived',risk='high',rubric=bad)
                self.assertFalse(m.location(self.repo,'MEL-002').exists())
                with self.assertRaisesRegex(m.StateError,'numeric threshold'):
                    m.revise_plan(self.repo,'MEL-001',self.current()['revision'],'codex',self.plan,'waived',rubric=bad)
                self.assertEqual(path.read_bytes(),before)
    def test_nonfinite_scores_are_refused_without_state_changes(self):
        state=self.high_risk_ready()
        state=m.inspect(self.repo,'MEL-002',state['revision'],'codex','claude',self.report_for())
        state=m.evaluate(self.repo,'MEL-002',state['revision'],'codex','claude','m',self.eval_report(name='passing.json'))
        state=m.ready(self.repo,'MEL-002',state['revision'],'codex')
        path=m.location(self.repo,'MEL-002')/'state.json';before=path.read_bytes()
        for number in ('NaN','Infinity','-Infinity','1e999','true'):
            with self.subTest(number=number):
                report=self.eval_report(scores=(3,'bad'))
                report.write_text(report.read_text().replace('"bad"',number))
                with self.assertRaisesRegex(m.StateError,'needs a numeric score and evidence'):
                    m.evaluate(self.repo,'MEL-002',state['revision'],'codex','claude','m',report)
                self.assertEqual(path.read_bytes(),before)
    def test_high_risk_ready_needs_passing_eval_from_a_non_builder(self):
        state=m.init(self.repo,'MEL-002','codex',self.plan,['A1'],'waived in fixture',risk='high',rubric=self.rubric())
        state=m.update(self.repo,'MEL-002',state['revision'],'codex',passed='A1',proof=self.proof,pr='https://github.com/example/project/pull/3')
        self.report_for('claude');state=m.inspect(self.repo,'MEL-002',state['revision'],'codex','claude',self.report)
        with self.assertRaisesRegex(m.StateError,'rubric eval'):m.ready(self.repo,'MEL-002',state['revision'],'codex')
        # Thresholds come from the plan's rubric, not from the judge's report.
        for judge,scores,pattern in (('claude',(5,),'R2 needs'),('codex',(5,4),'only builder'),('claude@omniroute',(5,4),'native'),('claude',(3,4),'Eval failed on R1: 3 < 4')):
            with self.assertRaisesRegex(m.StateError,pattern):m.evaluate(self.repo,'MEL-002',state['revision'],'codex',judge,'m',self.eval_report(judge,scores))
        state=m.load(self.repo,'MEL-002')  # only the complete failing eval was recorded (MEL-004 I5)
        state=m.evaluate(self.repo,'MEL-002',state['revision'],'codex','claude','claude-opus-5-5',self.eval_report())
        self.assertEqual(m.ready(self.repo,'MEL-002',state['revision'],'codex')['status'],'ready')
        state=m.update(self.repo,'MEL-002',state['revision']+1,'codex',status='review_pending')
        self.assertNotIn('evals',state)
        self.rubric().write_text('[]')
        with self.assertRaisesRegex(m.StateError,'missing or changed'):m.evaluate(self.repo,'MEL-002',state['revision'],'codex','claude','m',self.eval_report())
    def test_revised_plan_can_carry_a_revised_rubric(self):
        state=m.init(self.repo,'MEL-002','codex',self.plan,['A1'],'waived in fixture',risk='high',rubric=self.rubric())
        new=self.parent/'rubric-v2.json';new.write_text(json.dumps([{'id':'R1','criterion':'merge record cannot be faked','threshold':5}]))
        self.plan.write_text('Revised plan with a stricter rubric\n')
        state=m.revise_plan(self.repo,'MEL-002',state['revision'],'codex',self.plan,'waived again in fixture',author=A('codex'),rubric=new)
        self.assertEqual(state['rubric']['path'],str(new.resolve()));self.assertEqual(state['plan_history'][-1]['rubric']['path'],str(self.rubric().resolve()))
        state=m.update(self.repo,'MEL-002',state['revision'],'codex',passed='A1',proof=self.proof,pr='https://github.com/example/project/pull/5')
        with self.assertRaisesRegex(m.StateError,'R1: 4 < 5'):m.evaluate(self.repo,'MEL-002',state['revision'],'codex','claude','m',self.eval_report(scores=(4,)))
        state=m.load(self.repo,'MEL-002')
        self.assertIn('claude',m.evaluate(self.repo,'MEL-002',state['revision'],'codex','claude','m',self.eval_report(scores=(5,)))['evals'])
    def test_pruned_recorded_tree_falls_back_and_is_flagged(self):
        path=m.location(self.repo,'MEL-001')/'state.json';state=json.loads(path.read_text())
        state['recorded_tree']='0'*40;path.write_bytes(m.encoded(state));self.commit_code()
        entry=self.update(author=A('codex'))['ledger'][-1]
        self.assertIn('approximate',entry['attribution']);self.assertEqual(entry['files'],['code.py'])
        for flag in ('--who','--brief'):
            out=self.cli('show',flag);self.assertEqual(out.returncode,0,out.stderr)
            self.assertIn(entry['attribution'],out.stdout)
            self.assertIn('integration builders: claude, codex',out.stdout)
        (self.repo/'next.py').write_text('n')
        self.assertNotIn('attribution',self.update(author=A('codex'))['ledger'][-1])
    def test_mixed_authorship_high_risk_needs_eval_of_each_contribution(self):
        state=m.init(self.repo,'MEL-002','codex',self.plan,['A1'],'waived in fixture',risk='high',rubric=self.rubric())
        self.commit_code('claude part')
        state=m.update(self.repo,'MEL-002',state['revision'],'codex',passed='A1',proof=self.proof,pr='https://github.com/example/project/pull/4',author=A('claude'))
        for reviewer in ('claude','codex'):
            path=self.parent/f'{reviewer}-inspect.json';path.write_text(json.dumps({'verdict':'APPROVED','reviewer':reviewer,'coverage':['x'],'findings':[],'limitations':[]}))
            state=m.inspect(self.repo,'MEL-002',state['revision'],'codex',reviewer,path)
        state=m.evaluate(self.repo,'MEL-002',state['revision'],'codex','claude','m',self.eval_report('claude',name='e1.json'))
        with self.assertRaisesRegex(m.StateError,'each builder'):m.ready(self.repo,'MEL-002',state['revision'],'codex')
        state=m.evaluate(self.repo,'MEL-002',state['revision'],'codex','codex','m',self.eval_report('codex',name='e2.json'))
        self.assertEqual(m.ready(self.repo,'MEL-002',state['revision'],'codex')['status'],'ready')
    def test_same_finding_counts_once_and_corrections_need_a_reason(self):
        self.commit_code();self.update(author=A('codex','weak-model'))
        r1=self.round_report('r1.json',findings=[{'id':'F1','severity':'high'}]);r2=self.round_report('r2.json',findings=[{'id':'F1','severity':'high'},{'id':'F2','severity':'low'}])
        for r in (r1,r2):m.review_round(self.repo,'MEL-001',self.current()['revision'],'codex','inspect',r,'fixture')
        m.finding(self.repo,'MEL-001',self.current()['revision'],'codex','F1','high','codex','weak-model',r1)
        with self.assertRaisesRegex(m.StateError,'already recorded'):m.finding(self.repo,'MEL-001',self.current()['revision'],'codex','F1','high','codex','weak-model',r2)
        with self.assertRaisesRegex(m.StateError,'--correct'):m.finding(self.repo,'MEL-001',self.current()['revision'],'codex','F1','medium','codex','weak-model',r2)
        with self.assertRaisesRegex(m.StateError,'Only a recorded'):m.finding(self.repo,'MEL-001',self.current()['revision'],'codex','F9','retracted','codex','weak-model',r2,'never existed')
        state=m.finding(self.repo,'MEL-001',self.current()['revision'],'codex','F1','retracted','codex','weak-model',r2,'reviewer misread the diff')
        self.assertEqual(state['findings'][-1]['corrects'],{'severity':'high','reason':'reviewer misread the diff'})
        self.bench_with(1);self.assertIsNone(m.bench_status('weak-model'))
    def test_approval_and_inspection_count_against_the_budget_once(self):
        self.report_for('claude',plan_sha256=m.reference(self.plan)['sha256'])
        state=m.review_round(self.repo,'MEL-001',1,'codex','plan',self.report)
        state=m.approve_plan(self.repo,'MEL-001',state['revision'],'codex','claude',self.report)
        self.assertEqual([r['kind'] for r in state['rounds']],['plan'])
        self.update(pr='https://github.com/example/project/pull/1');self.update(passed='A1',proof=self.proof)
        for n in (1,2):
            state=self.inspect(coverage=[f'pass {n}'])
        self.assertEqual(sum(r['kind']=='inspect' for r in state['rounds']),2)
        self.report_for('claude',coverage=['pass 3'])
        with self.assertRaisesRegex(m.StateError,'budget \\(2\\)'):m.inspect(self.repo,'MEL-001',state['revision'],'codex','claude',self.report)
        self.assertEqual(m.inspect(self.repo,'MEL-001',state['revision'],'codex','claude',self.report,extend='Mohit approved round 3')['rounds'][-1]['extend'],'Mohit approved round 3')
    def test_normal_risk_skips_eval(self):
        self.prepare();self.assertEqual(self.ready()['status'],'ready')
    def test_round_budget_needs_reason_to_extend(self):
        for n in (1,2):self.assertEqual(m.review_round(self.repo,'MEL-001',self.current()['revision'],'codex','inspect',self.round_report(f'i{n}.json'))['rounds'][-1]['number'],n)
        with self.assertRaisesRegex(m.StateError,'budget \\(2\\)'):m.review_round(self.repo,'MEL-001',self.current()['revision'],'codex','inspect',self.round_report('i3.json'))
        state=m.review_round(self.repo,'MEL-001',self.current()['revision'],'codex','inspect',self.round_report('i3.json'),'F1 high; Mohit approved a third round')
        self.assertEqual((state['rounds'][-1]['number'],state['rounds'][-1]['extend']),(3,'F1 high; Mohit approved a third round'))
        self.assertEqual(m.review_round(self.repo,'MEL-001',state['revision'],'codex','plan',self.round_report('p1.json'))['rounds'][-1]['number'],1)
    def test_show_brief_is_a_compact_resume_packet(self):
        self.handoff('codex:resume')
        out=self.cli('show','--brief').stdout
        for text in ('MEL-001 status=planned owner=codex','open criteria: A1, A2','-> codex:resume (PENDING); next: Inspect A2','constraints: No external writes'):
            self.assertIn(text,out)
        self.assertLess(len(out.splitlines()),15)

    def test_unsuccessful_plan_round_voids_approval_until_renewed(self):
        for task,verdict in (('MEL-002','REVISE'),('MEL-003','BLOCKED')):
            with self.subTest(verdict=verdict):
                state=m.init(self.repo,task,'codex',self.plan,['A1'])
                approved=self.round_report(f'{task}-plan.json','APPROVED')
                data=json.loads(approved.read_text());data['plan_sha256']=m.reference(self.plan)['sha256'];approved.write_text(json.dumps(data))
                state=m.approve_plan(self.repo,task,state['revision'],'codex','claude',approved)
                state=m.update(self.repo,task,state['revision'],'codex',status='implementing',passed='A1',proof=self.proof,pr='https://github.com/example/project/pull/1')
                inspection=self.round_report(f'{task}-inspect.json','APPROVED')
                state=m.inspect(self.repo,task,state['revision'],'codex','claude',inspection)
                state=m.ready(self.repo,task,state['revision'],'codex');self.assertEqual(state['status'],'ready')
                rejected=self.round_report(f'{task}-failed.json',verdict)
                state=m.review_round(self.repo,task,state['revision'],'codex','plan',rejected)
                self.assertIsNone(state['plan_review']);self.assertEqual(state['status'],'review_pending')
                with self.assertRaisesRegex(m.StateError,'plan approval'):m.ready(self.repo,task,state['revision'],'codex')
                with self.assertRaisesRegex(m.StateError,'plan approval'):m.update(self.repo,task,state['revision'],'codex',status='implementing')
                state=m.approve_plan(self.repo,task,state['revision'],'codex','claude',approved)
                state=m.update(self.repo,task,state['revision'],'codex',status='implementing')
                state=m.inspect(self.repo,task,state['revision'],'codex','claude',inspection)
                self.assertEqual(m.ready(self.repo,task,state['revision'],'codex')['status'],'ready')
                # Re-recording the same unsuccessful report must also void renewed approval.
                state=m.load(self.repo,task)
                state=m.review_round(self.repo,task,state['revision'],'codex','plan',rejected)
                with self.assertRaisesRegex(m.StateError,'plan approval'):m.update(self.repo,task,state['revision'],'codex',status='implementing')

    def test_unsuccessful_inspect_round_voids_reviews_and_evals(self):
        for task,verdict in (('MEL-002','REVISE'),('MEL-003','BLOCKED')):
            with self.subTest(verdict=verdict):
                state=m.init(self.repo,task,'codex',self.plan,['A1'],'waived in fixture',risk='high',rubric=self.rubric())
                state=m.update(self.repo,task,state['revision'],'codex',passed='A1',proof=self.proof,pr='https://github.com/example/project/pull/1')
                approved=self.round_report(f'{task}-approved.json','APPROVED')
                state=m.inspect(self.repo,task,state['revision'],'codex','claude',approved)
                evaluation=self.eval_report()
                state=m.evaluate(self.repo,task,state['revision'],'codex','claude','fixture',evaluation)
                state=m.ready(self.repo,task,state['revision'],'codex');self.assertEqual(state['status'],'ready')
                state=m.review_round(self.repo,task,state['revision'],'codex','inspect',self.round_report(f'{task}-failed.json',verdict))
                self.assertEqual(state['reviews'],{});self.assertNotIn('evals',state);self.assertEqual(state['status'],'review_pending')
                with self.assertRaisesRegex(m.StateError,'inspection'):m.ready(self.repo,task,state['revision'],'codex')
                state=m.inspect(self.repo,task,state['revision'],'codex','claude',approved)
                with self.assertRaisesRegex(m.StateError,'rubric eval'):m.ready(self.repo,task,state['revision'],'codex')
                state=m.evaluate(self.repo,task,state['revision'],'codex','claude','fixture',evaluation)
                self.assertEqual(m.ready(self.repo,task,state['revision'],'codex')['status'],'ready')

    def finding_cli(self,report,severity,correct=''):
        args=['finding','--expected',str(self.current()['revision']),'--actor','codex','--id','F1','--severity',severity,
              '--builder','codex','--model','weak-model','--report',str(report)]
        if correct:args+=['--correct',correct]
        out=self.cli(*args);self.assertEqual(out.returncode,0,out.stderr)

    def finding_reports(self):
        self.update(author=A('codex','weak-model'));self.update(author=A('codex','other-model'))
        first=self.round_report('first.json',findings=[{'id':'F1','severity':'high'}])
        corrected=self.round_report('corrected.json',findings=[{'id':'F1','severity':'medium'}])
        for report in (first,corrected):m.review_round(self.repo,'MEL-001',self.current()['revision'],'codex','inspect',report)
        self.finding_cli(first,'high');return first,corrected

    def test_roster_cli_uses_latest_severity_and_keeps_other_models_readable(self):
        first,corrected=self.finding_reports()
        initial=self.cli('show','--roster');self.assertEqual(initial.returncode,0,initial.stderr)
        self.assertIn('weak-model: 1 tasks, 1 high, 0 medium, 0 low',initial.stdout)
        self.finding_cli(corrected,'medium','reviewer corrected the severity')
        out=self.cli('show','--roster');self.assertEqual(out.returncode,0,out.stderr)
        self.assertIn('weak-model: 1 tasks, 0 high, 1 medium, 0 low',out.stdout)
        self.assertIn('other-model: 1 tasks, 0 high, 0 medium, 0 low',out.stdout)
        brief=self.cli('show','--brief');self.assertEqual(brief.returncode,0,brief.stderr)
        self.assertIn('finding F1 medium by codex/weak-model',brief.stdout);self.assertNotIn('finding F1 high',brief.stdout)

    def test_roster_cli_excludes_retractions_and_brief_has_no_closed_findings(self):
        first,corrected=self.finding_reports()
        self.finding_cli(corrected,'retracted','reviewer misread the diff')
        out=self.cli('show','--roster');self.assertEqual(out.returncode,0,out.stderr)
        self.assertIn('weak-model: 1 tasks, 0 high, 0 medium, 0 low',out.stdout)
        self.assertIn('other-model: 1 tasks, 0 high, 0 medium, 0 low',out.stdout)
        brief=self.cli('show','--brief');self.assertEqual(brief.returncode,0,brief.stderr);self.assertNotIn('finding F1',brief.stdout)

    def test_roster_cli_ignores_unknown_severity_and_keys_findings_by_repo_task_id(self):
        for repo,task,severity in (('a','MEL-001','high'),('a','MEL-001','medium'),('b','MEL-001','low'),
                                   ('a','MEL-002','high'),('a','MEL-003','unknown')):
            m.roster_append(self.repo,{'repo_id':repo,'kind':'finding','task':task,'id':'F1','model':'fixture','severity':severity})
        out=self.cli('show','--roster');self.assertEqual(out.returncode,0,out.stderr)
        self.assertIn('fixture: 4 tasks, 1 high, 1 medium, 1 low',out.stdout)

    def test_global_finding_event_keeps_the_report_hash(self):
        first,corrected=self.finding_reports()
        event=m.roster()[-1]
        self.assertEqual(event['report'],m.reference(first))

    # MEL-004: integration-review fixes I1-I8 and P1-P7.
    def test_rejected_plan_voids_an_earlier_waiver(self):
        state=m.review_round(self.repo,'MEL-001',1,'codex','plan',self.round_report('p1.json'))
        self.assertEqual(state['plan_review_waiver'],'');self.assertIn('voided_waiver',state['plan_history'][-1])
        with self.assertRaisesRegex(m.StateError,'waiver required'):self.update(status='implementing')
        state=m.revise_plan(self.repo,'MEL-001',state['revision'],'codex',self.plan,'Mohit waived review again after reading p1')
        self.assertEqual(self.update(status='implementing')['status'],'implementing')
    def test_revise_plan_reconciles_scope_and_criteria(self):
        state=m.init(self.repo,'MEL-002','codex',self.plan,['A1','A2'],'waived in fixture',scope=['src/*'])
        (self.repo/'docs').mkdir();(self.repo/'docs'/'x.md').write_text('d');self.plan.write_text('Plan now covers docs\n')
        with self.assertRaisesRegex(m.StateError,'outside the declared scope'):
            m.revise_plan(self.repo,'MEL-002',state['revision'],'codex',self.plan,'w',author=A('codex'),scope=['src/*'])
        with self.assertRaisesRegex(m.StateError,'drop-reason'):
            m.revise_plan(self.repo,'MEL-002',state['revision'],'codex',self.plan,'w',author=A('codex'),scope=['src/*','docs/*','plan.md'],criteria=['A1','A3'])
        state=m.revise_plan(self.repo,'MEL-002',state['revision'],'codex',self.plan,'w',author=A('codex'),scope=['src/*','docs/*','plan.md'],criteria=['A1','A3'],drop_reason='A2 moved to MEL-005')
        self.assertEqual((state['scope'],sorted(state['criteria'])),(['src/*','docs/*','plan.md'],['A1','A3']))
        self.assertEqual((state['plan_history'][-1]['scope'],state['plan_history'][-1]['criteria']),(['src/*'],['A1','A2']))
        self.assertEqual(state['plan_history'][-1]['dropped'],{'criteria':['A2'],'reason':'A2 moved to MEL-005'})
        (self.repo/'other.py').write_text('o')
        with self.assertRaisesRegex(m.StateError,'other.py'):m.update(self.repo,'MEL-002',state['revision'],'codex',author=A('codex'))
    def test_identical_report_for_a_new_snapshot_is_a_new_round(self):
        state=m.init(self.repo,'MEL-002','codex',self.plan,['A1'],'waived',budget_inspect=1)
        report=self.round_report('same.json','APPROVED')
        state=m.update(self.repo,'MEL-002',state['revision'],'codex',passed='A1',proof=self.proof,pr='https://github.com/example/project/pull/1')
        state=m.inspect(self.repo,'MEL-002',state['revision'],'codex','claude',report)
        state=m.review_round(self.repo,'MEL-002',state['revision'],'codex','inspect',report)  # same execution: counted once
        self.assertEqual(sum(r['kind']=='inspect' for r in state['rounds']),1)
        self.commit_code('second snapshot');state=m.update(self.repo,'MEL-002',state['revision'],'codex',author=A('codex'))
        with self.assertRaisesRegex(m.StateError,'budget \\(1\\)'):m.inspect(self.repo,'MEL-002',state['revision'],'codex','claude',report)
        state=m.inspect(self.repo,'MEL-002',state['revision'],'codex','claude',report,extend='second snapshot needs its own review')
        self.assertEqual([r['number'] for r in state['rounds'] if r['kind']=='inspect'],[1,2])
    def high_risk_ready(self,owner='codex'):
        state=m.init(self.repo,'MEL-002',owner,self.plan,['A1'],'waived in fixture',risk='high',rubric=self.rubric())
        self.commit_code('built');state=m.update(self.repo,'MEL-002',state['revision'],owner,passed='A1',proof=self.proof,pr='https://github.com/example/project/pull/1',author=A(owner))
        return state
    def test_failed_eval_is_recorded_and_blocks_ready_until_the_same_judge_passes(self):
        owner='claude@omniroute';state=self.high_risk_ready(owner)  # backend work: either native judge may pass it
        state=m.inspect(self.repo,'MEL-002',state['revision'],owner,'claude',self.round_report('ok.json','APPROVED'))
        state=m.evaluate(self.repo,'MEL-002',state['revision'],owner,'claude','m',self.eval_report('claude',name='e1.json'))
        state=m.ready(self.repo,'MEL-002',state['revision'],owner);self.assertEqual(state['status'],'ready')
        with self.assertRaisesRegex(m.StateError,'R1: 3 < 4.*Recorded'):m.evaluate(self.repo,'MEL-002',state['revision'],owner,'codex','m',self.eval_report('codex',(3,4),'e2.json'))
        before=state['revision'];state=m.load(self.repo,'MEL-002');self.assertEqual(state['revision'],before+1)
        self.assertEqual((state['status'],state.get('evals'),state['eval_failures'][-1]['judge']),('review_pending',None,'codex'))
        state=m.evaluate(self.repo,'MEL-002',state['revision'],owner,'claude','m',self.eval_report('claude',name='e3.json'))
        with self.assertRaisesRegex(m.StateError,'codex failed the eval'):m.ready(self.repo,'MEL-002',state['revision'],owner)
        state=m.evaluate(self.repo,'MEL-002',state['revision'],owner,'codex','m',self.eval_report('codex',name='e4.json'))
        self.assertIsNotNone(state['eval_failures'][-1]['resolved_revision'])
        self.assertEqual(m.ready(self.repo,'MEL-002',state['revision'],owner)['status'],'ready')
    def test_failed_eval_cli_exits_1_but_advances_revision(self):
        state=self.high_risk_ready()
        out=subprocess.run([sys.executable,'-B',str(SCRIPT),'eval','--repo',str(self.repo),'--task','MEL-002','--expected',str(state['revision']),
                            '--actor','codex','--judge','claude','--model','m','--report',str(self.eval_report(scores=(1,1)))],capture_output=True,text=True)
        self.assertEqual(out.returncode,1);self.assertIn('Eval failed on R1',out.stderr)
        self.assertEqual(m.load(self.repo,'MEL-002')['revision'],state['revision']+1)
    def test_rubric_only_revision_supersedes_failed_eval_without_removing_history(self):
        state=self.high_risk_ready();current=m.snapshot(self.repo);plan=state['plan']
        state=m.inspect(self.repo,'MEL-002',state['revision'],'codex','claude',self.report_for())
        with self.assertRaisesRegex(m.StateError,'Eval failed on R1'):
            m.evaluate(self.repo,'MEL-002',state['revision'],'codex','claude','m',self.eval_report(scores=(3,4)))
        state=m.load(self.repo,'MEL-002');failures=state['eval_failures']
        rubric=self.parent/'rubric-v2.json';rubric.write_text(json.dumps([
            {'id':'R1','criterion':'merge record cannot be faked','threshold':3},
            {'id':'R2','criterion':'old state still loads','threshold':3}]))
        state=m.revise_plan(self.repo,'MEL-002',state['revision'],'codex',self.plan,'waived again in fixture',rubric=rubric)
        self.assertEqual((m.snapshot(self.repo),state['plan']),(current,plan))
        state=m.update(self.repo,'MEL-002',state['revision'],'codex',passed='A1',proof=self.proof)
        state=m.inspect(self.repo,'MEL-002',state['revision'],'codex','claude',self.report_for())
        state=m.evaluate(self.repo,'MEL-002',state['revision'],'codex','claude','m',self.eval_report(scores=(3,4),name='passing.json'))
        self.assertEqual(state['eval_failures'],failures)
        self.assertEqual(m.ready(self.repo,'MEL-002',state['revision'],'codex')['status'],'ready')
    def test_adoption_needs_named_or_unknown_authors(self):
        initial=m.snapshot(self.repo)['head'];self.commit_code('claude work before tracking')
        with self.assertRaisesRegex(m.StateError,'--adopt'):m.init(self.repo,'MEL-002','codex',self.plan,['A1'],'w',baseline=initial)
        with self.assertRaisesRegex(m.StateError,'Nothing to adopt'):m.init(self.repo,'MEL-003','codex',self.plan,['A1'],'w',adopt=['claude=x'])
        state=m.init(self.repo,'MEL-002','codex',self.plan,['A1'],'w',baseline=initial,adopt=['claude=claude-opus-5-5','codex=gpt-6.1-sol'])
        self.assertEqual(state['builders'],['claude','codex'])
        self.assertEqual([(e['builder'],e['files'],e['adopted']) for e in state['ledger']],[('claude',['code.py'],True),('codex',['code.py'],True)])
        ids=[e['event_id'] for e in m.roster()];self.assertEqual(len(ids),2);self.assertEqual(len(set(ids)),2)
        self.assertEqual(m.sync_roster(self.repo,state),0);self.assertEqual(m.sync_roster(self.repo,state),0)
        # Codex adopting Claude-built work: Claude alone cannot approve it.
        state=m.init(self.repo,'MEL-003','codex',self.plan,['A1'],'w',baseline=initial,adopt=['claude=claude-opus-5-5'])
        self.assertEqual(state['builders'],['claude'])
        state=m.update(self.repo,'MEL-003',state['revision'],'codex',passed='A1',proof=self.proof,pr='https://github.com/example/project/pull/1')
        with self.assertRaisesRegex(m.StateError,'own implementation'):m.inspect(self.repo,'MEL-003',state['revision'],'codex','claude',self.round_report('c.json','APPROVED'))
        state=m.inspect(self.repo,'MEL-003',state['revision'],'codex','codex',self.round_report('x.json','APPROVED',reviewer='codex'))
        self.assertEqual(m.ready(self.repo,'MEL-003',state['revision'],'codex')['status'],'ready')
    def adopted_codex_plan(self,task,owner='claude'):
        # A codex-written plan committed after the baseline, adopted by a claude-owned task.
        initial=m.snapshot(self.repo)['head'];plan=self.repo/('plan-'+task+'.md');plan.write_text('A1 by codex ')
        self.run_git('add',plan.name);self.run_git('commit','-m','codex plan')
        return plan,m.init(self.repo,task,owner,plan,['A1'],baseline=initial,adopt=['codex=fixture-model'],plan_author='codex')
    def approve(self,task,plan,state,actor,reviewer):
        self.report_for(reviewer,plan_sha256=m.reference(plan)['sha256'])
        return m.approve_plan(self.repo,task,state['revision'],actor,reviewer,self.report)
    def test_plan_author_not_coordinator_decides_who_approves(self):
        plan,state=self.adopted_codex_plan('MEL-010')
        self.assertEqual((state['plan_author'],state['coordinator']),('codex','claude'))
        with self.assertRaisesRegex(m.StateError,'other native provider'):self.approve('MEL-010',plan,state,'claude','codex')
        self.assertEqual(self.approve('MEL-010',plan,state,'claude','claude')['plan_review']['reviewer'],'claude')
    def test_plan_author_survives_handoff_and_takeover(self):
        plan,state=self.adopted_codex_plan('MEL-010')
        state=m.transfer(self.repo,'MEL-010',state['revision'],'claude','codex',['c'],['p'],'n')
        h=state['handoff'];state=m.acknowledge(self.repo,'MEL-010',state['revision'],'codex',h['id'],h['sha256'])
        self.assertEqual((state['owner'],state['plan_author']),('codex','codex'))
        with self.assertRaises(m.StateError):self.approve('MEL-010',plan,state,'codex','codex')
        self.assertEqual(self.approve('MEL-010',plan,state,'codex','claude')['plan_review']['reviewer'],'claude')
        plan,state=self.adopted_codex_plan('MEL-011')
        state=m.takeover(self.repo,'MEL-011',state['revision'],'codex','Mohit approved: claude out')
        self.assertEqual(state['plan_author'],'codex')
        with self.assertRaises(m.StateError):self.approve('MEL-011',plan,state,'codex','codex')
        self.approve('MEL-011',plan,state,'codex','claude')
    def test_legacy_state_without_plan_author_keeps_coordinator_rule(self):
        path=m.location(self.repo,'MEL-001')/'state.json';data=json.loads(path.read_text())
        del data['plan_author'];path.write_text(json.dumps(data))
        self.report_for('codex',plan_sha256=m.reference(self.plan)['sha256'])
        with self.assertRaises(m.StateError):m.approve_plan(self.repo,'MEL-001',1,'codex','codex',self.report)
        self.assertEqual(self.approve('MEL-001',self.plan,self.current(),'codex','claude')['plan_review']['reviewer'],'claude')
    def test_revise_plan_sets_plan_author_default_and_explicit(self):
        self.assertEqual(self.state['plan_author'],'codex')  # default: owner
        self.plan.write_text('v2 ');state=m.revise_plan(self.repo,'MEL-001',1,'codex',self.plan,'waived',author=A('codex'),plan_author='claude')
        self.assertEqual(state['plan_author'],'claude')
        self.plan.write_text('v3 ');state=m.revise_plan(self.repo,'MEL-001',state['revision'],'codex',self.plan,'waived',author=A('codex'))
        self.assertEqual(state['plan_author'],'codex')  # default: actor
        self.plan.write_text('v4 ')
        with self.assertRaisesRegex(m.StateError,'native'):m.revise_plan(self.repo,'MEL-001',state['revision'],'codex',self.plan,'waived',author=A('codex'),plan_author='codex@omniroute')
    def test_backend_owner_defaults_plan_author_to_native_harness(self):
        owner='claude@omniroute:fallback'
        state=m.init(self.repo,'MEL-014',owner,self.plan,['A1'],'waived')
        self.assertEqual(state['plan_author'],'claude')
        self.report_for('claude',plan_sha256=m.reference(self.plan)['sha256'])
        with self.assertRaises(m.StateError):m.approve_plan(self.repo,'MEL-014',1,owner,'claude',self.report)
        self.report_for('codex',plan_sha256=m.reference(self.plan)['sha256'])
        self.assertEqual(m.approve_plan(self.repo,'MEL-014',1,owner,'codex',self.report)['plan_review']['reviewer'],'codex')
        self.assertEqual(m.init(self.repo,'MEL-015',owner,self.plan,['A1'],'waived',plan_author='codex')['plan_author'],'codex')
        with self.assertRaisesRegex(m.StateError,'native'):m.init(self.repo,'MEL-016',owner,self.plan,['A1'],'waived',plan_author='codex@omniroute')
    def test_backend_actor_revise_plan_defaults_and_accepts_flag(self):
        owner='claude@omniroute:fallback'
        state=m.init(self.repo,'MEL-014',owner,self.plan,['A1'],'waived')
        self.plan.write_text('v2 ');state=m.revise_plan(self.repo,'MEL-014',state['revision'],owner,self.plan,'waived',author=A('claude'))
        self.assertEqual(state['plan_author'],'claude')
        self.plan.write_text('v3 ');state=m.revise_plan(self.repo,'MEL-014',state['revision'],owner,self.plan,'waived',author=A('claude'),plan_author='codex')
        self.assertEqual(state['plan_author'],'codex')
    def test_adopted_plan_needs_its_author_among_adopted_builders(self):
        initial=m.snapshot(self.repo)['head'];plan=self.repo/'plan-x.md';plan.write_text('x ')
        self.run_git('add','plan-x.md');self.run_git('commit','-m','plan')
        with self.assertRaisesRegex(m.StateError,'plan file'):m.init(self.repo,'MEL-012','claude',plan,['A1'],baseline=initial,adopt=['codex=x'])
        self.assertEqual(m.init(self.repo,'MEL-012','claude',plan,['A1'],baseline=initial,adopt=['codex=x'],plan_author='codex')['plan_author'],'codex')
        # Plan not among adopted files: the check is skipped.
        self.commit_code('other');base2=m.snapshot(self.repo)['head'];self.commit_code('other2')
        self.assertEqual(m.init(self.repo,'MEL-013','claude',plan,['A1'],baseline=base2,adopt=['codex=x'])['plan_author'],'claude')
    def test_unknown_adoption_needs_both_providers(self):
        initial=m.snapshot(self.repo)['head'];self.commit_code('who wrote this?')
        state=m.init(self.repo,'MEL-002','codex',self.plan,['A1'],'w',baseline=initial,adopt_unknown='inherited branch, author not recorded')
        self.assertEqual(state['builders'],['claude','codex']);self.assertNotIn('ledger',state)
        state=m.update(self.repo,'MEL-002',state['revision'],'codex',passed='A1',proof=self.proof,pr='https://github.com/example/project/pull/1')
        state=m.inspect(self.repo,'MEL-002',state['revision'],'codex','claude',self.round_report('a.json','APPROVED'))
        with self.assertRaisesRegex(m.StateError,'Fresh other-provider'):m.ready(self.repo,'MEL-002',state['revision'],'codex')
        state=m.inspect(self.repo,'MEL-002',state['revision'],'codex','codex',self.round_report('b.json','APPROVED',reviewer='codex'))
        self.assertEqual(m.ready(self.repo,'MEL-002',state['revision'],'codex')['status'],'ready')
        self.assertIn('unknown authorship (adopted): inherited branch',m.who(state))
    def test_unpublished_finding_still_benches_and_roster_sync_repairs(self):
        self.bench_with(1);self.commit_code();self.update(author=A('codex','weak-model'))
        report=self.round_report('r.json',findings=[{'id':'F1','severity':'high'}])
        m.review_round(self.repo,'MEL-001',self.current()['revision'],'codex','inspect',report)
        good=os.environ['MEL_ROSTER'];broken=self.parent/'roster-dir';broken.mkdir()
        with patch.dict(os.environ,{'MEL_ROSTER':str(broken)}):
            state=m.finding(self.repo,'MEL-001',self.current()['revision'],'codex','F1','high','codex','weak-model',report)
            self.assertEqual(state['findings'][-1]['id'],'F1')  # state recorded despite the roster failure
        self.assertNotIn('finding',[e['kind'] for e in m.roster() if e.get('task')=='MEL-001'])
        (self.repo/'next.py').write_text('n')
        with patch.object(m,'try_sync'):  # sync unavailable: the bench must still see F1
            with self.assertRaisesRegex(m.StateError,'benched'):self.update(author=A('codex','weak-model'))
        out=self.cli('roster-sync');self.assertEqual(out.returncode,0,out.stderr)
        self.assertEqual([e['kind'] for e in m.roster() if e.get('task')=='MEL-001'],['build','finding'])
        self.assertIn('0 roster event',self.cli('roster-sync').stdout);self.assertEqual(good,os.environ['MEL_ROSTER'])
    def test_no_file_redeclaration_of_benched_model_is_allowed(self):
        (self.repo/'w.py').write_text('w');entry=self.update(author=A('codex','weak-model'))['ledger'][-1]
        self.assertEqual(entry['files'],['w.py']);self.bench_with(2)
        self.run_git('add','w.py');self.run_git('commit','-m','fixture commit of declared work')
        entry=self.update(author=A('codex','weak-model'))['ledger'][-1]
        self.assertEqual((entry['files'],'bench_override' in entry),([],False))
        (self.repo/'x.py').write_text('x')
        with self.assertRaisesRegex(m.StateError,'benched'):self.update(author=A('codex','weak-model'))
    def test_who_lists_legacy_builders_without_ledger(self):
        path=m.location(self.repo,'MEL-001')/'state.json';state=json.loads(path.read_text())
        state['builders']=['claude'];path.write_bytes(m.encoded(state))  # MEL-002-shaped legacy state
        self.assertIn('claude: (recorded builder, no ledger)',self.cli('show','--who').stdout)
        out=self.cli('show','--brief');self.assertEqual(out.returncode,0,out.stderr)
        self.assertIn('builders: claude',out.stdout);self.assertNotIn('integration builders:',out.stdout)

    # MEL-006: expose uncertain integration authorship without rewriting history.
    def test_approximate_mel001_ledger_warns_in_both_cli_views(self):
        (self.repo/'code.py').write_text('inherited work')
        state=self.update(author=A('codex','gpt-6.1-sol'))
        reason='approximate: no recorded working copy to diff against (legacy state or pruned tree)'
        state['ledger'][-1]['attribution']=reason
        path=m.location(self.repo,'MEL-001')/'state.json';path.write_bytes(m.encoded(state))
        self.assertEqual(state['builders'],['codex'])  # actual MEL-001 shape: one recorded provider
        before=path.read_bytes()
        for flag in ('--who','--brief'):
            out=self.cli('show',flag);self.assertEqual(out.returncode,0,out.stderr)
            self.assertIn(reason,out.stdout);self.assertIn('integration builders: claude, codex',out.stdout)
            self.assertIn('codex/gpt-6.1-sol',out.stdout)
        self.assertIn('code.py',self.cli('show','--who').stdout)
        self.assertEqual(path.read_bytes(),before)

    def test_exact_ledger_has_no_approximate_warning_in_cli_views(self):
        (self.repo/'code.py').write_text('known work');self.update(author=A('codex','gpt-6.1-sol'))
        for flag in ('--who','--brief'):
            out=self.cli('show',flag);self.assertEqual(out.returncode,0,out.stderr)
            self.assertIn('codex/gpt-6.1-sol',out.stdout)
            self.assertNotIn('approximate:',out.stdout);self.assertNotIn('integration builders:',out.stdout)
        self.assertIn('code.py',self.cli('show','--who').stdout)

    def test_finding_cli_separates_blamed_author_from_changed_code_author(self):
        (self.repo/'code.py').write_text('original defect');self.update(author=A('codex','original-model'))
        report=self.round_report('r.json',findings=[{'id':i,'severity':'low'} for i in ('F0','F1')])
        m.review_round(self.repo,'MEL-001',self.current()['revision'],'codex','inspect',report)
        args=('finding','--actor','codex','--severity','low','--builder','codex','--model','original-model','--report',str(report))
        out=self.cli(*args,'--id','F0','--expected',str(self.current()['revision']))
        self.assertEqual(out.returncode,0,out.stderr)  # unchanged-code control
        (self.repo/'code.py').write_text('fix by a different author')
        before=self.current()
        out=self.cli(*args,'--id','F1','--expected',str(before['revision']))
        self.assertEqual(out.returncode,1);self.assertIn('declare its author',out.stderr)
        self.assertIn('separate update --builder ACTUAL_AUTHOR --model ACTUAL_MODEL',out.stderr)
        self.assertIn('finding --builder/--model',out.stderr)
        self.assertEqual(self.current(),before)  # includes revision, ledger and findings
        out=self.cli('update','--expected',str(before['revision']),'--actor','codex','--builder','claude','--model','fix-model')
        self.assertEqual(out.returncode,0,out.stderr)
        revision=self.current()['revision']
        out=self.cli(*args,'--id','F1','--expected',str(revision));self.assertEqual(out.returncode,0,out.stderr)
        state=self.current()
        self.assertEqual((state['findings'][-1]['builder'],state['findings'][-1]['model']),('codex','original-model'))
        self.assertEqual((state['ledger'][-1]['builder'],state['ledger'][-1]['model'],state['ledger'][-1]['files']),('claude','fix-model',['code.py']))

class BriefTests(unittest.TestCase):
    """Resume summaries without a Git fixture, state writes or helper CLI calls."""
    def setUp(self):
        self.folder = Path('unused-task-folder')
        self.state = {'task': 'MEL-006', 'status': 'planned', 'owner': 'claude', 'revision': 1,
                      'plan': {'path': 'plan.md', 'sha256': 'a'*64}, 'plan_review_waiver': 'fixture',
                      'criteria': {'A1': {'passed': False}}, 'builders': ['claude', 'codex'],
                      'blockers': [], 'handoff': None, 'recorded_tree': 'adopted-tree',
                      'adoption': {'attribution': 'unknown', 'reason': 'Runner did not record its model',
                                   'files': ['inherited.py']}}

    def test_brief_unknown_adoption_after_coordinator_declaration(self):
        # Exercise the real declaration, replacing only Git/roster access.
        with patch.object(m, 'work_tree', return_value='coordinator-tree'), \
             patch.object(m, 'changed_files', return_value=['coordinator.py']), \
             patch.object(m, 'repo_id', return_value='fixture-repo'), \
             patch.object(m, 'bench_status', return_value=None), \
             patch.object(m.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)):
            m.declare(self.folder, self.state, {'head': 'coordinator-head'}, A('claude', 'claude-opus-5-5'))
        self.assertEqual(self.state['ledger'][-1]['files'], ['coordinator.py'])
        before = m.encoded(self.state)
        out = m.brief(self.state, self.folder)
        with self.subTest('builders'):
            self.assertIn('builders: claude/claude-opus-5-5, codex', out.splitlines())
        with self.subTest('warning'):
            self.assertIn('unknown authorship (adopted): Runner did not record its model', out)
        self.assertEqual(m.encoded(self.state), before)

    def test_brief_mixed_known_unknown_adoption(self):
        self.state['ledger'] = [{'builder': 'claude', 'model': 'claude-opus-5-5',
                                 'files': ['inherited.py'], 'adopted': True}]
        before = m.encoded(self.state)
        out = m.brief(self.state, self.folder)
        with self.subTest('builders'):
            self.assertIn('builders: claude/claude-opus-5-5, codex', out.splitlines())
        with self.subTest('warning'):
            self.assertIn('unknown authorship (adopted): Runner did not record its model', out)
        self.assertEqual(m.encoded(self.state), before)

    def test_brief_exact_ledger_keeps_models_without_adoption_warning(self):
        self.state.pop('adoption')
        self.state['ledger'] = [A('claude', 'claude-opus-5-5'), A('codex', 'gpt-6.1-sol'),
                                A('codex', 'second-model')]
        out = m.brief(self.state, self.folder)
        self.assertIn('builders: claude/claude-opus-5-5, codex/gpt-6.1-sol, codex/second-model', out.splitlines())
        self.assertNotIn('unknown authorship', out)
        self.assertNotIn('attribution warning:', out)

    def test_brief_unknown_adoption_without_ledger(self):
        out = m.brief(self.state, self.folder)
        self.assertIn('builders: claude, codex', out.splitlines())
        self.assertIn('unknown authorship (adopted): Runner did not record its model', out)

class SingleProviderTests(unittest.TestCase):
    """MEL-009: one native provider is unavailable; the other reviews under an explicit, labelled rule."""
    PLAN = 'A1 proof: the fixture function returns the value.\n'
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.parent = Path(self.tmp.name).resolve(); self.repo = self.parent/'repo'; self.repo.mkdir()
        roster = patch.dict(os.environ, {'MEL_ROSTER': str(self.parent/'roster.jsonl')}); roster.start(); self.addCleanup(roster.stop)
        self.git('init','-b','claude/test'); self.git('config','user.name','Test'); self.git('config','user.email','test@example.invalid')
        self.plan = self.repo/'plan.md'; self.plan.write_text(self.PLAN)
        self.git('add','.'); self.git('commit','-m','baseline'); self.git('branch','main')
        self.proof = self.parent/'proof.txt'; self.proof.write_text('A1 verified in fixture')
        self.report = self.parent/'report.json'
    def git(self,*args):
        return subprocess.run(['git','-C',str(self.repo),*args],check=True,capture_output=True,text=True).stdout
    def cur(self): return m.load(self.repo,'MEL-001')
    def rev(self): return self.cur()['revision']
    def init(self,owner='claude',**kw):
        return m.init(self.repo,'MEL-001',owner,self.plan,['A1'],local_target='main',**kw)
    def enter(self,available='claude',plan_model='claude-sonnet-5-5',**kw):
        return m.single_provider_enter(self.repo,'MEL-001',self.rev(),available,available,'other provider out of capacity','user approved in chat',plan_model,**kw)
    def rep(self,reviewer,**kw):
        data={'verdict':'APPROVED','reviewer':reviewer,'coverage':['A1'],'findings':[],'limitations':['fixture'],
              'fresh_session':True,'built_nothing':True,'adversarial':['A1 may pass only on the fixture input; a wrong value would fail it.'],
              'plan_sha256':m.reference(self.plan)['sha256']}
        data.update(kw); self.report.write_text(json.dumps(data)); return self.report
    def approve(self,reviewer='claude',model='claude-opus-5-5',**kw):
        extra={k:kw.pop(k) for k in ('same_model','user_approval') if k in kw}
        self.rep(reviewer,**kw); return m.approve_plan(self.repo,'MEL-001',self.rev(),self.cur()['owner'],reviewer,self.report,model,**extra)
    def build(self,model='claude-sonnet-5-5',builder='claude'):
        (self.repo/'code.py').write_text('x=1\n'); self.git('add','code.py'); self.git('commit','-m','code'); self.git('branch','-f','main','HEAD')
        owner=self.cur()['owner']
        return m.update(self.repo,'MEL-001',self.rev(),owner,passed='A1',proof=self.proof,author=A(builder,model))
    def inspect(self,reviewer='claude',model='claude-opus-5-5',**kw):
        extra={k:kw.pop(k) for k in ('same_model','user_approval') if k in kw}
        self.rep(reviewer,**kw); return m.inspect(self.repo,'MEL-001',self.rev(),self.cur()['owner'],reviewer,self.report,model,**extra)
    def to_ready(self):
        self.init(); self.enter(); self.approve(); self.build(); self.inspect()
        return m.ready(self.repo,'MEL-001',self.rev(),'claude')

    def test_walkthrough_fresh_task_reaches_merged_with_label(self):
        label='SINGLE-PROVIDER REVIEW (other provider out of capacity, since '
        self.to_ready()
        self.assertTrue(self.cur()['review_label'].startswith(label))
        self.assertTrue(m.brief(self.cur(),m.location(self.repo,'MEL-001')).startswith(label))
        done=m.merged(self.repo,'MEL-001',self.rev(),'claude')
        self.assertEqual((done['status'],done['merge']['mode']),('merged','local'))
        self.assertTrue(done['review_label'].startswith(label))
        self.assertEqual(self.cur()['plan_review']['single_provider']['same_model'],None)
    def test_control_without_the_mode_both_gates_refuse(self):
        # CONTROL: passes on the old helper too; proves the walkthrough only succeeds because of the mode.
        self.init(); self.rep('claude')
        with self.assertRaises(m.StateError): m.approve_plan(self.repo,'MEL-001',1,'claude','claude',self.report,'claude-opus-5-5')
        self.report.write_text(json.dumps({'verdict':'APPROVED','reviewer':'codex','coverage':['A1'],'findings':[],'limitations':[],'plan_sha256':m.reference(self.plan)['sha256']}))
        m.approve_plan(self.repo,'MEL-001',1,'claude','codex',self.report)
        self.build()
        with self.assertRaises(m.StateError): self.inspect()
    def test_state_labelled_cli_output_keeps_stdout_json_and_label_on_stderr(self):
        self.to_ready()
        command=[sys.executable,'-B',str(SCRIPT),'merged','--repo',str(self.repo),'--task','MEL-001','--expected',str(self.rev()),'--actor','claude']
        done=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(done.returncode,0,done.stderr)
        self.assertEqual(json.loads(done.stdout)['status'],'merged'); self.assertIn('SINGLE-PROVIDER REVIEW',done.stderr)
    def test_cli_enter_and_leave_commands(self):
        self.init()
        base=[sys.executable,'-B',str(SCRIPT)]
        env=['--repo',str(self.repo),'--task','MEL-001','--actor','claude']
        refused=subprocess.run(base+['single-provider-enter',*env,'--expected','1','--single-provider','claude','--reason','codex out','--approved-by','user'],capture_output=True,text=True)
        self.assertEqual(refused.returncode,1); self.assertIn('plan-model',refused.stderr)
        entered=subprocess.run(base+['single-provider-enter',*env,'--expected','1','--single-provider','claude','--reason','codex out','--approved-by','user','--plan-model','claude-sonnet-5-5'],capture_output=True,text=True)
        self.assertEqual(entered.returncode,0,entered.stderr); self.assertEqual(json.loads(entered.stdout)['single_provider']['available'],'claude')
        left=subprocess.run(base+['single-provider-leave',*env,'--expected','2'],capture_output=True,text=True)
        self.assertEqual(left.returncode,0,left.stderr); self.assertNotIn('single_provider',json.loads(left.stdout))
    def test_mode_needs_attestations_model_and_adversarial_section(self):
        self.init(); self.enter()
        for bad in ({'fresh_session':False},{'built_nothing':False},{'adversarial':[]},{'adversarial':['']}):
            with self.assertRaises(m.StateError,msg=str(bad)): self.approve(**bad)
        with self.assertRaises(m.StateError): self.approve(model='')
    def test_same_model_refused_unless_labelled_and_approved(self):
        self.init(); self.enter()
        for model in ('claude-sonnet-5-5','Claude-Sonnet-5.5'):
            with self.assertRaises(m.StateError,msg=model): self.approve(model=model)
        with self.assertRaises(m.StateError): self.approve(model='claude-sonnet-5-5',same_model='strongest model available')
        with self.assertRaises(m.StateError): self.approve(model='claude-sonnet-5-5',user_approval='fine')
        self.approve(model='claude-sonnet-5-5',same_model='strongest model available',user_approval='user: yes, same model is ok')
        self.assertEqual(self.cur()['plan_review']['single_provider']['same_model']['reason'],'strongest model available')
    def test_inspect_model_must_differ_from_builder(self):
        self.init(); self.enter(); self.approve(); self.build('claude-opus-5-5')
        with self.assertRaises(m.StateError): self.inspect(model='Claude-Opus-5.5')
        self.inspect(model='claude-fable-5-1')
    def test_backend_reviewer_and_relabelled_builder_cannot_pass(self):
        self.init(); self.enter()
        with self.assertRaises(m.StateError): self.approve(reviewer='claude@openrouter')
        self.approve(); self.build(model='claude-opus-5-5',builder='claude@openrouter')
        # The native build declared as a backend one gets no relaxation: the same model still cannot review it.
        with self.assertRaises(m.StateError): self.inspect(model='claude-opus-5-5')
        with self.assertRaises(m.StateError): self.inspect(reviewer='claude@openrouter',model='gpt-6')
        self.inspect(model='claude-fable-5-1')
    def test_unavailable_provider_actions_are_refused(self):
        self.init(); self.enter(); self.approve(); self.build()
        owner=self.cur()['owner']
        with self.assertRaisesRegex(m.StateError,'other provider'): self.inspect(reviewer='codex',model='gpt-6.1-sol')
        with self.assertRaisesRegex(m.StateError,'other provider'): self.approve(reviewer='codex',model='gpt-6.1-sol')
        with self.assertRaisesRegex(m.StateError,'other provider'):
            m.transfer(self.repo,'MEL-001',self.rev(),owner,'codex',['c'],['p'],'n')
        with self.assertRaisesRegex(m.StateError,'other provider'):
            m.takeover(self.repo,'MEL-001',self.rev(),'codex','user said so')
        self.rep('codex')
        with self.assertRaisesRegex(m.StateError,'other provider'): m.review_round(self.repo,'MEL-001',self.rev(),owner,'inspect',self.report)
        (self.repo/'more.py').write_text('y=2\n'); self.git('add','more.py'); self.git('commit','-m','more')
        with self.assertRaisesRegex(m.StateError,'other provider'):
            m.update(self.repo,'MEL-001',self.rev(),owner,status='review_pending',author=A('codex','gpt-6.1-sol'))
    def test_owner_who_is_not_the_available_provider_cannot_act(self):
        self.init(); self.enter()
        state=self.cur(); state['single_provider']['available']='codex'; self.mutate_raw(state)
        # Owner claude, mode says codex only: handing to codex is allowed, claude acting is not.
        with self.assertRaisesRegex(m.StateError,'other provider'): m.update(self.repo,'MEL-001',self.rev(),'claude',status='implementing')
    def mutate_raw(self,state):
        (m.location(self.repo,'MEL-001')/'state.json').write_bytes(m.encoded(state))
    def test_codex_only_symmetry(self):
        self.init('codex'); self.enter('codex','gpt-6.1-sol')
        self.approve('codex','gpt-6.2-astra'); self.build('gpt-6.1-sol','codex'); self.inspect('codex','gpt-6.2-astra')
        done=m.ready(self.repo,'MEL-001',self.rev(),'codex'); self.assertIn('SINGLE-PROVIDER',done['review_label'])
        with self.assertRaisesRegex(m.StateError,'other provider'): self.inspect('claude','claude-opus-5-5')
    def test_enter_keeps_reviews_and_leave_voids_them_but_keeps_label(self):
        self.init('codex')
        # Other-provider review before entering stays valid after entering.
        self.rep('claude'); m.approve_plan(self.repo,'MEL-001',1,'codex','claude',self.report,'claude-opus-5-5')
        self.build('gpt-6.1-sol','codex'); self.inspect('claude','claude-opus-5-5',fresh_session=False)
        before=self.cur()['reviews']['claude']
        # An inspection by the other provider needs no mode; entering with codex available keeps it.
        m.single_provider_enter(self.repo,'MEL-001',self.rev(),'codex','codex','claude out of capacity','user approved','gpt-6.1-sol')
        self.assertEqual(self.cur()['reviews']['claude']['report'],before['report'])
        self.assertEqual(m.independent(self.cur()),{'codex':['claude','codex']})
        left=m.single_provider_leave(self.repo,'MEL-001',self.rev(),'codex')
        self.assertEqual(left['reviews'],{}); self.assertEqual(left['single_provider_history'][0]['left_revision'],left['revision'])
        self.assertEqual(m.independent(left),{'codex':['claude']})
    def test_label_persists_after_leave_in_rounds_and_merged_state(self):
        self.init(); self.enter(); self.approve(); self.build(); self.inspect()
        m.single_provider_leave(self.repo,'MEL-001',self.rev(),'claude')
        state=self.cur(); self.assertIn('single_provider',state['rounds'][0]); self.assertTrue(state['single_provider_history'])
        self.report=self.parent/'report-codex.json'  # the plan approval's report file must stay unchanged
        self.rep('codex'); m.inspect(self.repo,'MEL-001',self.rev(),'claude','codex',self.report,'gpt-6.1-sol')
        m.ready(self.repo,'MEL-001',self.rev(),'claude'); done=m.merged(self.repo,'MEL-001',self.rev(),'claude')
        self.assertIn('SINGLE-PROVIDER REVIEW',done['review_label'])
    def test_revise_plan_in_mode_needs_plan_model(self):
        self.init(); self.enter(); self.approve()
        self.plan.write_text(self.PLAN+'more\n'); self.git('commit','-qam','plan')
        with self.assertRaisesRegex(m.StateError,'plan-model'): m.revise_plan(self.repo,'MEL-001',self.rev(),'claude',self.plan,'waived',A('claude','claude-sonnet-5-5'))
        result=m.revise_plan(self.repo,'MEL-001',self.rev(),'claude',self.plan,'',A('claude','claude-sonnet-5-5'),plan_model='claude-sonnet-5-5')
        self.assertEqual(result['plan_model'],'claude-sonnet-5-5')
    def test_enter_requires_plan_model_before_plan_approval_and_valid_fields(self):
        self.init()
        with self.assertRaisesRegex(m.StateError,'plan-model'): m.single_provider_enter(self.repo,'MEL-001',1,'claude','claude','r','u',None)
        for args in (('claude','','u','m'),('claude','r','','m'),('bogus','r','u','m')):
            with self.assertRaises(m.StateError): m.single_provider_enter(self.repo,'MEL-001',1,'claude',*args)
        with self.assertRaises(m.StateError): m.single_provider_enter(self.repo,'MEL-001',1,'claude','codex','r','u','m')
        with self.assertRaises(m.StateError): m.init(self.repo,'MEL-002','claude',self.plan,['A1'],single_provider='claude',reason='r',approved_by='u')
    def test_fail_closed_on_unknown_authorship_and_legacy_but_not_untouched_owner(self):
        self.init(); self.enter()
        state=self.cur()
        self.assertEqual(m.authorship_models(state),set())  # owner builder with no ledger entry on a tracked task is accepted
        with self.assertRaisesRegex(m.StateError,'unknown authorship'): m.authorship_models({**state,'adoption':{'attribution':'unknown'}})
        legacy=dict(state); legacy.pop('recorded_fingerprint')
        with self.assertRaisesRegex(m.StateError,'Legacy'): m.authorship_models(legacy)
    def test_control_legacy_state_keeps_every_old_rule(self):
        # CONTROL: no single_provider field, so nothing about reviewers changes (also passes on the old helper).
        self.init('codex')
        self.assertNotIn('single_provider',self.cur()); self.assertEqual(m.independent(self.cur()),{'codex':['claude']})
        self.rep('codex')
        with self.assertRaises(m.StateError): m.approve_plan(self.repo,'MEL-001',1,'codex','codex',self.report)
        self.assertNotIn('SINGLE-PROVIDER',m.brief(self.cur(),m.location(self.repo,'MEL-001')))
    def test_needs_clarification_marker_refuses_plan_approval(self):
        self.plan.write_text(self.PLAN+'Scope: [NEEDS CLARIFICATION: which API?]\n'); self.git('commit','-qam','plan')
        self.init(); self.rep('codex')
        with self.assertRaisesRegex(m.StateError,'CLARIFICATION'): m.approve_plan(self.repo,'MEL-001',1,'claude','codex',self.report)
        self.plan.write_text(self.PLAN); self.git('commit','-qam','clean')
        m.revise_plan(self.repo,'MEL-001',1,'claude',self.plan,'',A('claude','m'))  # revised plan is clean
        self.rep('codex'); m.approve_plan(self.repo,'MEL-001',2,'claude','codex',self.report)
    def test_unproved_criteria_recorded_with_warning_on_stderr(self):
        self.plan.write_text('A1 must work.\nA10 proof: other.\n'); self.git('commit','-qam','plan')
        self.init(); self.rep('codex')
        command=[sys.executable,'-B',str(SCRIPT),'approve-plan','--repo',str(self.repo),'--task','MEL-001','--expected','1','--actor','claude','--reviewer','codex','--report',str(self.report)]
        done=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(done.returncode,0,done.stderr)
        self.assertEqual(json.loads(done.stdout)['plan_review']['unproved_criteria'],['A1'])  # stdout still parses as JSON
        self.assertIn('no proof line for criteria: A1',done.stderr); self.assertNotIn('WARNING',done.stdout)
        self.assertEqual(m.load(self.repo,'MEL-001')['plan_review']['unproved_criteria'],['A1'])
    def test_proved_criteria_leave_no_warning(self):
        self.init(); self.rep('codex'); state=m.approve_plan(self.repo,'MEL-001',1,'claude','codex',self.report)
        self.assertEqual(state['plan_review']['unproved_criteria'],[])

if __name__=='__main__':unittest.main()
