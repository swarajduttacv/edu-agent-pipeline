"""
LLM client wrapper — the only module that makes network calls.

Extracted from Part 1's agents.py so every agent goes through one
interface, and tests can mock a single function.
"""

import json
import re
import os


def _get_client():
    """Create a Gemini client. Reads GOOGLE_API_KEY from env.
    
    Import is lazy so tests that mock call_llm don't need the SDK.
    """
    from google import genai

    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not api_key:
        raise EnvironmentError(
            "GOOGLE_API_KEY not found. Set it in your .env file or environment."
        )
    return genai.Client(api_key=api_key)


def call_llm(system_prompt: str, user_prompt: str) -> str:
    """Send a prompt to Gemini and return the raw text response.

    This is the single entry point for all LLM calls. Every agent
    goes through here, which makes mocking straightforward in tests.
    """
    client = _get_client()

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=user_prompt,
        config={
            "system_instruction": system_prompt,
            "temperature": 0.4,
            "max_output_tokens": 2048,
        }
    )

    return response.text


def extract_json(raw_text: str) -> dict:
    """Parse LLM output into a dict, stripping markdown fences if present.

    Models sometimes wrap JSON in ```json ... ``` even when told not to.
    This handles that gracefully.
    """
    text = raw_text.strip()

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
