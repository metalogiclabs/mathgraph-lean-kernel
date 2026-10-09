#!/usr/bin/env python3
"""Bounded, source-exact observation transport proposal compiler.

Inputs may supply a known local equality, an observer and concrete rewrites.
The tool does not prove the equality, discover a theorem, check Lean, or warrant
a score. It emits source-bound UNKNOWN candidates for the pinned verifier.
No benchmark theorem names, solutions, or version-specific code live here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

FORBIDDEN = re.compile(
    r"\b(?:sorry|sorryAx|admit|axiom|native_decide|run_elab|run_cmd|unsafe)\b"
    r"|#\s*(?:eval|reduce|exit)\b"
)
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_'\u2080-\u2089]*$")


def digest(proof: str) -> str:
    return hashlib.sha256(proof.encode("utf-8")).hexdigest()


def proof_header(proof: str) -> str:
    delim = " := by\n"
    if proof.count(delim) < 1 or FORBIDDEN.search(proof):
        raise ValueError("unsupported proof header or forbidden term")
    return proof[:proof.index(delim) + len(delim)]


def compile_candidates(parent: dict, spec: dict, *, limit: int = 24) -> list[dict]:
    if limit < 1 or limit > 100:
        raise ValueError("candidate budget outside bounded envelope")
    if spec.get("schema") != "mathgraph.lra.observation-transfer-input.v1":
        raise ValueError("unsupported input schema")
    name = parent.get("name")
    original = parent.get("proof")
    if not isinstance(name, str) or not isinstance(original, str) or not original:
        raise ValueError("bad frozen parent")
    if spec.get("name") != name or spec.get("parent_sha256") != digest(original):
        raise ValueError("source name or exact proof hash mismatch")
    header = proof_header(original)
    old = spec.get("exact_site")
    if not isinstance(old, str) or not old.strip() or original.count(old) != 1:
        raise ValueError("no uniquely specified proof site")
    if old in header or original.find(old) < len(header):
        raise ValueError("cannot change declaration or proof boundary")
    # This is only a lexical scoping check, never a proof of the equality.
    equality = spec.get("equality_name")
    if not isinstance(equality, str) or not IDENTIFIER.fullmatch(equality):
        raise ValueError("invalid local witness name")
    before, after = original.split(old)
    if not re.search(r"\b(?:have|let)\s+" + re.escape(equality) + r"\b", before):
        raise ValueError("source equality not introduced before rewrite site")
    goal_prefix = spec.get("goal_prefix")
    if not isinstance(goal_prefix, str) or not old.startswith(goal_prefix):
        raise ValueError("replacement would alter protected goal declaration")
    if not goal_prefix.endswith(":= by\n"):
        raise ValueError("goal prefix is not a Lean proof boundary")
    observers = spec.get("observers")
    rewrites = spec.get("rewrites")
    if not isinstance(observers, list) or not observers or not isinstance(rewrites, list):
        raise ValueError("missing bounded observers or rewrites")

    result = [{
        "name": name,
        "label": "protected_exact_control",
        "proof": original,
        "proof_sha256": digest(original),
        "parent_sha256": digest(original),
        "mechanism": "EXACT_PARENT_CONTROL",
        "status": "PARENT_BYTES_UNMODIFIED__EVIDENCE_EXTERNAL",
    }]
    seen = {digest(original)}
    for observer in observers:
        if not isinstance(observer, dict) or set(observer) != {"id", "term"}:
            raise ValueError("observer must have id and literal Lean term")
        label = observer["id"]
        term = observer["term"]
        if not isinstance(label, str) or not IDENTIFIER.fullmatch(label):
            raise ValueError("invalid observer id")
        if not isinstance(term, str) or not term.strip() or "\n" in term:
            raise ValueError("observer must be a single Lean expression")
        if FORBIDDEN.search(term):
            raise ValueError("forbidden observer")
        for seq in rewrites:
            if not isinstance(seq, dict) or set(seq) != {"id", "tactics"}:
                raise ValueError("rewrite must supply id and tactics")
            rid, tactics = seq["id"], seq["tactics"]
            if not isinstance(rid, str) or not IDENTIFIER.fullmatch(rid):
                raise ValueError("invalid rewrite id")
            if not isinstance(tactics, list) or not all(isinstance(t, str) and t.strip()
                                                        and "\n" not in t for t in tactics):
                raise ValueError("rewrite tactics must be single-line strings")
            if any(FORBIDDEN.search(t) for t in tactics):
                raise ValueError("forbidden proof tactic")
            expression = (
                goal_prefix
                + "    have observed_witness := congrArg " + term + " " + equality + "\n"
                + "".join("    " + t + "\n" for t in tactics)
                + "    exact observed_witness\n"
            )
            candidate = before + expression + after
            if candidate[:len(header)] != header or FORBIDDEN.search(candidate):
                raise ValueError("proposal violated exact declaration boundary")
            # No syntactically identical proposed proofs and no zero-cost aliases.
            source_hash = digest(candidate)
            if source_hash in seen:
                continue
            seen.add(source_hash)
            result.append({
                "name": name,
                "label": "observe_" + label + "_" + rid,
                "proof": candidate,
                "proof_sha256": source_hash,
                "parent_sha256": digest(original),
                "mechanism": "OBSERVATIONAL_CONSEQUENCE_TRANSPORT",
                "status": "CANDIDATE_UNVERIFIED",
                "source_equality": equality,
                "observer_id": label,
                "rewrite_id": rid,
            })
            if len(result) >= limit:
                return result
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-bank", required=True)
    parser.add_argument("--parent-label", required=True)
    parser.add_argument("--spec", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--limit", type=int, default=24)
    args = parser.parse_args()
    parents = [
        json.loads(s) for s in Path(args.parent_bank).read_text(encoding="utf-8").splitlines()
        if s.strip()
    ]
    matches = [p for p in parents if p.get("label") == args.parent_label]
    if len(matches) != 1:
        raise ValueError("parent label must identify exactly one proof")
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    candidates = compile_candidates(matches[0], spec, limit=args.limit)
    Path(args.out).write_text(
        "".join(json.dumps(p, ensure_ascii=False) + "\n" for p in candidates),
        encoding="utf-8",
    )
    manifest = {
        "schema": "mathgraph.lra.observation-proposal-output.v1",
        "status": "UNVERIFIED_CANDIDATE_GENERATION_ONLY",
        "name": matches[0]["name"],
        "source_proof_sha256": digest(matches[0]["proof"]),
        "generated": len(candidates) - 1,
        "protected_exact_source_control": True,
        "candidate_hashes": [c["proof_sha256"] for c in candidates],
        "required_external_authority": "pinned Lean all required versions + exact objective",
        "officially_submitted": False,
    }
    Path(args.manifest).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in manifest.items() if k != "candidate_hashes"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
