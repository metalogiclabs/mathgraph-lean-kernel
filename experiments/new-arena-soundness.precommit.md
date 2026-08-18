# New Arena soundness regression precommit

Exact public V1: `1e209dad266d59b4d43cdea189876bc6ea551339`.

Arena moved from 62 to 66 adversarial reject cases after PRs #140 and #141. The public V1 now reports 65/66.

First experiment: reproduce exactly these four newly added cases against exact V1:

- extra-rec
- rec-missing-ih
- proj-of-stuck-prop
- proj-of-subst-prop

No repair is admitted until the unique wrong-accept is identified. The repair must reject that case, preserve the other three outcomes, pass the broader Arena semantic gate, and show no material performance regression on the score-driving corpus.
