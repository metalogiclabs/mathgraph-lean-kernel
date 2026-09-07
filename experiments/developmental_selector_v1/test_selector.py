import json, tempfile, unittest
from pathlib import Path
from controller import PREDICATES, compile_policy, safe_decision, digest, validate
from repair_v88 import OLD_BLOB, OLD, NEW, blob, transform, paths, execute
ROOT=Path(__file__).resolve().parent

class SelectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.history=json.loads((ROOT/'history.json').read_text())
        cls.policy=json.loads((ROOT/'FROZEN_POLICY.json').read_text())
        cls.source=(ROOT.parent/'measure_prune_dm_v88.py').read_text()
        assert blob(cls.source.encode())==OLD_BLOB
    def test_frozen_discovery(self):
        fitted=compile_policy(self.history['training'])
        self.assertEqual(digest(fitted),digest(self.policy))
        self.assertEqual(fitted['training_errors'],0)
    def test_heldout_without_refitting(self):
        self.assertEqual([safe_decision(self.policy,r['state']) for r in self.history['heldout']],['REJECT','REPAIR'])
    def test_ablation_changes_choice(self):
        baseline={'default':'PUSH','clauses':[]}
        self.assertEqual(safe_decision(baseline,self.history['heldout'][-1]['state']),'PROBE')
        self.assertEqual(safe_decision(self.policy,self.history['heldout'][-1]['state']),'REPAIR')
    def test_unknown_and_ambiguous_abstain(self):
        self.assertEqual(safe_decision(self.policy,dict.fromkeys(PREDICATES,False)),'PROBE')
        ambiguous=dict.fromkeys(PREDICATES,False)
        ambiguous['blocked']=True;ambiguous['measured_regression']=True
        self.assertEqual(safe_decision(self.policy,ambiguous),'PROBE')
    def test_no_identity_or_unverified_outcome(self):
        r=dict(self.history['training'][0]);r['state']=dict(r['state'],benchmark='mathlib')
        with self.assertRaises(ValueError):validate(r)
        r=dict(self.history['training'][0]);r['outcome']='verified-by-llm'
        with self.assertRaises(ValueError):validate(r)
    def test_no_release_promotion(self):
        self.assertNotIn('PROMOTE',safe_decision(self.policy,self.history['training'][0]['state']))
    def test_actual_source_roundtrip(self):
        self.assertEqual(transform(self.source).replace(NEW,OLD,1),self.source)
    def test_reject_unknown_source(self):
        with self.assertRaises(ValueError):transform(self.source.replace(OLD,''))
    def test_manifest_exact_names(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d)/'arena/_build/tests';base.mkdir(parents=True)
            for n in ('init-prelude','cedar','mathlib'):(base/(n+'.ndjson')).write_text('test')
            self.assertEqual(len(paths(d)),3)
            (base/'init-prelude.ndjson').unlink();(base/'std.ndjson').write_text('test')
            with self.assertRaises(FileNotFoundError):paths(d)
    def test_frozen_authorization_and_no_mutation_on_failure(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);src=d/'measure.py';src.write_text(self.source)
            pp=d/'FROZEN_POLICY.json';dp=d/'decision.json'
            pp.write_text(json.dumps(self.policy));dp.write_text((ROOT/'decision.json').read_text())
            (d/'history.json').write_text(json.dumps(self.history))
            execute(src,pp,dp,check=True)
            self.assertEqual(src.read_text(),self.source)
            bad=json.loads(dp.read_text());bad['action']='PUSH';dp.write_text(json.dumps(bad))
            with self.assertRaises(ValueError):execute(src,pp,dp)
            self.assertEqual(src.read_text(),self.source)
            dp.write_text((ROOT/'decision.json').read_text());execute(src,pp,dp)
            self.assertEqual(src.read_text(),transform(self.source))
            with self.assertRaises(ValueError):execute(src,pp,dp)
if __name__=='__main__':unittest.main()
