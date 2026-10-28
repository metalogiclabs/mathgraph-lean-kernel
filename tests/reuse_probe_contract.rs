use sokonanoda::reuse_probe::{MissClass, ReuseProbe};

#[test]
fn repeated_closed_global_expression_is_only_a_candidate_after_cache_reset() {
    let mut probe = ReuseProbe::default();
    assert_eq!(probe.observe_miss(19, 42, true, true), MissClass::First);
    assert_eq!(probe.observe_miss(19, 42, true, true), MissClass::SameGeneration);
    probe.cache_reset();
    assert_eq!(probe.observe_miss(19, 42, true, true), MissClass::AcrossGenerationCandidate);
    let s = probe.stats();
    assert_eq!((s.first, s.same_generation, s.across_generation_candidate), (1, 1, 1));
}

#[test]
fn a_changed_authority_epoch_cannot_inherit_a_candidate() {
    let mut probe = ReuseProbe::default();
    assert_eq!(probe.observe_miss(19, 42, true, true), MissClass::First);
    probe.cache_reset();
    assert_eq!(probe.observe_miss(20, 42, true, true), MissClass::First);
    assert_eq!(probe.stats().across_generation_candidate, 0);
}

#[test]
fn local_open_or_substituted_expressions_never_count_as_reusable() {
    let mut probe = ReuseProbe::default();
    assert_eq!(probe.observe_miss(19, 42, false, true), MissClass::Excluded);
    assert_eq!(probe.observe_miss(19, 42, true, false), MissClass::Excluded);
    probe.cache_reset();
    assert_eq!(probe.observe_miss(19, 42, true, true), MissClass::First);
    assert_eq!(probe.stats().excluded, 2);
}

#[test]
fn bounded_sample_is_deterministic_and_does_not_admit_every_pointer() {
    let sampled: Vec<_> = (1..=8192).filter(|id| ReuseProbe::in_sample(*id)).collect();
    assert!(sampled.len() >= 10 && sampled.len() <= 60, "unexpected sample size: {}", sampled.len());
    for id in sampled {
        assert!(ReuseProbe::in_sample(id));
    }
}

#[test]
fn report_marks_recurrence_as_unqualified_and_not_a_speedup() {
    let mut probe = ReuseProbe::default();
    assert_eq!(probe.observe_miss(19, 42, true, true), MissClass::First);
    probe.cache_reset();
    assert_eq!(probe.observe_miss(19, 42, true, true), MissClass::AcrossGenerationCandidate);
    let report = probe.report();
    assert_eq!(report["qualification"], "CANDIDATE_IDENTITY_ONLY");
    assert_eq!(report["speedup_measured"], false);
    assert_eq!(report["counts"]["across_generation_candidate"], 1);
}
