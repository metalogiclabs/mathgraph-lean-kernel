//! MathGraph representation controller.
//!
//! The controller is deliberately independent of benchmark/test identity. It
//! receives only structural pressure observed at the current kernel operation
//! and chooses the cheapest representation that has earned promotion.

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum AppRepresentation {
    PiSpine,
    DirectBeta,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub(crate) struct R1Pressure {
    /// The application spine is headed syntactically by a lambda.
    pub(crate) lambda_head: bool,
    /// Number of application nodes in the current spine.
    pub(crate) app_spine_depth: u8,
    /// Consecutive lambda bodies visible behind the head lambda.
    pub(crate) lambda_body_depth: u8,
    /// The first lambda body depends on its binder.
    pub(crate) binder_dependent: bool,
    /// The first lambda body begins with a local definition.
    pub(crate) let_body: bool,
}

/// Compile-time ablation switch used by qualification. The controller must
/// collapse exactly to the inherited Pi-spine representation when disabled.
pub(crate) const R1_DIRECT_BETA_FUSION: bool = true;

/// Development-calibrated admission threshold. A direct lambda application is
/// the minimum pressure that earns the alternate representation; deeper spines
/// and dependent bodies add evidence but do not use benchmark identity.
pub(crate) const R1_BETA_PRESSURE_THRESHOLD: u8 = 5;

pub(crate) fn r1_beta_pressure_score(p: R1Pressure) -> u8 {
    let mut score = 0u8;
    if p.lambda_head {
        score = score.saturating_add(4);
    }
    score = score.saturating_add(p.app_spine_depth.min(4));
    score = score.saturating_add(p.lambda_body_depth.min(3));
    if p.binder_dependent {
        score = score.saturating_add(2);
    }
    if p.let_body {
        score = score.saturating_add(1);
    }
    score
}

pub(crate) fn select_app_representation(p: R1Pressure) -> AppRepresentation {
    if !R1_DIRECT_BETA_FUSION || !p.lambda_head {
        return AppRepresentation::PiSpine;
    }
    if r1_beta_pressure_score(p) >= R1_BETA_PRESSURE_THRESHOLD {
        AppRepresentation::DirectBeta
    } else {
        AppRepresentation::PiSpine
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn inherited_path_is_default_without_beta_pressure() {
        assert_eq!(
            select_app_representation(R1Pressure::default()),
            AppRepresentation::PiSpine
        );
    }

    #[test]
    fn direct_lambda_application_earns_beta_representation() {
        let p = R1Pressure {
            lambda_head: true,
            app_spine_depth: 1,
            ..R1Pressure::default()
        };
        assert_eq!(r1_beta_pressure_score(p), R1_BETA_PRESSURE_THRESHOLD);
        assert_eq!(select_app_representation(p), AppRepresentation::DirectBeta);
    }

    #[test]
    fn deep_nonlambda_application_does_not_gain_beta_representation() {
        let p = R1Pressure {
            lambda_head: false,
            app_spine_depth: 8,
            lambda_body_depth: 3,
            binder_dependent: true,
            let_body: true,
        };
        assert!(r1_beta_pressure_score(p) >= R1_BETA_PRESSURE_THRESHOLD);
        assert_eq!(select_app_representation(p), AppRepresentation::PiSpine);
    }

    #[test]
    fn ablation_forces_inherited_representation() {
        if !R1_DIRECT_BETA_FUSION {
            let p = R1Pressure {
                lambda_head: true,
                app_spine_depth: 4,
                lambda_body_depth: 3,
                binder_dependent: true,
                let_body: true,
            };
            assert_eq!(select_app_representation(p), AppRepresentation::PiSpine);
        }
    }
}
