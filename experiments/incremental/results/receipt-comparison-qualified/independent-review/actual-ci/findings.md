# Independent review of receipt-comparison CI

Source `5dfe38b01ca7b1c67f70be4ffb2479978049239e`, successful run
`39581949051`, job `119161428100`. Compact artifact `12342450124` is
58,533,476 bytes, SHA256
`7aa231dff8ddda4d1f6cbd073d62ea408ac5e8f491f421f1ceeebfa5a01f4847`.

Independent content/source/arithmetic review passes **15,067 checks and
40 falsifiers**. Exact 197/335/719/251 legacy gates, 246/229 protected gates
with 21 controls and 21 samples per profile, retained parser shadow controls,
20 paired trials across four cases/40 actual arms and four cold replays pass. Eight representative
complete baseline/delta/receipt/native-index/config/output witnesses reconstruct
the exact composites and replay **60,356 declaration decisions**, including
2,692 selected obligations. Historical HMACs were observed authenticated by the
CI harness; this reviewer has no issuer key and does not authenticate them anew.

Complete warm apply improves in all four same-source comparisons. Times below
are milliseconds, medians of five alternating pairs; canonical and shared use
the same actual retained checker.

| Profile/edit | Canonical wall | Shared wall | Saving | Ratio 95% interval |
| --- | ---: | ---: | ---: | --- |
| Original early | 164.907 | 135.640 | 17.75% | [0.803841,0.875852] |
| Expanded early | 419.135 | 401.830 | 4.13% | [0.539903,0.976947] |
| Original unrelated | 130.641 | 103.014 | 21.15% | [0.591587,0.828350] |
| Expanded unrelated | 503.092 | 260.504 | 48.22% | [0.500817,0.964390] |

All win 5/5 and pass the pointwise bootstrap gate. CPU canonical→shared is
163.557→136.012ms and 422.555→399.637ms for early, 125.323→97.898ms and
514.715→280.744ms for unrelated, original then expanded. All four CPU gates pass.
Persistence medians are 64.174→36.470ms, 162.819→29.815ms, 62.585→36.988ms,
268.589→29.326ms in table order; all four persistence gates pass.

Shared apply/direct fresh full Rust medians are 135.640/284.934ms,
401.830/1183.929ms, 103.014/278.595ms and 260.504/1174.352ms in table order.
All eight direct-Rust comparisons, including canonical controls, pass separately.
These compare accepted warm updates with full Rust on the same live sealed
snapshot; they do not include session startup.

Only original early passes setup+one-apply components, by 0.6953%; the other
three are NO_SPEEDUP. Fresh shared baseline setup medians are about 4.059s
original early and 15.213s expanded early. Single cold shared replays cost
3.550906s setup plus 0.116808s apply (original) and 12.724238s plus 0.403724s
(expanded). Cold startup authenticates prior evidence and rebuilds parser/index
state; it does not claim a new full baseline kernel check. Shutdown and
multi-update amortization are unmeasured.

Expanded materialization/hash remains the largest stable named shared phase:
113.459ms early, 113.723ms unrelated. Early checking is 68.773ms, producer
40.329ms, persistence29.815ms, identity9.138ms. Expanded early shared apply varies
283.848–409.879ms; unassigned outer-minus-six-phases overhead varies22.155–145.975ms.
Persistence also has spikes. Their cause is unprofiled, and phase medians cannot
be added to infer total median savings. Complete reconstruction, conservative
reuse, export materialization/hash and declaration-list scanning remain O(N).

The host is AMD EPYC7763. Bootstrap intervals are pointwise finite-host repeats,
not cross-host or simultaneous confidence. Memory is preserved as post-phase
procfs RSS/HWM, HWM cumulative from startup; absent processes and the omitted
cold producer phase stay missing. No total/phase peak-memory saving follows.
This compact review executes no new kernel, rebuilds no omitted executable,
and does not formally prove the retained parser or comparison shortcut.
