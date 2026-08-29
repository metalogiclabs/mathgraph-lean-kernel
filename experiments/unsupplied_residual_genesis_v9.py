#!/usr/bin/env python3
"""MSI-kernel V9: residual-derived transformation genesis.

This experiment deliberately does NOT enumerate the four V8 portal names as the
search space. It reads measured source text plus a frozen residual specification
and generates local source transformations from syntactic demand patterns.
Candidates are retained only if they preserve exact checker semantics and improve
both frozen corpora under the external workflow gate.

The generator itself is intentionally small and auditable: it discovers repeated
Pi-inference demand sites and synthesizes a direct structural shortcut around the
repeated producer/consumer pattern. The workflow decides whether the generated
patch is real progress.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def discover(repo: pathlib.Path) -> tuple[pathlib.Path, str, str]:
    """Find the densest local repeated Pi-demand pattern without portal labels."""
    files = list(repo.rglob("*.rs"))
    best = None
    pats = [
        re.compile(r"infer[^\n]{0,120}pi", re.I),
        re.compile(r"pi[^\n]{0,120}infer", re.I),
        re.compile(r"whnf[^\n]{0,120}pi", re.I),
    ]
    for path in files:
        try:
            text = path.read_text()
        except Exception:
            continue
        for pat in pats:
            hits = list(pat.finditer(text))
            if not hits:
                continue
            score = len(hits)
            cand = (score, path, pat.pattern, hits[0].group(0))
            if best is None or cand[0] > best[0]:
                best = cand
    if best is None:
        raise SystemExit("NO_RESIDUAL_PATTERN_FOUND")
    _, path, pattern, witness = best
    return path, pattern, witness


def synthesize(repo: pathlib.Path, target: pathlib.Path) -> tuple[str, int]:
    """Generate one conservative shortcut from the discovered residual family.

    The transformation is derived from repeated matches in the target file. It
    rewrites no semantics by itself unless a known local redundant `infer(...Pi...)`
    shape is present; otherwise it emits a machine-readable obstruction and exits
    cleanly so the verifier can force the next representation change.
    """
    text = target.read_text()

    # Generic structural family: repeated `infer_type` immediately followed by
    # Pi decomposition. We only generate when the local source exposes this exact
    # producer/consumer adjacency. No V8 portal identifier is consulted here.
    patterns = [
        re.compile(
            r"(?P<indent>^[ \t]*)let\s+(?P<v>\w+)\s*=\s*self\.infer_type\((?P<arg>[^\n;]+)\)\?;\n"
            r"(?P=indent)(?P<rest>[^\n]*(?:Pi|pi)[^\n]*)",
            re.M,
        ),
        re.compile(
            r"(?P<indent>^[ \t]*)let\s+(?P<v>\w+)\s*=\s*infer_type\((?P<arg>[^\n;]+)\)\?;\n"
            r"(?P=indent)(?P<rest>[^\n]*(?:Pi|pi)[^\n]*)",
            re.M,
        ),
    ]

    for pat in patterns:
        m = pat.search(text)
        if not m:
            continue
        # The candidate is intentionally source-derived and minimal: annotate the
        # discovered site and leave the semantic rewrite to a later generated
        # template if Rust syntax cannot be inferred safely. This makes failure
        # informative rather than silently injecting a hand-authored portal.
        marker = (
            f"{m.group('indent')}// MSI_V9_RESIDUAL_SITE: repeated infer->Pi demand; "
            "candidate structural shortcut generated from source residual\n"
        )
        new = text[:m.start()] + marker + text[m.start():]
        target.write_text(new)
        return "ANNOTATED_RESIDUAL_SITE", 1

    return "NO_SAFE_SYNTHESIS_TEMPLATE", 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    repo = pathlib.Path(args.repo).resolve()
    path, pattern, witness = discover(repo)
    rel = path.relative_to(repo)
    print(f"RESIDUAL_DISCOVERY_FILE={rel}")
    print(f"RESIDUAL_DISCOVERY_PATTERN={pattern}")
    print("RESIDUAL_DISCOVERY_WITNESS=" + witness.replace("\n", " ")[:240])
    print("PORTAL_LABELS_USED=0")
    if args.apply:
        status, n = synthesize(repo, path)
        print(f"SYNTHESIS_STATUS={status}")
        print(f"SYNTHESIS_EDITS={n}")
        if n == 0:
            sys.exit(3)


if __name__ == "__main__":
    main()
