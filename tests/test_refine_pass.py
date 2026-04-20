"""
Test 2: Fail → refine → pass orchestration.

Mocks the LLM so that:
- Generator produces valid content
- Reviewer FAILS the first draft (low scores)
- Refiner produces improved content
- Reviewer PASSES the refined version (high scores)
- Tagger produces valid tags

Verifies the full approve-after-refinement flow.
"""

import sys
import os
import json
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from schemas import GenerateRequest, RunArtifact
from orchestrator import run_pipeline


# ── Mock LLM responses ──────────────────────────────────────────────

VALID_DRAFT = json.dumps({
    "explanation": {
        "text": "Fractions represent parts of a whole. When you cut a pizza into 4 equal slices and eat 1, you have eaten 1/4 of the pizza. The top number is the numerator and shows how many parts you have. The bottom number is the denominator and shows how many equal parts the whole is divided into.",
        "grade": 5
    },
    "mcqs": [
        {
            "question": "What does the numerator in a fraction represent?",
            "options": ["The total parts", "The parts you have", "The whole number", "The decimal"],
            "correct_index": 1
        },
        {
            "question": "If a pie is cut into 8 slices and you eat 3, what fraction did you eat?",
            "options": ["8/3", "3/8", "3/5", "5/8"],
            "correct_index": 1
        },
        {
            "question": "What is the denominator in 2/5?",
            "options": ["2", "5", "7", "10"],
            "correct_index": 1
        }
    ],
    "teacher_notes": {
        "learning_objective": "Students will identify numerators and denominators in fractions",
        "common_misconceptions": [
            "Students confuse numerator and denominator positions",
            "Students think fractions are always less than 1"
        ]
    }
})

FAILING_REVIEW = json.dumps({
    "scores": {
        "age_appropriateness": 3,
        "correctness": 4,
        "clarity": 3,
        "coverage": 4
    },
    "pass": False,
    "feedback": [
        {"field": "explanation.text", "issue": "Uses vocabulary too advanced for grade 5"},
        {"field": "mcqs[0].question", "issue": "Question could be clearer"}
    ]
})

PASSING_REVIEW = json.dumps({
    "scores": {
        "age_appropriateness": 5,
        "correctness": 5,
        "clarity": 5,
        "coverage": 4
    },
    "pass": True,
    "feedback": []
})

VALID_TAGS = json.dumps({
    "subject": "Mathematics",
    "topic": "Fractions",
    "grade": 5,
    "difficulty": "Medium",
    "content_type": ["Explanation", "Quiz"],
    "blooms_level": "Understanding"
})


def test_fail_refine_pass():
    """Content fails first review, gets refined, passes second review."""

    request = GenerateRequest(
        user_id="test_user",
        grade=5,
        topic="Fractions as parts of a whole"
    )

    # track which call we're on to return different responses
    call_sequence = [
        VALID_DRAFT,     # generator
        FAILING_REVIEW,  # first review (fails)
        VALID_DRAFT,     # refiner output (same structure, different call)
        PASSING_REVIEW,  # second review (passes)
        VALID_TAGS,      # tagger
    ]
    call_index = {"i": 0}

    def mock_call_llm(system_prompt, user_prompt):
        idx = call_index["i"]
        call_index["i"] += 1
        if idx < len(call_sequence):
            return call_sequence[idx]
        return VALID_DRAFT  # fallback

    with patch("agents.generator.call_llm", side_effect=mock_call_llm), \
         patch("agents.reviewer.call_llm", side_effect=mock_call_llm), \
         patch("agents.refiner.call_llm", side_effect=mock_call_llm), \
         patch("agents.tagger.call_llm", side_effect=mock_call_llm):
        artifact = run_pipeline(request)

    assert isinstance(artifact, RunArtifact)
    assert artifact.final.status == "approved"

    # should have 2 attempts: initial + 1 refinement
    assert len(artifact.attempts) == 2

    # first attempt should have a draft and a failing review
    assert artifact.attempts[0].draft is not None
    assert artifact.attempts[0].review is not None
    assert artifact.attempts[0].review.passed is False

    # second attempt should have refined content and passing review
    assert artifact.attempts[1].refined is not None
    assert artifact.attempts[1].review is not None
    assert artifact.attempts[1].review.passed is True

    # approved content should have tags
    assert artifact.final.content is not None
    assert artifact.final.tags is not None
    assert artifact.final.tags.subject == "Mathematics"
