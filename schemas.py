"""
Pydantic models for the governed content pipeline.

Every agent input/output and the overall RunArtifact are defined here
so validation is strict and consistent across the whole system.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Literal
from enum import Enum


# ── Enums ────────────────────────────────────────────────────────────

class DifficultyLevel(str, Enum):
    EASY = "Easy"
    MEDIUM = "Medium"
    HARD = "Hard"


class BloomsLevel(str, Enum):
    REMEMBERING = "Remembering"
    UNDERSTANDING = "Understanding"
    APPLYING = "Applying"
    ANALYZING = "Analyzing"
    EVALUATING = "Evaluating"
    CREATING = "Creating"


# ── Request model ────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    """What comes in from the API or the UI."""
    user_id: str = Field(min_length=1, description="Identifier for the requesting user")
    grade: int = Field(ge=1, le=12, description="Student grade level (1-12)")
    topic: str = Field(min_length=2, description="Subject topic to teach")


# ── Generator output (strict schema) ────────────────────────────────

class Explanation(BaseModel):
    text: str = Field(min_length=10, description="Grade-appropriate explanation text")
    grade: int = Field(ge=1, le=12)


class MCQ(BaseModel):
    question: str = Field(min_length=5)
    options: List[str] = Field(min_length=4, max_length=4)
    correct_index: int = Field(ge=0, le=3)

    @field_validator("options")
    @classmethod
    def options_must_be_non_empty(cls, v):
        for i, opt in enumerate(v):
            if not opt.strip():
                raise ValueError(f"Option {i} is empty")
        return v


class TeacherNotes(BaseModel):
    learning_objective: str = Field(min_length=5)
    common_misconceptions: List[str] = Field(min_length=1)


class ContentArtifact(BaseModel):
    """The structured educational content the generator must produce."""
    explanation: Explanation
    mcqs: List[MCQ] = Field(min_length=3, max_length=5)
    teacher_notes: TeacherNotes


# ── Reviewer output (quantitative + explainable) ────────────────────

class FeedbackItem(BaseModel):
    """A single piece of feedback tied to a specific field."""
    field: str = Field(description="Dot-path to the problematic field, e.g. 'explanation.text'")
    issue: str = Field(description="What's wrong and how to fix it")


class ReviewScores(BaseModel):
    age_appropriateness: int = Field(ge=1, le=5)
    correctness: int = Field(ge=1, le=5)
    clarity: int = Field(ge=1, le=5)
    coverage: int = Field(ge=1, le=5)


class ReviewReport(BaseModel):
    """Reviewer verdict with numeric scores and field-level feedback."""
    scores: ReviewScores
    # 'pass' is a Python keyword, so we alias it
    passed: bool = Field(alias="pass", default=False)
    feedback: List[FeedbackItem] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


# ── Tagger output ───────────────────────────────────────────────────

class Tags(BaseModel):
    subject: str
    topic: str
    grade: int = Field(ge=1, le=12)
    difficulty: DifficultyLevel
    content_type: List[str] = Field(min_length=1)
    blooms_level: BloomsLevel


# ── Run artifact (full lifecycle record) ─────────────────────────────

class AttemptLog(BaseModel):
    """One generate-review cycle."""
    attempt: int
    draft: Optional[ContentArtifact] = None
    review: Optional[ReviewReport] = None
    refined: Optional[ContentArtifact] = None
    errors: List[str] = Field(default_factory=list)


class FinalDecision(BaseModel):
    status: Literal["approved", "rejected"]
    content: Optional[ContentArtifact] = None
    tags: Optional[Tags] = None


class Timestamps(BaseModel):
    started_at: str
    finished_at: str


class RunArtifact(BaseModel):
    """Complete audit trail for a single pipeline run."""
    run_id: str
    input: GenerateRequest
    attempts: List[AttemptLog]
    final: FinalDecision
    timestamps: Timestamps
