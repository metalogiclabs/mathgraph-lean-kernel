import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('macros',Path(__file__).resolve().parents[1]/'source_macro_discovery.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class MacroTests(unittest.TestCase):
 def test_acquires_repeated_global_function_prefix(self):
  proof='theorem t (a b : Nat) : True := by\n  have h := f.longName a b\n  have k := f.longName a b\n  have q := f.longName a b\n  have r := f.longName a b\n  trivial\n'
  rows=m.discover({'name':'t','proof':proof})
  chosen=next(r for r in rows if r['discovered'].get('expression')=='f.longName a b')
  self.assertIn('  let mg_acquired := f.longName a b\n',chosen['proof'])
  self.assertEqual(chosen['proof'].count('f.longName a b'),1)
  self.assertEqual(chosen['proof'].split(':= by')[0],proof.split(':= by')[0])
 def test_does_not_hoist_local_binders(self):
  proof='theorem t : True := by\n  intro y\n  have h := f.longName y y\n  have k := f.longName y y\n  have q := f.longName y y\n  have r := f.longName y y\n  trivial\n'
  self.assertFalse(any(' y' in r['discovered'].get('expression','') for r in m.discover({'name':'t','proof':proof})))
 def test_preserves_directed_rewrite_order_and_typed_observer(self):
  proof='theorem t : True := by\n  have he := congrArg (fun g => d g) h\n  rw [a] at he\n  rw [b, c] at he\n  exact he\n'
  rows=m.discover({'name':'t','proof':proof})
  r=next(r for r in rows if r['operator']=='merge_directed_rewrites')
  self.assertIn('rw [a, b, c] at he',r['proof'])
  self.assertIn('congrArg (fun g => d g) h',r['proof'])
 def test_lambda_macro_and_candidate_status(self):
  proof='theorem t (p : Nat → Prop) : True := by\n  have a := List.filter (fun c => p c ∧ p c) xs\n  have b := List.filter (fun c => p c ∧ p c) ys\n  trivial\n'
  rows=m.discover({'name':'t','proof':proof})
  self.assertTrue(any(r['discovered'].get('expression')=='(fun c => p c ∧ p c)' for r in rows))
  self.assertTrue(all(r['status']=='CANDIDATE_UNVERIFIED' for r in rows))
if __name__=='__main__':unittest.main()
