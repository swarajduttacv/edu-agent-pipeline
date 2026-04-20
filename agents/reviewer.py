"""
Reviewer agent — evaluates content quality with numeric scores
and field-referenced feedback.

The LLM produces scores and feedback, but pass/fail is determined
by code-level thresholds so the gating is deterministic.
"""

from schemas import ContentArtifact, ReviewReport
from llm import call_llm, extract_json
from prompts import build_reviewer_prompt


# ── Quality thresholds (documented in README) ────────────────────────
# These are enforced in code, not left to the LLM's judgment.

THRESHOLD_AGE = 4
THRESHOLD_CORRECTNESS = 4
THRESHOLD_CLARITY = 4
THRESHOLD_COVERAGE = 3
THRESHOLD_AVERAGE = 4.0


class ReviewerAgent:
    """Quantitatively evaluates content and decides pass/fail.

    Scores come from the LLM, but the pass/fail decision is applied
    deterministically using the thresholds above.
    """

    def run(self, content: ContentArtifact, grade: int, topic: str) -> ReviewReport:
        """Review content and return a scored report.

        Args:
            content: the ContentArtifact to evaluate
            grade: target grade level (for age-appropriateness check)
            topic: subject topic

        Returns:
            ReviewReport with scores, pass/fail, and field-level feedback
        """
        content_dict = content.model_dump()
        system_prompt, user_prompt = build_reviewer_prompt(grade, topic, content_dict)

        raw = call_llm(system_prompt, user_prompt)
        data = extract_json(raw)

        try:
            report = ReviewReport.model_validate(data)
        except Exception as e:
            raise ValueError(f"Reviewer output failed schema validation: {e}")

        # override the LLM's pass/fail with deterministic thresholds
        scores = report.scores
        avg = (scores.age_appropriateness + scores.correctness +
               scores.clarity + scores.coverage) / 4.0

        passes = (
            scores.age_appropriateness >= THRESHOLD_AGE
            and scores.correctness >= THRESHOLD_CORRECTNESS
            and scores.clarity >= THRESHOLD_CLARITY
            and scores.coverage >= THRESHOLD_COVERAGE
            and avg >= THRESHOLD_AVERAGE
        )

        report.passed = passes

        # if passing, clear any stale feedback
        if passes:
            report.feedback = []

        return report
