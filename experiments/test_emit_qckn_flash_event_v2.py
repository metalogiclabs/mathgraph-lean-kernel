import hashlib
import json
import unittest

from emit_qckn_flash_event_v2 import build_event, canonical


class LeanFlashEventEmitterV2Tests(unittest.TestCase):
    def test_unfold_event_is_canonical_and_bound_to_qualification(self):
        evidence,event=build_event(
            source_commit="0123456789abcdef0123456789abcdef01234567"
        )
        evidence_text=canonical(evidence)
        self.assertEqual(event["event_kind"],"capability_admission")
        self.assertEqual(event["event_id"],"lean:ordinary-unfold-neutral:v1")
        self.assertEqual(
            event["source_evidence_sha256"],
            hashlib.sha256(evidence_text.encode()).hexdigest(),
        )
        self.assertEqual(
            event["payload_sha256"],
            hashlib.sha256(canonical(event["payload"]).encode()).hexdigest(),
        )
        self.assertEqual(evidence["semantic"]["exports"],409)
        self.assertEqual(evidence["semantic"]["mismatches"],0)
        self.assertGreater(evidence["native"]["wall_speedup"],1.0)
        self.assertLess(
            evidence["callgrind"]["candidate_ir"],
            evidence["callgrind"]["ablated_ir"],
        )
        self.assertEqual(
            event["payload"]["capability"]["dependencies"],
            ["lean:direct-var:v1"],
        )
        self.assertEqual(canonical(event),canonical(json.loads(canonical(event))))

    def test_source_commit_must_be_full_sha(self):
        with self.assertRaises(ValueError):
            build_event(source_commit="bad")


if __name__=="__main__":
    unittest.main()
