"""
Test 3: Fail → refine → fail → reject orchestration.

Mocks the reviewer to always return failing scores, so the pipeline
exhausts its 2 refinement attempts and ends with rejected status.

Verifies:
- Exactly 2 refinement attempts are logged
- Final status is "rejected"
- Tags are None
- All attempts have review records
"""

import sys
import os
import json
import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from schemas import GenerateRequest, RunArtifact
from orchestrator import run_pipeline


VALID_CONTENT = json.dumps({
    "explanation": {
        "text": "Fractions represent parts of a whole. When you divide something into equal pieces, each piece is a fraction of the whole. The top number tells how many pieces you have. The bottom number tells how many equal pieces make up the whole.",
        "grade": 5
    },
    "mcqs": [
        {
            "question": "What does the top number of a fraction show?",
            "options": ["Total pieces", "Pieces you have", "The whole", "Nothing"],
            "correct_index": 1
        },
        {
            "question": "What is 1/4 of a pizza?",
            "options": ["The whole pizza", "Half the pizza", "One of four equal slices", "Four pizzas"],
            "correct_index": 2
        },
        {
            "question": "Which fraction is larger: 1/2 or 1/4?",
            "options": ["1/4", "1/2", "They are equal", "Cannot tell"],
            "correct_index": 1
        }
    ],
    "teacher_notes": {
        "learning_objective": "Students will understand basic fraction concepts",
        "common_misconceptions": [
            "Larger denominators mean larger fractions",
            "Fractions are always less than one"
        ]
    }
})

FAILING_REVIEW = json.dumps({
    "scores": {
        "age_appropriateness": 3,
        "correctness": 3,
        "clarity": 3,
        "coverage": 3
    },
    "pass": False,
    "feedback": [
        {"field": "explanation.text", "issue": "Language too complex for grade level"},
        {"field": "mcqs[2].options", "issue": "Options are confusing"}
    ]
})


def test_fail_refine_fail_rejects():
    """Content fails every review — pipeline rejects after 2 refinement attempts."""

    request = GenerateRequest(
        user_id="test_user",
        grade=5,
        topic="Fractions"
    )

    # generator and refiner always return valid content,
    # reviewer always fails it
    def mock_call_llm(system_prompt, user_prompt):
        if "reviewer" in system_prompt.lower() or "review" in system_prompt.lower():
            return FAILING_REVIEW
        return VALID_CONTENT

    with patch("agents.generator.call_llm", side_effect=mock_call_llm), \
         patch("agents.reviewer.call_llm", side_effect=mock_call_llm), \
         patch("agents.refiner.call_llm", side_effect=mock_call_llm):
        artifact = run_pipeline(request)

    assert isinstance(artifact, RunArtifact)
    assert artifact.final.status == "rejected"

    # should have 3 attempts: initial + 2 refinements
    assert len(artifact.attempts) == 3

    # first attempt: draft + failing review
    assert artifact.attempts[0].draft is not None
    assert artifact.attempts[0].review is not None
    assert artifact.attempts[0].review.passed is False

    # second attempt: refinement + failing review
    assert artifact.attempts[1].refined is not None
    assert artifact.attempts[1].review is not None
    assert artifact.attempts[1].review.passed is False

    # third attempt: refinement + failing review
    assert artifact.attempts[2].refined is not None
    assert artifact.attempts[2].review is not None
    assert artifact.attempts[2].review.passed is False

    # no tags on rejected content
    assert artifact.final.tags is None

    # no approved content
    assert artifact.final.content is None

    # timestamps present
    assert artifact.timestamps.started_at is not None
    assert artifact.timestamps.finished_at is not None
