"""
Pipeline orchestrator — deterministic, bounded, auditable.

Ties all four agents into a fixed flow that always produces a
complete RunArtifact, whether the content is approved or rejected.

Flow:
  1. Generator produces draft (1 internal schema retry)
  2. Reviewer scores the draft
  3. If pass → Tagger → approved
  4. If fail → Refiner (max 2 attempts) → Review each time
  5. If still failing after 2 refinements → rejected
  6. Always persist to storage, always return RunArtifact
"""

import uuid
from datetime import datetime, timezone

from schemas import (
    GenerateRequest, ContentArtifact, RunArtifact,
    AttemptLog, FinalDecision, Timestamps
)
from agents.generator import GeneratorAgent
from agents.reviewer import ReviewerAgent
from agents.refiner import RefinerAgent
from agents.tagger import TaggerAgent
from storage import save_artifact


MAX_REFINEMENT_ATTEMPTS = 2


def run_pipeline(request: GenerateRequest, status_callback=None) -> RunArtifact:
    """Execute the full governed pipeline.

    Args:
        request: GenerateRequest with user_id, grade, topic
        status_callback: optional function for UI progress updates

    Returns:
        RunArtifact — complete audit trail regardless of outcome
    """
    generator = GeneratorAgent()
    reviewer = ReviewerAgent()
    refiner = RefinerAgent()
    tagger = TaggerAgent()

    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc).isoformat()
    attempts = []

    def update(msg):
        if status_callback:
            status_callback(msg)

    # ── Step 1: Initial generation ──────────────────────────────
    attempt_1 = AttemptLog(attempt=1)

    update("📝 Generator is creating content...")
    try:
        draft = generator.run(request.grade, request.topic)
        attempt_1.draft = draft
        update("✅ Initial content generated")
    except ValueError as e:
        attempt_1.errors.append(f"Generator failed: {e}")
        attempts.append(attempt_1)
        update("❌ Generator failed — schema validation error")
        return _finalize(run_id, request, attempts, "rejected",
                         None, None, started_at)

    # ── Step 2: Review the first draft ──────────────────────────
    update("🔍 Reviewer is evaluating content...")
    try:
        review = reviewer.run(draft, request.grade, request.topic)
        attempt_1.review = review
        update(f"📋 Review complete — {'PASS' if review.passed else 'FAIL'}")
    except ValueError as e:
        attempt_1.errors.append(f"Reviewer failed: {e}")
        attempts.append(attempt_1)
        update("❌ Reviewer failed — schema validation error")
        return _finalize(run_id, request, attempts, "rejected",
                         draft, None, started_at)

    attempts.append(attempt_1)

    # ── If passed on first try ──────────────────────────────────
    if review.passed:
        update("🏷️ Tagging approved content...")
        tags = _safe_tag(tagger, draft, request.grade, update)
        update("✅ Pipeline complete — content approved!")
        return _finalize(run_id, request, attempts, "approved",
                         draft, tags, started_at)

    # ── Step 3: Refinement loop (max 2 attempts) ────────────────
    current_draft = draft
    current_feedback = review.feedback

    for i in range(1, MAX_REFINEMENT_ATTEMPTS + 1):
        attempt_n = AttemptLog(attempt=i + 1)

        update(f"🔄 Refinement attempt {i}/{MAX_REFINEMENT_ATTEMPTS}...")
        try:
            refined = refiner.run(
                current_draft, current_feedback,
                request.grade, request.topic
            )
            attempt_n.refined = refined
            update(f"✅ Refinement {i} complete")
        except ValueError as e:
            attempt_n.errors.append(f"Refiner failed: {e}")
            attempts.append(attempt_n)
            update(f"❌ Refiner failed on attempt {i}")
            return _finalize(run_id, request, attempts, "rejected",
                             None, None, started_at)

        # review the refined version
        update("🔍 Reviewing refined content...")
        try:
            refined_review = reviewer.run(
                refined, request.grade, request.topic
            )
            attempt_n.review = refined_review
            update(f"📋 Review {i + 1} — {'PASS' if refined_review.passed else 'FAIL'}")
        except ValueError as e:
            attempt_n.errors.append(f"Reviewer failed: {e}")
            attempts.append(attempt_n)
            update("❌ Reviewer failed on refined content")
            return _finalize(run_id, request, attempts, "rejected",
                             refined, None, started_at)

        attempts.append(attempt_n)

        if refined_review.passed:
            update("🏷️ Tagging approved content...")
            tags = _safe_tag(tagger, refined, request.grade, update)
            update("✅ Pipeline complete — content approved after refinement!")
            return _finalize(run_id, request, attempts, "approved",
                             refined, tags, started_at)

        # prepare for next refinement iteration
        current_draft = refined
        current_feedback = refined_review.feedback

    # ── Exhausted all refinement attempts ───────────────────────
    update("❌ Content rejected after maximum refinement attempts")
    return _finalize(run_id, request, attempts, "rejected",
                     None, None, started_at)


def _safe_tag(tagger, content, grade, update):
    """Run tagger with error handling — tagging failure shouldn't
    reject otherwise-approved content."""
    try:
        return tagger.run(content, grade)
    except Exception as e:
        update(f"⚠️ Tagger failed ({e}) — content still approved, tags omitted")
        return None


def _finalize(run_id, request, attempts, status, content, tags, started_at):
    """Build, persist, and return the complete RunArtifact."""
    finished_at = datetime.now(timezone.utc).isoformat()

    artifact = RunArtifact(
        run_id=run_id,
        input=request,
        attempts=attempts,
        final=FinalDecision(
            status=status,
            content=content,
            tags=tags,
        ),
        timestamps=Timestamps(
            started_at=started_at,
            finished_at=finished_at,
        ),
    )

    # persist to SQLite
    try:
        save_artifact(artifact)
    except Exception:
        pass  # storage failure shouldn't break the pipeline response

    return artifact
