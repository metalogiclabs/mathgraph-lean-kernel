# LRA V16 reconciliation implementation plan

Goal: admit the completed Binius V12 and Wick V16 results into the existing V15 packet, preserve thirteen other proofs, and obtain a provisional official warm-up evaluation.

Architecture: reuse immutable source-bound Lean results; do not repeat proof search or claim a fresh Lean replay. Keep the existing campaign branch intact until the isolated branch passes. Official competition eligibility still requires reproducible generation and budget/report review.

- [x] Bind completed artifact results to frozen candidate proof hashes and required versions.
- [x] Update only the two admitted proof rows, submission packet and version audit; repair the regression test that still asserts pre-V15 proofs.
- [x] Check exact statements, all fifteen hashes, version authority, no reference fallbacks and existing Python gates.
- [ ] Persist the isolated branch and qualified evidence; request the official practice evaluation under MathGraph, retaining its key privately.
- [ ] Record the actual submission/result and remaining eligibility boundary in ROS.

Constraints: pinned harness 7f3a401470d04f70013d293db4253b088ec8a0ae; every required Lean version positive; objective improves; unchanged proof rows stay byte-identical; no key in git or logs; no claimed final rank or generation-budget compliance from a warm-up score.

Baseline: 54 Python tests, one fails because it hardcodes historical 555-token Wick and 308-token Typing proofs already superseded by V15. Existing V15 artifact admission is green. Repair its authority source, preserving its packet parity assertions.

V16: 2233.13 aggregate objective; 82.9584% projection. 59/59 Python tests and official 15-row upload preflight pass. Packet SHA256 49b9c1cd7e44b94423ec508b4a77c0ea443a0523acacd8f04a644907069feecb. No Lean rebuilt in this reconciliation; archived required-version results reused.
