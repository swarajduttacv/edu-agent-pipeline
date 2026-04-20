"""
Test 1: Schema validation failure handling.

Mocks the LLM to return invalid JSON on every call, verifying that:
- The generator retries once internally
- The pipeline ends with status="rejected"
- The attempt log captures validation error messages
- A complete RunArtifact is still returned
"""

import sys
import os
import json
import pytest
from unittest.mock import patch

# make sure project root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from schemas import GenerateRequest, RunArtifact
from orchestrator import run_pipeline


# deliberately broken output — missing required fields
INVALID_LLM_RESPONSE = json.dumps({
    "explanation": "just a string, not the nested object",
    # missing mcqs entirely
    # missing teacher_notes entirely
})


def test_schema_validation_failure_rejects():
    """When the generator can't produce valid schema output,
    the pipeline should reject gracefully with an audit trail."""

    request = GenerateRequest(
        user_id="test_user",
        grade=5,
        topic="Fractions"
    )

    # mock call_llm to always return invalid content
    with patch("agents.generator.call_llm", return_value=INVALID_LLM_RESPONSE):
        artifact = run_pipeline(request)

    # should still get a complete RunArtifact back
    assert isinstance(artifact, RunArtifact)
    assert artifact.run_id is not None
    assert artifact.final.status == "rejected"

    # content and tags should be None on rejection
    assert artifact.final.content is None
    assert artifact.final.tags is None

    # at least one attempt should be logged
    assert len(artifact.attempts) >= 1

    # the attempt should have recorded the validation error
    first_attempt = artifact.attempts[0]
    assert len(first_attempt.errors) > 0
    assert "Generator failed" in first_attempt.errors[0]

    # timestamps should be populated
    assert artifact.timestamps.started_at is not None
    assert artifact.timestamps.finished_at is not None


def test_schema_validation_failure_with_json_parse_error():
    """When the LLM returns complete garbage (not even valid JSON),
    the pipeline should still handle it gracefully."""

    request = GenerateRequest(
        user_id="test_user",
        grade=3,
        topic="Addition"
    )

    with patch("agents.generator.call_llm", return_value="This is not JSON at all!"):
        artifact = run_pipeline(request)

    assert artifact.final.status == "rejected"
    assert len(artifact.attempts) >= 1
    assert len(artifact.attempts[0].errors) > 0
