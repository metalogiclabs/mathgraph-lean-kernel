import copy
import unittest

from reviewer import SCHEMA, Reviewer, patch_index, validate_structure
from test_reuse_rule import index


class ReviewerContracts(unittest.TestCase):
    def valid(self):
        return dict(schema=SCHEMA,completed=True,correctness_passed=True,source_and_binary_stable=True,
                    repetitions=1,cycles=1,requested_profiles=['original'],profiles={'original':{}})

    def test_fake_passed_zero_work_and_profile_substitution_refuse(self):
        validate_structure(self.valid(),True)
        for mutate in (lambda r:r.update(repetitions=0),lambda r:r.update(repetitions=True),
                       lambda r:r.update(cycles=False),lambda r:r.update(profiles={},requested_profiles=[]),
                       lambda r:r.update(requested_profiles=['original','original']),
                       lambda r:r.update(requested_profiles=['foreign'],profiles={'foreign':{}}),
                       lambda r:r.update(correctness_passed=False)):
            report=self.valid();mutate(report)
            with self.subTest(report=report),self.assertRaises(ValueError):validate_structure(report,True)
        with self.assertRaises(ValueError):validate_structure(self.valid(),False)

    def test_typed_predecessor_patch_rejects_topology_changes(self):
        before=index();after=index(True)
        patch=dict(schema='mathgraph.export-identity-baseline-patch.v1',count=4,
                   declarations=after['declarations'][:3],builtins={})
        self.assertEqual(patch_index(before,patch),after)
        for mutate in (lambda p:p.update(count=True),lambda p:p['declarations'][0].update(deps=[]),
                       lambda p:p['declarations'].append(copy.deepcopy(p['declarations'][0])),
                       lambda p:p['declarations'][0].update(own='bad')):
            bad=copy.deepcopy(patch);mutate(bad)
            with self.subTest(bad=bad),self.assertRaises(ValueError):patch_index(before,bad)

    def test_parent_head_or_evidence_substitution_refuse(self):
        reviewer=Reviewer.__new__(Reviewer)
        good=dict(status='VERIFIED',evidence_id='b'*64,previous_evidence='a'*64,
                  revision_chain=dict(head_id='c'*64,parent_head='d'*64,parent_evidence='a'*64,
                                      revision=1,source_capture_id='e'*64))
        reviewer.link(good,'d'*64,'a'*64,1)
        for mutate in (lambda r:r.update(previous_evidence='f'*64),
                       lambda r:r['revision_chain'].update(parent_head='f'*64),
                       lambda r:r['revision_chain'].update(revision=True),
                       lambda r:r['revision_chain'].update(parent_evidence='f'*64)):
            bad=copy.deepcopy(good);mutate(bad)
            with self.subTest(bad=bad),self.assertRaises(ValueError):reviewer.link(bad,'d'*64,'a'*64,1)


if __name__=='__main__':unittest.main()
