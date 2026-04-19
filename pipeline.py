"""
Pipeline orchestration — ties the generator and reviewer together
into a single deterministic flow.

Flow:
  1. Generator produces content from grade + topic
  2. Reviewer evaluates the content
  3. If reviewer says "fail", we feed the feedback back to the
     generator for ONE refinement attempt
  4. Package everything up for the UI

We cap it at one retry to keep things predictable and avoid
burning through API quota on edge cases.
"""

from schemas import GeneratorInput, PipelineResult
from agents import GeneratorAgent, ReviewerAgent


def run_pipeline(grade: int, topic: str, status_callback=None):
    """Execute the full generate → review → (optional retry) pipeline.
    
    Args:
        grade: student grade level (1-12)
        topic: subject topic string
        status_callback: optional function to call with status updates,
                         used by the UI to show progress messages
    
    Returns:
        PipelineResult with all stages filled in
    """
    generator = GeneratorAgent()
    reviewer = ReviewerAgent()

    # helper to push status updates to the UI (if hooked up)
    def update(msg):
        if status_callback:
            status_callback(msg)

    # ── Step 1: Initial generation ──────────────────────────────
    update("📝 Generator is creating content...")
    first_output = generator.run(grade, topic)
    update("✅ Initial content generated")

    # ── Step 2: Review the first draft ──────────────────────────
    update("🔍 Reviewer is evaluating content...")
    first_review = reviewer.run(grade, topic, first_output)
    update(f"📋 Review complete — status: {first_review.status}")

    refined_output = None
    refined_review = None

    # ── Step 3: If review failed, do one refinement pass ────────
    if first_review.status == "fail":
        update("🔄 Content failed review — refining with feedback...")
        refined_output = generator.run(grade, topic, feedback=first_review.feedback)
        update("✅ Refined content generated")

        update("🔍 Reviewing refined content...")
        refined_review = reviewer.run(grade, topic, refined_output)
        update(f"📋 Second review — status: {refined_review.status}")

    # ── Package results ─────────────────────────────────────────
    result = PipelineResult(
        request={"grade": grade, "topic": topic},
        generated=first_output.model_dump(),
        review=first_review.model_dump(),
        refined=refined_output.model_dump() if refined_output else None,
        refined_review=refined_review.model_dump() if refined_review else None,
    )

    return result
