from precog.continual import ChampionChallenger, ModelCandidate
from precog.outcome_evaluation import OutcomeEvaluationReport


def report(
    *,
    accuracy: float = 0.9,
    success: float = 0.9,
    brier: float = 0.09,
    coverage: float = 1.0,
    passed: bool = True,
    experience_ids: tuple[str, ...] = ("exp-1", "exp-2"),
) -> OutcomeEvaluationReport:
    return OutcomeEvaluationReport(
        sample_count=len(experience_ids),
        behavior_accuracy=accuracy,
        successful_outcome_rate=success,
        mean_confidence=0.9,
        brier_score=brier,
        evidence_coverage=coverage,
        evaluated_experience_ids=experience_ids,
        passed=passed,
        reasons=() if passed else ("evaluation threshold failed",),
    )


def candidate(name: str, metric: float = 0.0) -> ModelCandidate:
    return ModelCandidate(name, "v1", metric, ("commit:abc123", "dataset:golden-set"))


def test_initial_champion_requires_passed_outcome_report() -> None:
    manager = ChampionChallenger()
    blocked = manager.evaluate_outcomes(candidate("blocked"), report(passed=False))
    assert blocked.promoted is False
    assert manager.champion is None

    accepted = manager.evaluate_outcomes(candidate("first"), report())
    assert accepted.promoted is True
    assert manager.champion == candidate("first")
    assert manager.champion_outcome_report == report()


def test_promotion_compares_same_cohort_and_enforces_non_regression() -> None:
    manager = ChampionChallenger()
    baseline = report(accuracy=0.8, success=0.8, brier=0.16)
    assert manager.evaluate_outcomes(candidate("champion"), baseline).promoted

    improved = report(accuracy=0.9, success=0.9, brier=0.09)
    decision = manager.evaluate_outcomes(candidate("challenger"), improved)
    assert decision.promoted is True
    assert manager.champion == candidate("challenger")
    assert manager.champion_outcome_report == improved


def test_regression_blocks_promotion_even_if_other_metrics_improve() -> None:
    manager = ChampionChallenger()
    baseline = report(accuracy=0.9, success=0.9, brier=0.09)
    manager.evaluate_outcomes(candidate("champion"), baseline)
    challenger = report(accuracy=0.7, success=1.0, brier=0.0)

    decision = manager.evaluate_outcomes(candidate("regression"), challenger)
    assert decision.promoted is False
    assert decision.reason == "outcome guardrail regression"
    assert any("behavior accuracy regressed" in item for item in decision.guardrail_failures)
    assert manager.champion == candidate("champion")


def test_incompatible_evaluation_cohort_fails_closed() -> None:
    manager = ChampionChallenger()
    baseline = report()
    manager.evaluate_outcomes(candidate("champion"), baseline)
    other_cohort = report(experience_ids=("exp-3", "exp-4"))

    decision = manager.evaluate_outcomes(candidate("other-cohort"), other_cohort)
    assert decision.promoted is False
    assert decision.reason == "evaluation cohorts differ"


def test_rollback_restores_champion_and_its_outcome_report() -> None:
    manager = ChampionChallenger()
    baseline = report(accuracy=0.8, success=0.8, brier=0.16)
    improved = report(accuracy=0.9, success=0.9, brier=0.09)
    manager.evaluate_outcomes(candidate("champion"), baseline)
    assert manager.evaluate_outcomes(candidate("challenger"), improved).promoted

    restored = manager.rollback()
    assert restored == candidate("champion")
    assert manager.champion_outcome_report == baseline


def test_existing_champion_without_baseline_report_fails_closed() -> None:
    manager = ChampionChallenger(champion=candidate("legacy-champion"))
    decision = manager.evaluate_outcomes(candidate("challenger"), report())
    assert decision.promoted is False
    assert decision.reason == "missing champion baseline evaluation"
