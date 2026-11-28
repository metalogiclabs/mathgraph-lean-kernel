# Direct sort-value table experiment

The independently authored prototype replaces the general interning lookup
for complete raw universe-level ids below 4096 with a direct per-Vals table.
Larger ids use the original interner. The table clears with Vals and counts
against its memory budgets. Gruszka's direct identity tables motivated this
replacement; this experiment adds no general front-cache layer.

The first attempt used index() and therefore erased the LOCAL namespace bit.
A retained ProofIrrelUnderBVar regression rejected it before cost measurement.
A targeted local-versus-global level test reproduced the collision. That
failed source and its logs are retained under attempt-01-masked-level.
The correction keys by raw(), sending local ids to the original interner.

The corrected prototype passes 40 library tests and retained integration
regressions, including local/global levels, table bounds and reset controls,
plus 16 raw source-record controls. Two alternating prefix pairs accept all
25,131 declarations. Software instructions fall 0.700% overall; the pairs
save 0.202% and 1.199%. This fails the prospective 1% repeat and aggregate
gate and is not promoted. Full-input, broad portable and Arena effects
remain UNKNOWN.

The rejected attempt repeats a reusable boundary lesson: a shared numeric
index does not imply shared identity across local and imported namespaces.
An acceleration must retain the full identity key as well as cache lifetime.
