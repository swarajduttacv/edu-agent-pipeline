"""
Demo data for running the pipeline without LLM access.

When the API quota is exhausted or the key isn't set, the pipeline
can fall back to this pre-built data to demonstrate the full
orchestration flow: schema validation, scoring, refinement, tagging.

All data passes through the same Pydantic validation and orchestration
logic — only the LLM call is swapped out.
"""

import json

# ── Grade-topic combinations with realistic content ──────────────────

DEMO_RESPONSES = {
    "generator": json.dumps({
        "explanation": {
            "text": "A fraction represents a part of a whole. Imagine you have a pizza cut into 4 equal slices. If you eat 1 slice, you have eaten 1/4 of the pizza. The top number is called the numerator — it tells you how many parts you picked. The bottom number is called the denominator — it tells you how many equal parts the whole was divided into. So in 3/4, the numerator is 3 and the denominator is 4, meaning you have 3 out of 4 equal parts.",
            "grade": 5
        },
        "mcqs": [
            {
                "question": "What does the numerator of a fraction tell you?",
                "options": [
                    "How many equal parts the whole is divided into",
                    "How many parts you are talking about",
                    "The total number of items",
                    "The size of each part"
                ],
                "correct_index": 1
            },
            {
                "question": "If a chocolate bar is broken into 8 equal pieces and you eat 3, what fraction did you eat?",
                "options": ["8/3", "3/8", "5/8", "3/5"],
                "correct_index": 1
            },
            {
                "question": "In the fraction 5/6, what is the denominator?",
                "options": ["5", "6", "11", "1"],
                "correct_index": 1
            }
        ],
        "teacher_notes": {
            "learning_objective": "Students will identify and explain numerators and denominators in fractions and relate fractions to equal parts of a whole.",
            "common_misconceptions": [
                "Students often think a larger denominator means a larger fraction (e.g., thinking 1/8 > 1/4).",
                "Students confuse the numerator and denominator positions, placing the total on top."
            ]
        }
    }),

    # first review fails (scores below threshold) to demonstrate refinement
    "review_fail": json.dumps({
        "scores": {
            "age_appropriateness": 3,
            "correctness": 5,
            "clarity": 3,
            "coverage": 4
        },
        "pass": False,
        "feedback": [
            {"field": "explanation.text", "issue": "The word 'numerator' and 'denominator' are introduced without enough context for grade 5 — use simpler build-up."},
            {"field": "mcqs[0].question", "issue": "Question uses the word 'numerator' before the explanation has fully built the concept in kid-friendly terms."}
        ]
    }),

    # refined content (fixed based on feedback)
    "refiner": json.dumps({
        "explanation": {
            "text": "A fraction is a way to show a part of something. Think about cutting a pizza into 4 equal slices. If you eat 1 slice, you ate one-fourth of the pizza, written as 1/4. The number on top (1) is how many slices you took — we call it the numerator. The number on the bottom (4) is how many slices the pizza was cut into — we call it the denominator. So when you see 3/4, it means 3 slices out of 4 equal slices.",
            "grade": 5
        },
        "mcqs": [
            {
                "question": "In the fraction 1/4, what does the number on top tell you?",
                "options": [
                    "How many total slices there are",
                    "How many slices you took",
                    "How big the pizza is",
                    "How many pizzas you have"
                ],
                "correct_index": 1
            },
            {
                "question": "A chocolate bar is broken into 8 equal pieces. You eat 3. What fraction did you eat?",
                "options": ["8/3", "3/8", "5/8", "3/5"],
                "correct_index": 1
            },
            {
                "question": "In the fraction 5/6, what does the bottom number (6) tell you?",
                "options": [
                    "How many parts you picked",
                    "How many equal parts the whole is divided into",
                    "How many wholes you have",
                    "The answer to a division problem"
                ],
                "correct_index": 1
            }
        ],
        "teacher_notes": {
            "learning_objective": "Students will identify numerators and denominators using concrete examples and relate fractions to equal parts of a whole.",
            "common_misconceptions": [
                "Students often think a bigger bottom number means a bigger fraction (e.g., 1/8 seems bigger than 1/4 because 8 is bigger than 4).",
                "Students sometimes put the total number of parts on top instead of the bottom."
            ]
        }
    }),

    # second review passes after refinement
    "review_pass": json.dumps({
        "scores": {
            "age_appropriateness": 5,
            "correctness": 5,
            "clarity": 5,
            "coverage": 4
        },
        "pass": True,
        "feedback": []
    }),

    "tagger": json.dumps({
        "subject": "Mathematics",
        "topic": "Fractions",
        "grade": 5,
        "difficulty": "Medium",
        "content_type": ["Explanation", "Quiz"],
        "blooms_level": "Understanding"
    }),
}


def get_demo_response(agent_type: str, call_count: int = 0) -> str:
    """Return a pre-built LLM response for the given agent type.

    For the reviewer, alternates between fail (first call) and pass
    (second call) to demonstrate the refinement flow.
    """
    if agent_type == "reviewer":
        if call_count == 0:
            return DEMO_RESPONSES["review_fail"]
        return DEMO_RESPONSES["review_pass"]

    return DEMO_RESPONSES.get(agent_type, DEMO_RESPONSES["generator"])
