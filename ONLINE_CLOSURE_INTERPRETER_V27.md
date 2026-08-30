# V27 — online closure interpreter genesis

## Question
Can the V26 closure-extension result survive after removing the pre-materialized `z00..z11` outcome table and the learner-side `source_for(program)` lookup?

## Frozen substrate
The learner sees only anonymous primitive event fields: `root`, `a0`, `a1`, `depth`, plus generic Boolean facts. Candidate interaction programs are generated compositionally from the alphabet `u0`, `u1`, `e0`; the interpreter starts at `root`, `u0/u1` move to anonymous child handles, and `e0` emits the current handle's code. No table mapping complete programs to outcomes is supplied.

## Gates
1. Depth-0/1 closure is insufficient.
2. A generated depth-2 program produces a strict safe-frontier gain.
3. Exactly one minimum-cost behavioural generator class attains the optimum.
4. The descendant guard is reachable only through that installed generator class.
5. Exact generator-class ablation restores a lower frontier.
6. The compiled descendant is byte-identical to baseline on Std and Cedar discovery prefixes.
7. Broadening to TRUE fails.
8. The compiled descendant remains byte-identical on untouched rows 400001..600000 of Std and Cedar.

A pass is `ONLINE_CLOSURE_INTERPRETER_V27=BOUNDED_POSITIVE`. It is not a claim of unrestricted experiment invention; the anonymous primitive interpreter and bounded program depth remain supplied.
