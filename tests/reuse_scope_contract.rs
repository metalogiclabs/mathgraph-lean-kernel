#![cfg(feature = "reuse-scope-probe")]

use sokonanoda::reuse_probe::MissClass;
use sokonanoda::reuse_scope::{HeadKind, ScopeClass, ScopeProbe, Support};

#[test]
fn identical_cutoff_without_temporary_environment_is_strict_only_after_a_reset() {
    let mut probe = ScopeProbe::default();
    assert_eq!(
        probe.observe(0, 17, MissClass::First, 100, false, HeadKind::App, || Support::MaxDirectIndex(23)),
        ScopeClass::First
    );
    assert_eq!(
        probe.observe(0, 17, MissClass::SameGeneration, 100, false, HeadKind::App, || panic!("support rescanned")),
        ScopeClass::SameGeneration
    );
    assert_eq!(
        probe.observe(0, 17, MissClass::AcrossGenerationCandidate, 100, false, HeadKind::App, || panic!("support rescanned")),
        ScopeClass::StrictSameCutoff
    );
    assert_eq!(probe.report()["counts"]["strict_same_cutoff"], 1);
}

#[test]
fn prefix_growth_requires_all_direct_references_to_be_visible_in_both_prefixes() {
    let mut probe = ScopeProbe::default();
    probe.observe(0, 23, MissClass::First, 50, false, HeadKind::Const, || Support::MaxDirectIndex(49));
    assert_eq!(
        probe.observe(0, 23, MissClass::AcrossGenerationCandidate, 90, false, HeadKind::Const, || panic!("support rescanned")),
        ScopeClass::AdvancedVisibleDirectSupport
    );

    probe.observe(0, 24, MissClass::First, 50, false, HeadKind::Proj, || Support::MaxDirectIndex(50));
    assert_eq!(
        probe.observe(0, 24, MissClass::AcrossGenerationCandidate, 90, false, HeadKind::Proj, || panic!("support rescanned")),
        ScopeClass::AdvancedBlockedDirectSupport
    );
    probe.observe(0, 25, MissClass::First, 50, false, HeadKind::Let, || Support::UnknownMissingDeclaration);
    assert_eq!(
        probe.observe(0, 25, MissClass::AcrossGenerationCandidate, 90, false, HeadKind::Let, || panic!("support rescanned")),
        ScopeClass::AdvancedUnknownSupport
    );
    probe.observe(0, 26, MissClass::First, 50, false, HeadKind::Pi, || Support::UnknownTraversalCap);
    assert_eq!(
        probe.observe(0, 26, MissClass::AcrossGenerationCandidate, 90, false, HeadKind::Pi, || panic!("support rescanned")),
        ScopeClass::AdvancedUnknownSupport
    );
    assert_eq!(probe.report()["counts"]["advanced_visible_direct_support"], 1);
    assert_eq!(probe.report()["counts"]["advanced_blocked_direct_support"], 1);
    assert_eq!(probe.report()["counts"]["advanced_unknown_support"], 2);
}

#[test]
fn temporary_extension_and_reversed_prefix_never_become_supported_by_identity() {
    let mut probe = ScopeProbe::default();
    probe.observe(0, 1, MissClass::First, 40, true, HeadKind::App, || Support::NoDirectReferences);
    assert_eq!(
        probe.observe(0, 1, MissClass::AcrossGenerationCandidate, 40, false, HeadKind::App, || panic!("support rescanned")),
        ScopeClass::TemporaryContext
    );
    probe.observe(0, 2, MissClass::First, 80, false, HeadKind::App, || Support::NoDirectReferences);
    assert_eq!(
        probe.observe(0, 2, MissClass::AcrossGenerationCandidate, 60, false, HeadKind::App, || panic!("support rescanned")),
        ScopeClass::RegressedPrefix
    );
    assert_eq!(probe.report()["counts"]["temporary_context"], 1);
    assert_eq!(probe.report()["counts"]["regressed_prefix"], 1);
}

#[test]
fn source_epoch_and_diagnostic_cost_do_not_amplify_reuse_warrant() {
    let mut probe = ScopeProbe::default();
    probe.observe(1, 7, MissClass::First, 40, false, HeadKind::App, || Support::NoDirectReferences);
    probe.record_inclusive_elapsed_ns(ScopeClass::First, HeadKind::App, 120);
    probe.observe(2, 7, MissClass::First, 40, false, HeadKind::App, || Support::NoDirectReferences);
    probe.observe(1, 7, MissClass::AcrossGenerationCandidate, 50, false, HeadKind::App, || panic!("support rescanned"));
    probe.record_inclusive_elapsed_ns(ScopeClass::AdvancedVisibleDirectSupport, HeadKind::App, 900);
    let report = probe.report();
    assert_eq!(report["qualification"], "CANDIDATE_CONTEXT_DIAGNOSTIC_ONLY");
    assert_eq!(report["sound_persistent_reuse_implemented"], false);
    assert_eq!(report["speedup_measured"], false);
    assert_eq!(report["counts"]["first"], 2);
    assert_eq!(report["counts"]["advanced_visible_direct_support"], 1);
    assert_eq!(report["recurrent_by_head"]["App"], 1);
    assert_eq!(report["sampled_inclusive_elapsed_ns"]["advanced_visible_direct_support"], 900);
}
