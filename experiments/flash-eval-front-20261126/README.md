# Paged exact-environment evaluation cache

REJECTED for prefix performance promotion. Two alternating two-worker pairs
ACCEPT all 25,131 declarations, but cost 9.143% more software instructions
(ratios 1.089326 and 1.093524). The three exact-loop controls pass. The library
suite passes 41 tests and the existing 16 source-record controls pass with
one worker. Broader portable and complete-input outcomes remain UNKNOWN.

The independently authored prototype indexes recent results by the complete
expression identity (separate local/global namespaces), original environment
identity and cache generation. It retains normal memoization on misses and
all namespace/session invalidation barriers. The tests catch dropped identity
components and stale values after reset; their original red and green logs
are retained. This representation adds work on this input, so no performance
claim or release change follows.

The first local counter invocation failed its exact-loop calibration before
any checker measurement. That attempt used an existing mutable client with
a different executable hash. Its receipts are kept under invalid-counter-attempt.
The successful comparison compiles the retained original counter source into
a separate client, records its hash and rechecks all controls. That failure
is an apparatus failure, not a semantic checker result.

Apply prototype.patch to qualified bc704eeb to reconstruct this isolated
source. compare_instructions.py verifies the exact prefix and immutable
executable identities before and after every observation. The counter is a
software basic-block estimate, not an Arena-native retired-instruction score.
