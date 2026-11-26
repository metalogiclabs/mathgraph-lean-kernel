# Demand-directed recursor prefix experiment

This isolated prototype evaluates a constructor major first and applies its
selected validated recursor rule to expression arguments. It skips evaluation
of syntactically unused prefix binders while preserving their environment
positions. Original rule selection and constructor-field application are
shared with the original evaluator; literal and non-constructor majors retain
the old reduction path. Full type inference still checks every argument.

The library suite passes 40 tests, including a context-sensitive positive
example and rejection of an ill-typed argument erased during evaluation.
All 16 raw source-record controls and 29 original recursor-named tutorial
exports pass. These controls do not establish universal soundness.

Two alternating two-worker prefix pairs accept all 25,131 declarations.
Software instructions fall 0.243% in aggregate: the first pair saves 0.651%,
and the second increases instructions by 0.165%. This fails the prospective
1% repeat gate. The prototype is not promoted. Full-input, full portable
suite and Arena effects remain UNKNOWN.

The earlier auxiliary tutorial invocation used an unsupported CLI flag and
never reached checking. Its decline outputs are retained as an invalid
harness attempt, separately from the corrected 29-case semantic results.

Gruszka/Pestka motivated the demand-directed strategy. The patch is authored
against the existing credited Flash evaluator; competitor code is not copied.
