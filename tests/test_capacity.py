"""Usage-window decisions from fixture readings. No model calls; real Codex/Claude files are never read."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/mohit-engineering-loop/scripts/capacity.py'
spec = importlib.util.spec_from_file_location('capacity', SCRIPT)
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)
NOW = datetime(2026, 10, 24, 15, 0, tzinfo=timezone.utc)

def event(five, week, stamp='2026-10-24T14:55:00Z', resets=1793000000):
    return json.dumps({'timestamp': stamp, 'type': 'event_msg', 'payload': {'type': 'token_count', 'rate_limits': {
        'plan_type': 'plus', 'primary': {'used_percent': five, 'window_minutes': 300, 'resets_at': resets},
        'secondary': {'used_percent': week, 'window_minutes': 10080, 'resets_at': resets}}}})

class CapacityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.dir = Path(self.tmp.name)
        self.limits = c.thresholds(self.dir / 'absent.json')
    def log(self, *lines):
        path = self.dir / 'codex.jsonl'; path.write_text('\n'.join(lines) + '\n', encoding='utf-8'); return path
    def codex(self, *lines):
        return c.assess(c.codex_reading(self.log(*lines)), self.limits, NOW)
    def test_thresholds_map_to_decisions(self):
        for five, week, expected in ((10, 10, 'go'), (85, 10, 'no-new-large-work'), (10, 75, 'no-new-large-work'),
                                     (95, 10, 'checkpoint-and-handoff'), (10, 91, 'checkpoint-and-handoff')):
            self.assertEqual(self.codex(event(five, week))['decision'], expected, (five, week))
    def test_last_reading_wins_and_plan_is_reported(self):
        result = self.codex(event(95, 95), event(5, 5))
        self.assertEqual((result['decision'], result['plan']), ('go', 'plus'))
    def test_limit_error_after_reading_outranks_percentages(self):
        hit = 'ERROR: You have hit your usage limit. Try again at 2:10 PM.'
        self.assertEqual(self.codex(event(5, 5), hit)['decision'], 'checkpoint-and-handoff')
        self.assertEqual(self.codex(hit, event(5, 5))['decision'], 'go')
        failed = json.dumps({'type': 'turn.failed', 'error': {'message': "You've hit your usage limit."}})
        self.assertEqual(self.codex(event(5, 5), failed)['decision'], 'checkpoint-and-handoff')
    def test_limit_phrase_inside_tool_output_is_not_a_limit(self):
        # Seen 2026-10-24: Codex read a log that quoted the phrase; that is not its own limit.
        quoted = json.dumps({'type': 'item.completed', 'item': {'type': 'command_execution', 'aggregated_output': 'ERROR: hit your usage limit'}})
        self.assertEqual(self.codex(event(5, 5), quoted)['decision'], 'go')
    def test_stale_reading_is_unknown_not_go(self):
        result = self.codex(event(5, 5, stamp='2026-10-24T10:00:00Z'))
        self.assertEqual(result['decision'], 'unknown'); self.assertIn('min old', result['notes'][0])
    def test_incomplete_or_undated_reading_is_never_go(self):
        # MEL-004 I4: go needs a dated reading of both windows; an exhausted window still wins.
        undated = json.loads(event(5, 5)); undated.pop('timestamp')
        self.assertEqual(self.codex(json.dumps(undated))['decision'], 'unknown')
        def only_five(used):
            data = json.loads(event(used, 5)); data['payload']['rate_limits'].pop('secondary'); return json.dumps(data)
        result = self.codex(only_five(5))
        self.assertEqual(result['decision'], 'unknown'); self.assertIn('no weekly reading', result['notes'])
        self.assertEqual(self.codex(only_five(95))['decision'], 'checkpoint-and-handoff')
        self.assertEqual(self.codex(event(85, 5, stamp='2026-10-24T10:00:00Z'))['decision'], 'unknown')
        self.assertEqual(self.codex(event(95, 5, stamp='2026-10-24T10:00:00Z'))['decision'], 'checkpoint-and-handoff')
    def test_reset_window_counts_as_empty(self):
        past = int(datetime(2026, 10, 24, 14, 0, tzinfo=timezone.utc).timestamp())
        self.assertEqual(self.codex(event(99, 10, resets=past))['decision'], 'go')
    def test_naive_observed_at_is_unknown_unless_a_window_is_exhausted(self):
        for used,expected in ((5,'unknown'),(95,'checkpoint-and-handoff')):
            with self.subTest(used=used):
                result=self.codex(event(used,5,stamp='2026-10-24T14:55:00'))
                self.assertEqual(result['decision'],expected)
                self.assertIn('reading has no usable timestamp',result['notes'])
    def test_naive_claude_reset_is_not_counted_as_reset(self):
        path=self.dir/'claude.json'
        for used,expected in ((5,'unknown'),(95,'checkpoint-and-handoff')):
            with self.subTest(used=used):
                path.write_text(json.dumps({'observed_at':'2026-10-24T14:55:00Z','plan':{'windows':[
                    {'label':'5-hour limit','percentUsed':used,'resetsAt':'2026-10-24T14:00:00'},
                    {'label':'Weekly all models','percentUsed':5}]}}),encoding='utf-8')
                result=c.assess(c.claude_reading(path),self.limits,NOW)
                self.assertEqual(result['decision'],expected)
                self.assertIn('five_hour window has no usable reset timestamp',result['notes'])
                self.assertEqual(result['windows'][0]['decision'],c.decide(used,'five_hour',self.limits))
    def test_missing_reading_is_unknown(self):
        self.assertEqual(c.assess(c.codex_reading(home=self.dir / 'none'), self.limits, NOW)['decision'], 'unknown')
    def test_claude_usage_json_and_custom_thresholds(self):
        path = self.dir / 'claude.json'
        path.write_text(json.dumps({'observed_at': '2026-10-24T14:59:00Z', 'plan': {'plan': 'Max', 'windows': [
            {'label': '5-hour limit', 'percentUsed': 60, 'resetsAt': '2026-10-24T18:00:00Z'},
            {'label': 'Weekly · all models', 'percentUsed': 20, 'resetsAt': '2026-10-31T10:00:00Z'}]}}), encoding='utf-8')
        self.assertEqual(c.assess(c.claude_reading(path), self.limits, NOW)['decision'], 'go')
        strict = self.dir / 'strict.json'; strict.write_text(json.dumps({'five_hour': {'no_new_work': 50}}), encoding='utf-8')
        result = c.assess(c.claude_reading(path), c.thresholds(strict), NOW)
        self.assertEqual((result['decision'], result['plan']), ('no-new-large-work', 'Max'))
    def test_cli_prints_one_line_per_provider_without_traceback(self):
        out = subprocess.run([sys.executable, '-B', str(SCRIPT), '--codex-log', str(self.log(event(5, 5))),
                              '--thresholds', str(self.dir / 'absent.json')], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0); self.assertTrue(out.stdout.startswith('codex [plus]:'))
        bad = subprocess.run([sys.executable, '-B', str(SCRIPT), '--codex-home', str(self.dir / 'none'), '--claude', str(self.dir / 'missing.json')], capture_output=True, text=True)
        self.assertEqual(bad.returncode, 1); self.assertNotIn('Traceback', bad.stderr)

    def test_cli_accepts_wrapped_and_raw_claude_plans_with_equivalent_readings(self):
        stamp=datetime.now(timezone.utc).isoformat()
        plan={'plan':'Max','windows':[{'label':'5-hour limit','percentUsed':85},
                                    {'label':'Weekly all models','percentUsed':20}]}
        readings=[]
        for data in ({'observed_at':stamp,'plan':plan},{**plan,'observed_at':stamp}):
            path=self.dir/'claude.json';path.write_text(json.dumps(data),encoding='utf-8')
            out=subprocess.run([sys.executable,'-B',str(SCRIPT),'--claude',str(path),'--codex-home',str(self.dir/'none'),
                                '--thresholds',str(self.dir/'absent.json'),'--json'],capture_output=True,text=True)
            self.assertEqual(out.returncode,0,out.stderr);self.assertNotIn('Traceback',out.stderr)
            reading=json.loads(out.stdout)[1];reading.pop('source');readings.append(reading)
        self.assertEqual(readings[0],readings[1])
        self.assertEqual((readings[1]['plan'],readings[1]['decision']),('Max','no-new-large-work'))
        self.assertEqual([(w['window'],w['used']) for w in readings[1]['windows']],[('five_hour',85.0),('weekly',20.0)])

    def test_cli_rejects_malformed_claude_shapes_without_traceback(self):
        for data in ([],None,{'plan':[]},{'plan':'Max','windows':{}},{'plan':{'windows':[None]}},
                     {'plan':'Max','windows':[{'label':42,'percentUsed':5}]},
                     {'plan':'Max','windows':[{'label':'5-hour limit'}]}):
            with self.subTest(data=data):
                path=self.dir/'claude.json';path.write_text(json.dumps(data),encoding='utf-8')
                out=subprocess.run([sys.executable,'-B',str(SCRIPT),'--claude',str(path),'--codex-home',str(self.dir/'none'),
                                    '--thresholds',str(self.dir/'absent.json')],capture_output=True,text=True)
                self.assertEqual(out.returncode,1);self.assertTrue(out.stderr.startswith('ERROR:'),out.stderr)
                self.assertNotIn('Traceback',out.stderr)

if __name__ == '__main__':
    unittest.main()
