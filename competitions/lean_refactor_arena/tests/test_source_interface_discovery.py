import importlib.util
from pathlib import Path
import unittest
P=Path(__file__).resolve().parents[1]/'source_interface_discovery.py'
spec=importlib.util.spec_from_file_location('discovery',P)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class DiscoveryTests(unittest.TestCase):
    def test_discovers_witness_observer_and_normalizers_without_spec(self):
        source='theorem toy (h : x = y) : f x = f y := by\n  have out := congrArg (fun z => f z) h\n  rw [a, b] at out\n  rw [c] at out\n  exact out\n'
        rows=m.discover({'name':'toy','proof':source})
        fused=next(r for r in rows if r['operator']=='fuse_observation_only')
        self.assertIn('simpa only [a, b, c] using congrArg (fun z => f z) h',fused['proof'])
        self.assertEqual(fused['discovered']['witness'],'h')
        self.assertEqual(fused['discovered']['observer'],'(fun z => f z)')
        self.assertEqual(source.split(':= by')[0],fused['proof'].split(':= by')[0])
    def test_rejects_nonterminal_or_mixed_scope(self):
        for tail in ['  exact other\n','  exact out\n  exact out\n']:
            s='theorem t : True := by\n  have out := congrArg (fun z => f z) h\n  rw [r] at out\n'+tail
            self.assertFalse(any(r['operator'].startswith('fuse') for r in m.discover({'name':'t','proof':s})))
    def test_header_observer_is_not_a_candidate_site(self):
        p='theorem t {x y : Nat} (h : x = y) (_ : congrArg (fun z => z) h = h) : x = y := by\n  exact h\n'
        self.assertEqual(m.discover({'name':'t','proof':p}),[])
    def test_preserves_parent_and_deduplicates(self):
        row={'name':'t','proof':'theorem t (h : x = y) : f x = f y := by\n  exact congrArg (fun z => f z) h\n'}
        before=dict(row);a=m.discover(row);b=m.discover(row)
        self.assertEqual(row,before);self.assertEqual(a,b)
        self.assertEqual(len({x['proof_sha256'] for x in a}),len(a))
        self.assertTrue(all(x['status']=='CANDIDATE_UNVERIFIED' for x in a))
    def test_fail_closed_on_comments_or_admission(self):
        for p in ['theorem t : True := by\n  -- congrArg f h\n  trivial','theorem t : True := by\n  sorry']:
            self.assertEqual(m.discover({'name':'t','proof':p}),[])

if __name__=='__main__':unittest.main()
