# Experimental counter: preserve the failed agreement gate

This independently authored diagnostic moves basic-block instruction updates
to raw thread-local storage and merges counts once at thread exit. It uses
the pinned DynamoRIO SDK's public TLS and drreg APIs, preserving application
arithmetic flags. The callback uses the saved exiting-context pointer because
thread-exit events can execute on another thread. This is limited to x86-64
and the retained no-fork programs.

The prototype passes all 15 bounded controls: three exact loops, six exact
live-register/carry controls, and one/two/four-worker coverage under both the
original and experimental clients. All four checker-prefix processes ACCEPT
the same 25,131 declarations on the identical frozen checker binary and input.

Nevertheless, the prefix runner **fails its declared 10-parts-per-million
single-worker agreement tolerance**, returning exit 1. Original count:
10,216,054,452; experimental count: 10,215,868,875. The discrepancy is about
18.2 parts per million. The cause is UNKNOWN. Two additional alternating
single-worker pairs give three observations per client, with all eight total
prefix processes ACCEPTing. The original counter itself spans 16.8 ppm and
the new counter 10.8 ppm; their observed ranges overlap. This warrants
within-client variation, without identifying its cause or proving the two
instruments interchangeable. The original failed gate is retained.

The new client takes less local instrumentation time in these observations,
but this does not establish interchangeability, a kernel speedup, a whole-input
cost or an Arena score. It is excluded from the active full-input batch512
comparison and every submitted checker build.

`identity.json`, calibration/prefix identities, outcome rows and actual
stdout/stderr preserve the observations. The two local Python runners record
the executed workspace layout; rerunning them requires that layout and the
SHA-pinned input, checker and control executables. The C source is reusable
independently of those local paths. Actual binary hashes are retained, while
the small client can be rebuilt from the recorded compiler command and SDK.

`repeat-variation.json` preserves the follow-up separately from the original
negative outcome. Additional applications and an independent complete-input
comparison would be needed before relying on the new client as a replacement.
