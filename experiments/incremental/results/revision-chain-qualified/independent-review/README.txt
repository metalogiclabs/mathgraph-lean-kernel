Independent revision lifecycle artifact reader (standard library only)

Qualified CI review:
  python3 reviewer.py --artifact COMPACT.zip --repo CHECKOUT \
    --source d1b22447d23a928ae536cbe838a47fc9682a4b39 --output ci-review.json

Local development fixture, explicitly UNQUALIFIED:
  python3 reviewer.py --smoke \
    --artifact /workspace/kernel-audit/revision-lifecycle/harness/smoke-continuous-final \
    --repo /workspace/mathgraph-lean-kernel-lifecycle \
    --source d1b22447d23a928ae536cbe838a47fc9682a4b39 --output smoke-review.json

The ZIP is streamed; there is no extraction. Members are mapped from historical
CI paths to ZIP-root-relative names. Before/after source pins are compared with
git show of the explicitly supplied commit. Full review requires both 5x40
profiles, alternating uninterrupted 40/41 candidate/direct histories, 40-step
cold replay, complete actual-input coverage, both exact 32-control matrices and
their complete rejected inputs. The local smoke's reported older dirty HEAD is
retained in the output; only its exact code-byte match to the supplied commit is
verified. Missing local CI/control scope is explicitly reported UNQUALIFIED.
Lifecycle summary JSON and the manifest descriptors for exactly the four
frozen chain-test/control report families allow up to 512 MiB. Decoded control
summaries share that scoped bound. Generic logs, indexes, result witnesses and
continuous summaries retain 64 MiB limits; complete exports are streamed.

Outputs:
  --output JSON: independent findings, source/reader hashes and bounded scopes.
  inputs.json beside --output: unique accepted/rejected complete inputs, with
    sha256, bytes, expected_returncode, member, encoding, profile, roles,
    observations and compressed member SHA/size. Accepted observations also
    include selected indices and result/evidence references for optional fresh
    full-parser selected checking. Failed review clears this manifest to [].

Trust boundary:
  This reader imports none of engine, producer_delta, revision_chain, or any
  project benchmark. It independently recomputes SCC roots, declaration
  schedules, the prefix/dependency reuse rule, every decision witness/evidence
  origin, and all arithmetic/bootstrap statistics. Declaration own and complex
  fingerprints retain the explicitly frozen full-native/Python witness bridge.
  Historical HMAC validity is NOT reauthenticated without the private CI key;
  only exact object addresses, domains and source/policy/predecessor linkage are
  independently checked. Prior CI publisher completion is observed, not used
  as a substitute for these lifecycle checks. No fresh kernel is run here.
  The caller should independently run pinned full Rust/normal C++/paranoid C++
  on the enumerated exact bytes, expecting the stated 0 or 1 exit code.

Tests:
  python3 -m unittest discover -v
  python3 run_falsifiers.py --artifact LOCAL_SMOKE --repo CHECKOUT \
    --source EXACT_SHA --output falsifiers.json

Falsifiers preserve fake empty success, missing input objects, changed gzip
identity, predecessor substitution, omitted complete-input coverage, duplicate
JSON/ZIP names, traversal/symlinks, contradictory descriptor caching and local
artifact mutation. Separate helper RED/GREEN logs and actual unqualified SCC,
topology, zero-selected and economics smoke observations are retained here.
