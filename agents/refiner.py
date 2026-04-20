"""
Refiner agent — improves content using the reviewer's field-level feedback.

Uses the same schema validation + internal retry as the generator.
The orchestrator is responsible for capping refinement attempts at 2.
"""

from schemas import ContentArtifact, FeedbackItem
from llm import call_llm, extract_json
from prompts import build_refiner_prompt
from typing import List


class RefinerAgent:
    """Refines content based on reviewer feedback."""

    MAX_SCHEMA_RETRIES = 1

    def run(self, draft: ContentArtifact, feedback: List[FeedbackItem],
            grade: int, topic: str) -> ContentArtifact:
        """Refine the draft using specific feedback items.

        Args:
            draft: the current ContentArtifact that failed review
            feedback: list of FeedbackItem objects from the reviewer
            grade: target grade level
            topic: subject topic

        Returns:
            ContentArtifact — the improved version (validated)

        Raises:
            ValueError: if the refined output fails validation after retry
        """
        draft_dict = draft.model_dump()
        feedback_dicts = [item.model_dump() for item in feedback]

        system_prompt, user_prompt = build_refiner_prompt(
            grade, topic, draft_dict, feedback_dicts
        )

        last_error = None
        for attempt in range(1 + self.MAX_SCHEMA_RETRIES):
            try:
                raw = call_llm(system_prompt, user_prompt)
                data = extract_json(raw)
                return ContentArtifact.model_validate(data)
            except (ValueError, Exception) as e:
                last_error = e
                if attempt < self.MAX_SCHEMA_RETRIES:
                    continue
                break

        raise ValueError(
            f"Refiner output failed schema validation after "
            f"{1 + self.MAX_SCHEMA_RETRIES} attempt(s): {last_error}"
        )
