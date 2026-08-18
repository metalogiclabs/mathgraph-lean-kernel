# Iota cost decomposition separator

## Frozen baseline
`1e209dad266d59b4d43cdea189876bc6ea551339`

## Residual
Compiled structural-plan caching was neutral/worse despite ~1,674x behavioral quotient compression. The expensive work is therefore below structural rule selection.

## Question
On `perf/grind-ring-5`, where does successful fresh recursor work occur?

Separate four regions:

1. `rule_eval`: cache hit/miss and `eval_inst` of the selected recursor rule.
2. `major_decode`: `major_to_ctor`/K/struct-eta plus constructor unwrap and argument extraction.
3. `rule_apply`: the three `apply_many` phases after a rule value is available.
4. `downstream`: successful fire returns whose result is subsequently reduced/forced by the enclosing `force_all` loop.

Also record closure/environment pressure during `rule_apply`: lambda applications, environment extensions, and closure bodies whose captured environment length exceeds the body's required loose-bvar count.

## Decision rule
This is diagnostic only. On grind-ring-5 classify the largest measured dynamic work/counter concentration:

- `RULE_EVAL_DOMINANT` if rule-cache misses/evaluations remain substantial.
- `CLOSURE_CAPTURE_DOMINANT` if lambda application creates large excess captured environments at high frequency.
- `ARGUMENT_APPLICATION_DOMINANT` if application/env-extension volume dominates without excess capture.
- `DOWNSTREAM_FORCE_DOMINANT` if successful fires commonly trigger further reductions after construction.
- otherwise `NO_SINGLE_IOTA_SUBLAYER__PROFILE_INSTRUCTIONS_BY_FUNCTION`.

No optimization is promoted from this census alone. The next intervention must target only the winning residual class and preserve exact checker output.