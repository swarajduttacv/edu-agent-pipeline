"""
Prompt templates for all four agents.

Each function returns (system_prompt, user_prompt) so the caller
just passes them straight to llm.call_llm().
"""

import json


# ── Generator prompts ────────────────────────────────────────────────

def build_generator_prompt(grade: int, topic: str, feedback=None):
    """Build the system + user prompt for content generation.

    Feedback is a list of FeedbackItem dicts from a failed review,
    only populated during refinement passes.
    """
    if grade <= 3:
        complexity = "very simple words, short sentences, like talking to a young child"
    elif grade <= 6:
        complexity = "clear and simple language appropriate for an upper elementary student"
    elif grade <= 9:
        complexity = "moderately detailed language suitable for a middle school student"
    else:
        complexity = "detailed but accessible language for a high school student"

    schema_example = {
        "explanation": {
            "text": "A clear, kid-friendly explanation of the topic...",
            "grade": grade
        },
        "mcqs": [
            {
                "question": "What is ...?",
                "options": ["Option A", "Option B", "Option C", "Option D"],
                "correct_index": 1
            }
        ],
        "teacher_notes": {
            "learning_objective": "Students will be able to ...",
            "common_misconceptions": [
                "Students often think that ..."
            ]
        }
    }

    system_msg = (
        "You are an expert educational content creator. "
        "You MUST respond with ONLY valid JSON, no markdown, no code fences, no extra text. "
        "Follow the exact schema provided."
    )

    user_msg = f"""Create educational content for a Grade {grade} student on the topic: "{topic}".

Language level: {complexity}

Requirements:
- Write a clear explanation (4-8 sentences) covering the key concepts. Set the "grade" field to {grade}.
- Create exactly 3 multiple-choice questions testing understanding of the explanation.
- Each question must have exactly 4 options (strings).
- The "correct_index" must be the 0-based index (0, 1, 2, or 3) of the correct option.
- Include teacher notes with a learning objective and at least 2 common misconceptions.
- Make everything age-appropriate for grade {grade}.

Your response MUST match this JSON structure exactly:
{json.dumps(schema_example, indent=2)}
"""

    if feedback and len(feedback) > 0:
        feedback_lines = []
        for item in feedback:
            if isinstance(item, dict):
                feedback_lines.append(f"  - [{item.get('field', '?')}] {item.get('issue', '')}")
            else:
                feedback_lines.append(f"  - {item}")
        feedback_str = "\n".join(feedback_lines)
        user_msg += f"""
IMPORTANT — Previous version was rejected by the reviewer. Fix these specific issues:
{feedback_str}

Rewrite the content addressing ALL feedback points above.
"""

    return system_msg, user_msg


# ── Reviewer prompts ─────────────────────────────────────────────────

def build_reviewer_prompt(grade: int, topic: str, content_json: dict):
    """Build the review prompt with scoring rubric."""

    schema_example = {
        "scores": {
            "age_appropriateness": 5,
            "correctness": 5,
            "clarity": 4,
            "coverage": 4
        },
        "pass": True,
        "feedback": []
    }

    fail_example = {
        "scores": {
            "age_appropriateness": 3,
            "correctness": 4,
            "clarity": 2,
            "coverage": 4
        },
        "pass": False,
        "feedback": [
            {"field": "explanation.text", "issue": "Sentence too complex for the grade level"},
            {"field": "mcqs[1].question", "issue": "Question is ambiguous"}
        ]
    }

    system_msg = (
        "You are a strict educational content reviewer. "
        "You MUST respond with ONLY valid JSON, no markdown, no code fences, no extra text. "
        "Follow the exact schema provided."
    )

    user_msg = f"""Review the following educational content created for Grade {grade} on "{topic}".

Content to review:
{json.dumps(content_json, indent=2)}

Score each dimension on a 1-5 scale:
1. AGE_APPROPRIATENESS: Is the language suitable for grade {grade}?
2. CORRECTNESS: Are all facts accurate? Are MCQ answers correct? Is correct_index valid?
3. CLARITY: Is the explanation easy to follow? Are questions unambiguous?
4. COVERAGE: Does the explanation cover the topic adequately? Do MCQs align with the explanation?

For each issue found, provide a feedback item with:
- "field": the dot-path to the problematic field (e.g. "explanation.text", "mcqs[0].question", "teacher_notes.common_misconceptions[0]")
- "issue": a clear description of what's wrong

If all scores are high and no issues found, set "pass" to true with empty feedback.
If any score is below 4 (or coverage below 3), set "pass" to false.

Pass example: {json.dumps(schema_example)}
Fail example: {json.dumps(fail_example)}
"""

    return system_msg, user_msg


# ── Refiner prompts ──────────────────────────────────────────────────

def build_refiner_prompt(grade: int, topic: str, draft_json: dict,
                         feedback_items: list):
    """Build refiner prompt — includes the original draft and specific feedback."""

    schema_example = {
        "explanation": {
            "text": "Improved explanation...",
            "grade": grade
        },
        "mcqs": [
            {
                "question": "Improved question...",
                "options": ["A", "B", "C", "D"],
                "correct_index": 0
            }
        ],
        "teacher_notes": {
            "learning_objective": "...",
            "common_misconceptions": ["..."]
        }
    }

    system_msg = (
        "You are an expert educational content editor. "
        "You MUST respond with ONLY valid JSON, no markdown, no code fences, no extra text. "
        "Your job is to fix specific issues in existing content while keeping what already works."
    )

    feedback_str = "\n".join(
        f"  - [{item.get('field', '?')}] {item.get('issue', '')}"
        for item in feedback_items
    )

    user_msg = f"""Improve the following educational content for Grade {grade} on "{topic}".

Current draft (needs fixes):
{json.dumps(draft_json, indent=2)}

Issues identified by the reviewer:
{feedback_str}

Instructions:
- Fix EVERY issue listed above
- Keep parts that weren't flagged — don't rewrite the whole thing unnecessarily
- Maintain exactly 3 MCQs with exactly 4 options each
- correct_index must be 0-based (0, 1, 2, or 3)
- Include teacher_notes with learning_objective and at least 2 common_misconceptions
- Keep language appropriate for grade {grade}

Output the corrected content matching this JSON structure:
{json.dumps(schema_example, indent=2)}
"""

    return system_msg, user_msg


# ── Tagger prompts ───────────────────────────────────────────────────

def build_tagger_prompt(content_json: dict, grade: int):
    """Build tagger prompt to classify approved content."""

    schema_example = {
        "subject": "Mathematics",
        "topic": "Fractions",
        "grade": grade,
        "difficulty": "Medium",
        "content_type": ["Explanation", "Quiz"],
        "blooms_level": "Understanding"
    }

    system_msg = (
        "You are a content classifier for an educational platform. "
        "You MUST respond with ONLY valid JSON, no markdown, no code fences, no extra text."
    )

    user_msg = f"""Classify the following educational content.

Content:
{json.dumps(content_json, indent=2)}

Rules:
- "subject": the broad academic subject (e.g. "Mathematics", "Science", "English")
- "topic": a concise topic label
- "grade": {grade}
- "difficulty": one of "Easy", "Medium", "Hard" based on content complexity relative to grade
- "content_type": list of content types present (e.g. ["Explanation", "Quiz"])
- "blooms_level": one of "Remembering", "Understanding", "Applying", "Analyzing", "Evaluating", "Creating"

Output this exact JSON structure:
{json.dumps(schema_example, indent=2)}
"""

    return system_msg, user_msg
