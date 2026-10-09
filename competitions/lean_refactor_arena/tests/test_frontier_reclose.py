import hashlib
import json
import unittest

from frontier_reclose import decide, reclose_packet


NAME = "Example.example_theorem"
PIN = "lean-refactor-pinned-sha"
VERSIONS = ["v4.32.0", "v4.31.0"]


def proof(label):
    return f"theorem example_theorem : True := by\n  {label}"


def entry(label):
    return {"name": NAME, "label": label, "proof": proof(label)}


def evidence(label, length, hb, objective, *, versions=VERSIONS, **overrides):
    p = proof(label)
    r = {
        "name": NAME, "candidate_label": label,
        "proof_sha256": hashlib.sha256(p.encode()).hexdigest(),
        "public_harness_sha": PIN,
        "all_versions": True,
        "compiled": True,
        "statement_ok": True,
        "eligible": True,
        "compat": {v: True for v in versions},
        "per_version": [{"version": v, "tested": True, "ok": True} for v in versions],
        "length": length,
        "heartbeats": hb,
        "reference_length": 200,
        "reference_heartbeats": 1000,
        "survival_pct": 100,
        "objective_sum_pct": objective,
    }
    r.update(overrides)
    return r


class FrontierTests(unittest.TestCase):
    def setUp(self):
        self.control = entry("control")
        self.better = entry("better")
        self.old_score = evidence("control", 100, 500, 100)
        self.new_score = evidence("better", 80, 400, 120)

    def decision(self, rows=None, scores=None):
        return decide(rows or [self.control, self.better],
                      scores or [self.old_score, self.new_score],
                      expected_name=NAME, required_versions=VERSIONS,
                      expected_public_sha=PIN, incumbent_label="control")

    def test_selects_verified_dominating_candidate(self):
        result = self.decision()
        self.assertEqual(result["selected_label"], "better")
        self.assertEqual(result["objective_gain"], 20.0)
        self.assertEqual(result["frontier_labels"], ["better"])
        self.assertEqual(result["admission"]["better"]["status"], "WARRANTED")

    def test_does_not_accept_primary_only_hundred_percent_survival(self):
        incomplete = evidence("better", 80, 400, 120,
                              versions=["v4.32.0"])
        result = self.decision(scores=[self.old_score, incomplete])
        self.assertEqual(result["selected_label"], "control")
        self.assertEqual(result["admission"]["better"]["status"], "UNKNOWN")

    def test_explicit_failed_version_is_rejected(self):
        bad = evidence("better", 80, 400, 120)
        bad["compat"]["v4.31.0"] = False
        bad["per_version"][1]["ok"] = False
        result = self.decision(scores=[self.old_score, bad])
        self.assertEqual(result["selected_label"], "control")
        self.assertEqual(result["admission"]["better"]["status"], "REJECTED")

    def test_wrong_proof_digest_is_unknown_not_warranted(self):
        bad = evidence("better", 80, 400, 120)
        bad["proof_sha256"] = "0" * 64
        result = self.decision(scores=[self.old_score, bad])
        self.assertEqual(result["selected_label"], "control")
        self.assertEqual(result["admission"]["better"]["status"], "UNKNOWN")

    def test_source_pin_change_requires_requalification(self):
        bad = evidence("better", 80, 400, 120)
        bad["public_harness_sha"] = "later-but-not-qualified"
        result = self.decision(scores=[self.old_score, bad])
        self.assertEqual(result["admission"]["better"]["status"], "UNKNOWN")

    def test_keeps_pareto_alternatives_instead_of_forgetting_fast_one(self):
        faster = entry("faster")
        quick = evidence("faster", 120, 300, 110)
        result = self.decision(rows=[self.control, self.better, faster],
                               scores=[self.old_score, self.new_score, quick])
        self.assertEqual(result["selected_label"], "better")
        self.assertEqual(set(result["frontier_labels"]), {"better", "faster"})

    def test_does_not_replace_incumbent_with_lower_objective(self):
        worse = evidence("better", 80, 600, 100)
        # 60 length reduction + 40 heartbeat reduction = 100, so no gain.
        result = self.decision(scores=[self.old_score, worse])
        self.assertEqual(result["selected_label"], "control")
        self.assertEqual(result["objective_gain"], 0.0)

    def test_fails_closed_when_incumbent_has_no_exact_warrant(self):
        with self.assertRaises(ValueError):
            self.decision(scores=[self.new_score])

    def test_mismatch_in_verified_theorem_is_rejected(self):
        bad = evidence("better", 80, 400, 120, statement_ok=False)
        result = self.decision(scores=[self.old_score, bad])
        self.assertEqual(result["admission"]["better"]["status"], "REJECTED")

    def test_packet_reclosure_preserves_fourteen_raw_rows(self):
        lines=[json.dumps({"name": f"Other.{i}", "proof": proof(str(i))}, ensure_ascii=False) for i in range(14)]
        lines.append(json.dumps({"name":NAME,"proof":self.control["proof"]},ensure_ascii=False))
        old_packet="\n".join(lines)+"\n"
        changed, decision = reclose_packet(old_packet,NAME,[self.control,self.better],
                [self.old_score,self.new_score], required_versions=VERSIONS,
                expected_public_sha=PIN, incumbent_label="control")
        self.assertEqual(changed.splitlines()[:14],lines[:14])
        self.assertEqual(json.loads(changed.splitlines()[14])["proof"],self.better["proof"])
        self.assertEqual(decision["selected_label"],"better")
        degraded=evidence("better",80,600,100)
        same, decision2=reclose_packet(old_packet,NAME,[self.control,self.better],
                [self.old_score,degraded], required_versions=VERSIONS,
                expected_public_sha=PIN, incumbent_label="control")
        self.assertEqual(same,old_packet)
        self.assertEqual(decision2["objective_gain"],0.0)

    def test_packet_reclosure_never_admits_stale_proof_certificate(self):
        packet=json.dumps({"name":NAME,"proof":self.control["proof"]})+"\n"
        changed=dict(self.better,proof=self.better["proof"]+"\n  trivial")
        packet2,decision=reclose_packet(packet,NAME,[self.control,changed],
            [self.old_score,self.new_score],required_versions=VERSIONS,
            expected_public_sha=PIN,incumbent_label="control")
        self.assertEqual(packet2,packet)
        self.assertEqual(decision["admission"]["better"]["status"],"UNKNOWN")

    def test_packet_reclosure_rejects_stale_incumbent_proof(self):
        packet=json.dumps({"name":NAME,"proof":"theorem example_theorem : True := by\n  sorry"})+"\n"
        with self.assertRaises(ValueError):
            reclose_packet(packet,NAME,[self.control,self.better],[self.old_score,self.new_score],
                required_versions=VERSIONS,expected_public_sha=PIN,incumbent_label="control")

    def test_packet_reclosure_rejects_unknown_name(self):
        rows=json.dumps({"name":"Other.A", "proof":"by trivial"})+"\n"
        with self.assertRaises(ValueError):
            reclose_packet(rows,NAME,[self.control,self.better],[self.old_score,self.new_score],
                required_versions=VERSIONS, expected_public_sha=PIN,
                incumbent_label="control")


    def test_real_em_evidence_recloses_at_pareto_frontier(self):
        """Real pinned EM objective geometry, not a synthetic proof-length example."""
        from pathlib import Path
        root=Path(__file__).resolve().parents[1]
        bank=root / "experiments" / "em_terminal_normalization_v1.jsonl"
        all_rows=[json.loads(s) for s in bank.read_text().splitlines() if s.strip()]
        labels=("em_retained_567_control","em_terminal_field_simp_only","em_hcross_simp")
        rows=[next(r for r in all_rows if r["label"]==label) for label in labels]
        benchmark="Electromagnetism.ElectromagneticPotential.time_deriv_time_deriv_electricField_of_isExtrema"
        measured={
            "em_retained_567_control":(567,10557,120.75),
            "em_terminal_field_simp_only":(565,10556,120.90),
            "em_hcross_simp":(568,10499,120.89)
        }
        evidence_rows=[]
        for row in rows:
            length,heartbeat,objective=measured[row["label"]]
            evidence_rows.append({
                "name":benchmark,"candidate_label":row["label"],
                "proof_sha256":hashlib.sha256(row["proof"].encode("utf-8")).hexdigest(),
                "public_harness_sha":"7f3a401470d04f70013d293db4253b088ec8a0ae",
                "all_versions":True,"compiled":True,"statement_ok":True,"eligible":True,
                "compat":{"v4.32.0":True},
                "per_version":[{"version":"v4.32.0","tested":True,"ok":True}],
                "length":length,"heartbeats":heartbeat,
                "reference_length":1372,"reference_heartbeats":27841,
                "survival_pct":100,"objective_sum_pct":objective
            })
        result=decide(rows,evidence_rows,expected_name=benchmark,
                      required_versions=["v4.32.0"],
                      expected_public_sha="7f3a401470d04f70013d293db4253b088ec8a0ae",
                      incumbent_label="em_retained_567_control")
        self.assertEqual(result["selected_label"],"em_terminal_field_simp_only")
        self.assertEqual(result["objective_gain"],0.15)
        self.assertEqual(set(result["frontier_labels"]),{"em_terminal_field_simp_only","em_hcross_simp"})
        packet_path=root / "submissions" / "mathgraph_verified_15_warmup_20261009.jsonl"
        packet=packet_path.read_text()
        lines=packet.splitlines()
        idx=next(i for i,line in enumerate(lines) if json.loads(line)["name"]==benchmark)
        current=json.loads(lines[idx])
        self.assertEqual(current["proof"],rows[1]["proof"])
        before=lines[:]
        current["proof"]=rows[0]["proof"]
        before[idx]=json.dumps(current,ensure_ascii=False)
        updated,decision=reclose_packet("\n".join(before)+"\n",benchmark,rows,evidence_rows,
            required_versions=["v4.32.0"],
            expected_public_sha="7f3a401470d04f70013d293db4253b088ec8a0ae",
            incumbent_label="em_retained_567_control")
        after=updated.splitlines()
        self.assertEqual(len(after),15)
        self.assertEqual(after[:idx]+after[idx+1:],before[:idx]+before[idx+1:])
        self.assertEqual(json.loads(after[idx])["proof"],rows[1]["proof"])


if __name__ == "__main__":
    unittest.main()
