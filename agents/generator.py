"""
Generator agent — produces structured educational content.

Takes a grade and topic, calls the LLM, and validates the response
against the ContentArtifact schema. If validation fails, retries
the LLM call once before giving up.
"""

from schemas import ContentArtifact
from llm import call_llm, extract_json
from prompts import build_generator_prompt


class GeneratorAgent:
    """Generates educational content (explanation + MCQs + teacher notes)
    for a given grade and topic.
    """

    MAX_SCHEMA_RETRIES = 1

    def run(self, grade: int, topic: str, feedback=None) -> ContentArtifact:
        """Generate content. Retries once on schema validation failure.

        Args:
            grade: student grade level
            topic: subject topic
            feedback: list of FeedbackItem dicts from a previous review
                      (only used during refinement, usually None for fresh gen)

        Returns:
            ContentArtifact — validated educational content

        Raises:
            ValueError: if the LLM output fails validation after retry
        """
        system_prompt, user_prompt = build_generator_prompt(grade, topic, feedback)

        last_error = None
        for attempt in range(1 + self.MAX_SCHEMA_RETRIES):
            try:
                raw = call_llm(system_prompt, user_prompt)
                data = extract_json(raw)
                return ContentArtifact.model_validate(data)
            except (ValueError, Exception) as e:
                last_error = e
                if attempt < self.MAX_SCHEMA_RETRIES:
                    continue  # retry once
                break

        raise ValueError(
            f"Generator output failed schema validation after "
            f"{1 + self.MAX_SCHEMA_RETRIES} attempt(s): {last_error}"
        )
