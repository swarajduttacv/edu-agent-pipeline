"""
Data models for the generator and reviewer agents.
Keeping these separate so both agents and the pipeline can import
without circular dependency headaches.
"""

from pydantic import BaseModel, Field, conlist
from typing import List, Literal, Optional


class GeneratorInput(BaseModel):
    """What we send to the generator – grade level, topic, and
    optionally the reviewer's feedback if we're on a refinement pass."""
    grade: int = Field(ge=1, le=12, description="Student grade level (1-12)")
    topic: str = Field(min_length=2, description="Subject topic to teach")
    feedback: Optional[List[str]] = None  # only populated during retry


class MCQ(BaseModel):
    """Single multiple-choice question. We lock it to exactly 4 options
    so the UI can render consistently every time."""
    question: str
    options: conlist(str, min_length=4, max_length=4)
    answer: Literal["A", "B", "C", "D"]


class GeneratorOutput(BaseModel):
    """The structured content the generator must always produce.
    explanation = kid-friendly paragraph(s), mcqs = quiz questions."""
    explanation: str
    mcqs: conlist(MCQ, min_length=1)


class ReviewerInput(BaseModel):
    """Wraps everything the reviewer needs to judge the content."""
    grade: int
    topic: str
    content: GeneratorOutput


class ReviewerOutput(BaseModel):
    """Reviewer verdict. feedback list is empty when status is pass."""
    status: Literal["pass", "fail"]
    feedback: List[str] = Field(default_factory=list)


class PipelineResult(BaseModel):
    """Full pipeline run packaged up for the UI to display."""
    request: dict
    generated: dict
    review: dict
    refined: Optional[dict] = None
    refined_review: Optional[dict] = None
