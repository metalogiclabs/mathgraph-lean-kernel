# Next implementation slice

Instrument the conversion engine without changing its default behavior.

Required records at each scheduling choice:

- structural state signature only;
- baseline action taken;
- whether the decision ultimately preserved semantic correctness;
- local/aggregate cost counters;
- optional provenance stored as metadata but never admitted as a policy feature.

Counterfactual replay should be performed in a separate experimental runner so candidate actions cannot perturb the frozen K0 trace. The first real compiler run should use a discovery split and a sealed Arena split fixed before fitting.
