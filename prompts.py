"""
Prompt templates for the generator and reviewer agents.

The trick here is being very explicit about the JSON schema we expect.
LLMs are surprisingly good at following structure if you spell it out
clearly, but they also love adding extra commentary, so we explicitly
tell them not to.
"""

import json


def build_generator_prompt(grade: int, topic: str, feedback=None):
    """Builds the system + user prompt for content generation.
    
    If feedback is provided (from a failed review), we weave it into
    the prompt so the model knows exactly what to fix.
    """

    # adjust vocabulary expectations based on grade band
    if grade <= 3:
        complexity = "very simple words, short sentences, like talking to a young child"
    elif grade <= 6:
        complexity = "clear and simple language appropriate for an upper elementary student"
    elif grade <= 9:
        complexity = "moderately detailed language suitable for a middle school student"
    else:
        complexity = "detailed but accessible language for a high school student"

    schema_example = {
        "explanation": "A clear, kid-friendly explanation of the topic...",
        "mcqs": [
            {
                "question": "What is ...?",
                "options": ["Option A text", "Option B text", "Option C text", "Option D text"],
                "answer": "A"
            }
        ]
    }

    system_msg = (
        "You are an expert educational content creator. "
        "You MUST respond with ONLY valid JSON, no markdown, no code fences, no extra text. "
        "Follow the exact schema provided."
    )

    user_msg = f"""Create educational content for a Grade {grade} student on the topic: "{topic}".

Language level: {complexity}

Requirements:
- Write a clear explanation (4-8 sentences) covering the key concepts
- Create exactly 3 multiple-choice questions that test understanding of the explanation
- Each question must have exactly 4 options labeled A through D
- The "answer" field should be the letter (A, B, C, or D) of the correct option
- Make sure questions only test concepts mentioned in your explanation
- Keep everything age-appropriate for grade {grade}

Your response must match this JSON structure exactly:
{json.dumps(schema_example, indent=2)}
"""

    # if we're retrying after a failed review, append the feedback
    if feedback and len(feedback) > 0:
        feedback_str = "\n".join(f"  - {fb}" for fb in feedback)
        user_msg += f"""
IMPORTANT — Previous version was rejected by the reviewer. Fix these issues:
{feedback_str}

Rewrite the content addressing ALL feedback points above.
"""

    return system_msg, user_msg


def build_reviewer_prompt(grade: int, topic: str, content_json: dict):
    """Builds the review prompt. We pass the full generated content
    plus the original grade/topic so the reviewer can check
    age-appropriateness properly.
    """

    schema_example = {
        "status": "pass",
        "feedback": []
    }

    fail_example = {
        "status": "fail",
        "feedback": [
            "The explanation uses vocabulary too advanced for the grade level",
            "Question 2 has an incorrect answer key"
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

Evaluate against these criteria:
1. AGE APPROPRIATENESS: Is the language suitable for grade {grade}? No overly complex words or concepts.
2. CORRECTNESS: Are all facts accurate? Are all MCQ answers correct?
3. CLARITY: Is the explanation easy to follow? Are questions unambiguous?
4. COMPLETENESS: Does the explanation cover the topic adequately? Do MCQs align with the explanation?
5. STRUCTURE: Are there exactly 4 options per question? Is each answer A/B/C/D?

Rules:
- If ALL criteria pass, respond with status "pass" and an empty feedback list
- If ANY criterion fails, respond with status "fail" and list specific, actionable feedback
- Be constructive but strict — this content is for real students
- Each feedback item should be a single clear sentence

Respond in this JSON format:
Pass example: {json.dumps(schema_example)}
Fail example: {json.dumps(fail_example)}
"""

    return system_msg, user_msg
