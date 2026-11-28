# Register and arithmetic-flag controls

These bounded controls investigate the unresolved SIGILL in the instrumented
native worker study. They do not reproduce that failure or establish its cause.
The successful generic recovery is a separate, complete-input observation.

Each assembly program keeps all 15 non-stack general-purpose registers live
through an ADC/DEC/JNZ loop and checks their final values before returning.
The first family starts with carry zero; `carry-one/` starts with carry one.
The latter adjusts the expected accumulator so losing the carry flag fails
the value check. Loop lengths 1, 17 and 1,000,000 have exact instruction counts
`3 * iterations + 49`: 52, 100 and 3,000,049. All six programs return zero both
natively and under the private software counter, with all six counts exact.

The actual counter is SHA-256
`212a57d6dedc34155467d196e76d30b5d50ceb15010212c4c0f65dd6914194ce`,
built from source SHA-256
`6d00654e55d4b2049ff3f2031383106b9658a0ddaa3a3a05db53261fb35adb34`
against DynamoRIO 11.92.20777. Assembly, stdout/stderr, source hashes,
executable hashes and original outcome rows are retained here. These local
controls are excluded from all checker performance comparisons.

The [register-manager documentation](https://dynamorio.org/struct__drreg__options__t.html)
requires room for saved registers and arithmetic flags; extensions can also
contribute to initialization. Passing these controls does not establish that
every native instruction or register state is handled. The original native
SIGILL remains UNKNOWN. No counting-client change was made on this evidence.
