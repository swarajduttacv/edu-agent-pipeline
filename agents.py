"""
Agent implementations for content generation and review.

Each agent wraps a single LLM call, handles prompt building, 
parses the response into a validated Pydantic model, and raises
clear errors if the LLM gives us garbage.

Uses the google-genai SDK (the current/supported one, not the
deprecated google-generativeai package).
"""

import json
import re
import os
from google import genai
from schemas import GeneratorOutput, ReviewerOutput
from prompts import build_generator_prompt, build_reviewer_prompt


# ── LLM Client Setup ───────────────────────────────────────────────

def _get_client():
    """Create a Gemini client. Reads GOOGLE_API_KEY from env."""
    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not api_key:
        raise EnvironmentError(
            "GOOGLE_API_KEY not found. Set it in your .env file or environment."
        )
    return genai.Client(api_key=api_key)


def _call_gemini(system_prompt: str, user_prompt: str) -> str:
    """Send a prompt to Gemini and return the raw text response.
    
    Using gemini-2.0-flash — it's fast, free-tier friendly, and
    handles JSON output well enough for our needs.
    """
    client = _get_client()

    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=user_prompt,
        config={
            "system_instruction": system_prompt,
            "temperature": 0.4,       # lower temp = more consistent structure
            "max_output_tokens": 2048,
        }
    )

    return response.text


def _extract_json_from_response(raw_text: str) -> dict:
    """Sometimes models wrap JSON in markdown code fences even when
    we tell them not to. This strips that away and parses it.
    """
    text = raw_text.strip()

    # remove ```json ... ``` wrappers if present
    fence_pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
    match = re.search(fence_pattern, text, re.DOTALL)
    if match:
        text = match.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"LLM returned invalid JSON. Parse error: {e}\nRaw output:\n{text[:500]}"
        )


# ── Generator Agent ─────────────────────────────────────────────────

class GeneratorAgent:
    """Generates educational content (explanation + MCQs) for a given
    grade and topic. Optionally accepts reviewer feedback to improve
    a previous attempt.
    """

    def run(self, grade: int, topic: str, feedback=None) -> GeneratorOutput:
        system_prompt, user_prompt = build_generator_prompt(grade, topic, feedback)
        raw = _call_gemini(system_prompt, user_prompt)
        data = _extract_json_from_response(raw)

        # validate against our schema — this catches missing fields,
        # wrong types, wrong number of options, etc.
        try:
            return GeneratorOutput.model_validate(data)
        except Exception as e:
            raise ValueError(f"Generator output failed schema validation: {e}")


# ── Reviewer Agent ───────────────────────────────────────────────────

class ReviewerAgent:
    """Reviews generated content against quality criteria:
    age appropriateness, factual correctness, clarity, and structure.
    
    Returns a pass/fail verdict with actionable feedback when failing.
    """

    def run(self, grade: int, topic: str, content: GeneratorOutput) -> ReviewerOutput:
        content_dict = content.model_dump()
        system_prompt, user_prompt = build_reviewer_prompt(grade, topic, content_dict)
        raw = _call_gemini(system_prompt, user_prompt)
        data = _extract_json_from_response(raw)

        try:
            result = ReviewerOutput.model_validate(data)
        except Exception as e:
            raise ValueError(f"Reviewer output failed schema validation: {e}")

        # sanity check: if pass, feedback should be empty
        if result.status == "pass":
            result.feedback = []

        return result
