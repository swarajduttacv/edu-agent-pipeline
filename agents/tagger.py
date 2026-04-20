"""
Tagger agent — classifies approved content with metadata tags.

Only runs when the pipeline approves content. Adds subject, difficulty,
Bloom's level, and content type labels.
"""

from schemas import ContentArtifact, Tags
from llm import call_llm, extract_json
from prompts import build_tagger_prompt


class TaggerAgent:
    """Classifies approved content. Should only be called on approved artifacts."""

    def run(self, content: ContentArtifact, grade: int) -> Tags:
        """Tag the content with classification metadata.

        Args:
            content: approved ContentArtifact
            grade: target grade level

        Returns:
            Tags — classification metadata (validated)
        """
        content_dict = content.model_dump()
        system_prompt, user_prompt = build_tagger_prompt(content_dict, grade)

        raw = call_llm(system_prompt, user_prompt)
        data = extract_json(raw)

        try:
            return Tags.model_validate(data)
        except Exception as e:
            raise ValueError(f"Tagger output failed schema validation: {e}")
