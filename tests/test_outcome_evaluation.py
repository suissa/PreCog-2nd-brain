from precog.outcome_evaluation import OutcomeEvaluator, PredictionObservation


def observation(
    i: int,
    *,
    predicted: str = "place-order",
    actual: str = "place-order",
    confidence: float = 0.9,
    outcome: str = "succeeded",
) -> PredictionObservation:
    return PredictionObservation(
        prediction_id=f"prediction-{i}",
        predicted_behavior_id=predicted,
        confidence=confidence,
        actual_behavior_id=actual,
        outcome=outcome,
        evidence_ids=(f"memory-{i}",),
        experience_id=f"experience-{i}",
    )


def test_evaluation_passes_only_when_all_quality_gates_pass() -> None:
    report = OutcomeEvaluator().evaluate(tuple(observation(i) for i in range(25)))

    assert report.passed is True
    assert report.sample_count == 25
    assert report.behavior_accuracy == 1.0
    assert report.successful_outcome_rate == 1.0
    assert report.brier_score == 0.01
    assert report.evidence_coverage == 1.0
    assert len(report.evaluated_experience_ids) == 25


def test_wrong_behavior_and_failed_outcomes_block_promotion_readiness() -> None:
    observations = tuple(
        observation(i, predicted="place-order", actual="cancel-order",
                    confidence=0.95, outcome="failed")
        for i in range(25)
    )
    report = OutcomeEvaluator().evaluate(observations)

    assert report.passed is False
    assert report.behavior_accuracy == 0.0
    assert report.successful_outcome_rate == 0.0
    assert any("behavior accuracy" in reason for reason in report.reasons)
    assert any("successful outcome rate" in reason for reason in report.reasons)


def test_small_sample_never_passes_default_gate() -> None:
    report = OutcomeEvaluator().evaluate(tuple(observation(i) for i in range(3)))

    assert report.passed is False
    assert any("insufficient sample count" in reason for reason in report.reasons)


def test_empty_sample_returns_explicit_non_passing_report() -> None:
    report = OutcomeEvaluator().evaluate(())

    assert report.passed is False
    assert report.sample_count == 0
    assert report.reasons == ("no observations",)


def test_prediction_confidence_must_be_probability() -> None:
    try:
        observation(1, confidence=1.2)
    except ValueError as error:
        assert "between 0 and 1" in str(error)
    else:
        raise AssertionError("invalid confidence was accepted")
