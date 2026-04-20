"""
LLM client wrapper — the only module that makes network calls.

Extracted from Part 1's agents.py so every agent goes through one
interface, and tests can mock a single function.

Supports a DEMO_MODE flag that bypasses the LLM entirely with
pre-built responses, so the full pipeline can be demonstrated
even when the API quota is exhausted.
"""

import json
import re
import os
import time

# ── Demo mode state ──────────────────────────────────────────────────
# When True, call_llm returns mock data instead of hitting the API.
# Controlled by the UI toggle or environment variable.

_demo_mode = os.getenv("DEMO_MODE", "").lower() in ("1", "true", "yes")
_demo_call_counter = {"generator": 0, "reviewer": 0, "refiner": 0, "tagger": 0}


def set_demo_mode(enabled: bool):
    """Toggle demo mode on or off. Called by the UI."""
    global _demo_mode
    _demo_mode = enabled
    # reset counters when toggling
    for k in _demo_call_counter:
        _demo_call_counter[k] = 0


def is_demo_mode() -> bool:
    return _demo_mode


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

    When demo mode is active, returns pre-built responses instead.
    """
    if _demo_mode:
        return _demo_response(system_prompt)

    client = _get_client()

    # retry once on rate limit with backoff
    for attempt in range(2):
        try:
            response = client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=user_prompt,
                config={
                    "system_instruction": system_prompt,
                    "temperature": 0.4,
                    "max_output_tokens": 2048,
                }
            )
            return response.text
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                if attempt == 0:
                    time.sleep(5)  # brief backoff before retry
                    continue
                # quota exhausted after retry — raise clear error
                raise ValueError(
                    f"API quota exhausted. Consider enabling Demo Mode to "
                    f"test the pipeline without API calls. Error: {e}"
                )
            raise

    return ""


def _demo_response(system_prompt: str) -> str:
    """Return pre-built demo data based on which agent is calling."""
    from demo_data import get_demo_response

    prompt_lower = system_prompt.lower()

    if "classifier" in prompt_lower or "classify" in prompt_lower:
        agent = "tagger"
    elif "editor" in prompt_lower or "fix" in prompt_lower or "improve" in prompt_lower:
        agent = "refiner"
    elif "reviewer" in prompt_lower or "review" in prompt_lower:
        agent = "reviewer"
    else:
        agent = "generator"

    count = _demo_call_counter.get(agent, 0)
    _demo_call_counter[agent] = count + 1

    return get_demo_response(agent, count)


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
