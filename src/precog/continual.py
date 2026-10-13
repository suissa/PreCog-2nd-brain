from __future__ import annotations

from dataclasses import dataclass

from .outcome_evaluation import OutcomeEvaluationReport


@dataclass(frozen=True, slots=True)
class ModelCandidate:
    id: str
    version: str
    metric: float
    provenance: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    candidate_id: str
    promoted: bool
    reason: str


@dataclass(frozen=True, slots=True)
class OutcomePromotionDecision:
    candidate_id: str
    promoted: bool
    reason: str
    candidate_quality: float
    baseline_quality: float | None
    guardrail_failures: tuple[str, ...] = ()


def outcome_quality(report: OutcomeEvaluationReport) -> float:
    """Return a deterministic [0, 1] composite score from observed outcomes."""
    return (
        report.behavior_accuracy
        + report.successful_outcome_rate
        + (1.0 - report.brier_score)
        + report.evidence_coverage
    ) / 4.0


class ChampionChallenger:
    """Offline promotion/rollback state machine with outcome-based safety gates.

    This class records decisions only. It does not deploy a model or authorize
    runtime actions. Promotion through evaluate_outcomes requires an approved
    candidate report, comparable evaluation evidence, and non-regressing metrics.
    """

    def __init__(self, champion: ModelCandidate | None = None) -> None:
        self.champion = champion
        self.history: list[ModelCandidate] = []
        self.champion_outcome_report: OutcomeEvaluationReport | None = None
        # Kept index-aligned with history so rollback restores model and report.
        self._outcome_history: list[OutcomeEvaluationReport | None] = []

    def evaluate(self, challenger: ModelCandidate, *, min_gain: float = 0.01) -> PromotionDecision:
        """Legacy metric-based evaluation; outcome-gated callers should use evaluate_outcomes."""
        if not challenger.provenance:
            return PromotionDecision(challenger.id, False, "missing provenance")
        if self.champion is None:
            self.champion = challenger
            self.champion_outcome_report = None
            return PromotionDecision(challenger.id, True, "initial champion")
        if challenger.metric >= self.champion.metric + min_gain:
            self.history.append(self.champion)
            self._outcome_history.append(self.champion_outcome_report)
            self.champion = challenger
            self.champion_outcome_report = None
            return PromotionDecision(challenger.id, True, "challenger exceeds champion threshold")
        return PromotionDecision(challenger.id, False, "insufficient measured gain")

    def evaluate_outcomes(
        self,
        challenger: ModelCandidate,
        report: OutcomeEvaluationReport,
        *,
        baseline_report: OutcomeEvaluationReport | None = None,
        min_gain: float = 0.01,
        max_accuracy_drop: float = 0.0,
        max_success_rate_drop: float = 0.0,
        max_brier_increase: float = 0.0,
        max_evidence_coverage_drop: float = 0.0,
    ) -> OutcomePromotionDecision:
        """Evaluate a candidate against observed outcomes without deploying it.

        When a champion already exists, its report must be supplied explicitly or
        previously recorded by this instance. Baseline and candidate must use the
        same Experience cohort to avoid comparing unlike evaluation sets.
        """
        candidate_score = outcome_quality(report)
        if not challenger.provenance:
            return OutcomePromotionDecision(
                challenger.id, False, "missing provenance", candidate_score, None,
                ("missing provenance",),
            )
        if not report.passed:
            return OutcomePromotionDecision(
                challenger.id, False, "candidate evaluation did not pass", candidate_score, None,
                report.reasons or ("candidate evaluation did not pass",),
            )
        if min_gain < 0:
            raise ValueError("min_gain must be non-negative")
        for value, name in (
            (max_accuracy_drop, "max_accuracy_drop"),
            (max_success_rate_drop, "max_success_rate_drop"),
            (max_brier_increase, "max_brier_increase"),
            (max_evidence_coverage_drop, "max_evidence_coverage_drop"),
        ):
            if value < 0:
                raise ValueError(f"{name} must be non-negative")

        if self.champion is None:
            self.champion = challenger
            self.champion_outcome_report = report
            return OutcomePromotionDecision(
                challenger.id, True, "initial champion; outcome gates passed", candidate_score, None
            )

        baseline = baseline_report or self.champion_outcome_report
        if baseline is None:
            return OutcomePromotionDecision(
                challenger.id, False, "missing champion baseline evaluation", candidate_score, None,
                ("missing champion baseline evaluation",),
            )

        if (
            report.sample_count != baseline.sample_count
            or set(report.evaluated_experience_ids) != set(baseline.evaluated_experience_ids)
        ):
            return OutcomePromotionDecision(
                challenger.id, False, "evaluation cohorts differ", candidate_score,
                outcome_quality(baseline), ("evaluation cohorts differ",),
            )

        baseline_score = outcome_quality(baseline)
        failures: list[str] = []
        if report.behavior_accuracy < baseline.behavior_accuracy - max_accuracy_drop:
            failures.append("behavior accuracy regressed beyond allowed tolerance")
        if report.successful_outcome_rate < baseline.successful_outcome_rate - max_success_rate_drop:
            failures.append("successful outcome rate regressed beyond allowed tolerance")
        if report.brier_score > baseline.brier_score + max_brier_increase:
            failures.append("Brier score regressed beyond allowed tolerance")
        if report.evidence_coverage < baseline.evidence_coverage - max_evidence_coverage_drop:
            failures.append("evidence coverage regressed beyond allowed tolerance")
        if failures:
            return OutcomePromotionDecision(
                challenger.id, False, "outcome guardrail regression", candidate_score,
                baseline_score, tuple(failures),
            )
        if candidate_score < baseline_score + min_gain:
            return OutcomePromotionDecision(
                challenger.id, False, "insufficient outcome-quality gain", candidate_score,
                baseline_score, ("insufficient outcome-quality gain",),
            )

        self.history.append(self.champion)
        self._outcome_history.append(self.champion_outcome_report or baseline)
        self.champion = challenger
        self.champion_outcome_report = report
        return OutcomePromotionDecision(
            challenger.id, True, "outcome gates passed and quality gain verified",
            candidate_score, baseline_score,
        )

    def rollback(self) -> ModelCandidate:
        if not self.history:
            raise ValueError("no previous champion available")
        self.champion = self.history.pop()
        self.champion_outcome_report = (
            self._outcome_history.pop() if self._outcome_history else None
        )
        return self.champion
