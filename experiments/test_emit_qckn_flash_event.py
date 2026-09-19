import hashlib
import json
import unittest

from emit_qckn_flash_event import build_event, canonical


class LeanFlashEventEmitterTests(unittest.TestCase):
    def test_direct_var_event_is_canonical_and_bound_to_evidence(self):
        evidence, event = build_event(
            source_commit="0123456789abcdef0123456789abcdef01234567"
        )
        evidence_text = canonical(evidence)
        event_text = canonical(event)

        self.assertEqual(event["schema"], "qckn-flash-external-event-v1")
        self.assertEqual(event["event_kind"], "capability_admission")
        self.assertEqual(
            event["source_evidence_sha256"],
            hashlib.sha256(evidence_text.encode()).hexdigest(),
        )
        self.assertEqual(
            event["payload_sha256"],
            hashlib.sha256(canonical(event["payload"]).encode()).hexdigest(),
        )
        self.assertEqual(event_text, canonical(json.loads(event_text)))
        self.assertEqual(
            event["payload"]["capability"]["capability_id"],
            "lean:direct-var:v1",
        )
        self.assertEqual(
            event["payload"]["capability"]["provenance_ids"],
            [
                "commit:74dc5ddb4584e1254f5687615e5b02795b8dc6f3",
                "run:35380841937",
                "run:35380563756",
            ],
        )
        self.assertEqual(evidence["semantic"]["exports"], 409)
        self.assertEqual(evidence["semantic"]["mismatches"], 0)
        self.assertGreater(evidence["native"]["wall_speedup"], 1.0)

    def test_source_commit_must_be_full_lowercase_sha(self):
        with self.assertRaises(ValueError):
            build_event(source_commit="bad")


if __name__ == "__main__":
    unittest.main()
