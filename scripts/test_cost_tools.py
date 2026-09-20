import unittest
import cost_tools as m

class Tests(unittest.TestCase):
    def test_callgrind_excludes_recursive_edge_cost(self):
        text='events: Ir\nsummary: 30\nfn=(1) f\n0 10\ncfn=(1)\ncalls=2 0\n0 100\nfn=(2) g\n0 20\n'
        result=m.parse_callgrind(text)
        self.assertEqual(result['total_ir'],30)
        self.assertEqual(result['self_ir'],{'f':10,'g':20})
    def test_callgrind_resolves_forward_name(self):
        text='events: Ir\nsummary: 5\nfn=(1) a\n0 2\ncfn=(2) b\ncalls=1 0\n0 3\nfn=(2)\n0 3\n'
        self.assertEqual(m.parse_callgrind(text)['self_ir']['b'],3)
    def test_callgrind_rejects_bad_total(self):
        with self.assertRaises(ValueError):m.parse_callgrind('events: Ir\nsummary: 99\nfn=(1) a\n0 2\n')
    def test_cost_summary_is_weighted_not_count_ranked(self):
        obj={'schema':1,'seed':17,'root_calls':100,'nested_calls':0,'samples':11,
             'sample_denominator':1024,'timer_floor_ns':20,'rows':[
             {'shape':'ptr','raw':'plain','samples':10,'force_ns':100,'compare_ns':100,'max_ns':20},
             {'shape':'pi_pi','raw':'thunk','samples':1,'force_ns':1000,'compare_ns':9000,'max_ns':10000}]}
        self.assertEqual(m.summarize_cost(obj)['largest_shape'],'pi_pi')
    def test_cost_summary_rejects_missing_fields(self):
        with self.assertRaises(ValueError):m.summarize_cost({'samples':2})
    def test_cost_summary_rejects_nonreconciled_samples(self):
        o={'schema':1,'seed':1,'root_calls':3,'nested_calls':0,'samples':2,'sample_denominator':1024,'timer_floor_ns':20,'rows':[]}
        with self.assertRaises(ValueError):m.summarize_cost(o)

if __name__=='__main__':unittest.main()

class PatchTests(unittest.TestCase):
    def test_anchor_rejects_duplicates(self):
        from apply_qckn_conv_cost_probe import replace_once
        with self.assertRaises(ValueError): replace_once('xx','x','y','duplicate')
    def test_anchor_rejects_missing(self):
        from apply_qckn_conv_cost_probe import replace_once
        with self.assertRaises(ValueError): replace_once('','x','y','missing')
    def test_original_route_stays_available(self):
        from pathlib import Path
        s=Path(__file__).with_name('apply_qckn_conv_cost_probe.py').read_text()
        self.assertIn('return self.conv_types_at(depth, a, b);',s)
        self.assertIn('self.unbudgeted(|s| {',s)
        self.assertNotIn('infer_value(InferOnly',s)
    def test_instrumentation_does_not_store_value_pointers(self):
        from pathlib import Path
        s=Path(__file__).with_name('qckn_conv_cost_probe.rs').read_text()
        self.assertIn('rows: [Row; 48]',s)
        self.assertNotIn('HashMap',s)
        self.assertNotIn('HashSet',s)
