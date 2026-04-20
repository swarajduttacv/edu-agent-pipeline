# EduAgent Pipeline v2 — Governed, Auditable AI Content Pipeline

A governed AI pipeline that generates, reviews, refines, and tags educational content with full audit trails. Extends the Part 1 two-agent pipeline into a four-agent system with schema validation, quantitative scoring, bounded retries, and persistent run artifacts.

## How It Works

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Generator    │ ──► │  Reviewer    │ ──► │  Refiner     │ ──► │  Tagger      │
│  Agent        │     │  Agent       │     │  (if needed) │     │  (if approved)│
│               │     │              │     │              │     │              │
│ grade + topic │     │ scores 1-5   │     │ max 2 tries  │     │ subject,     │
│ → explanation │     │ field issues │     │ uses feedback│     │ difficulty,  │
│ → 3 MCQs      │     │ pass / fail  │     │ to improve   │     │ Bloom's level│
│ → teacher     │     │              │     │              │     │              │
│   notes       │     │              │     │              │     │              │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
```

Every run produces a **RunArtifact** — a single JSON document that captures inputs, all draft attempts, review scores, refinement logs, the final decision, and timestamps.

## Agent Roles

### Generator Agent
Takes a grade level and topic. Produces a structured `ContentArtifact` with an age-appropriate explanation, 3 multiple-choice questions (with `correct_index`), and teacher notes (learning objective + common misconceptions). If schema validation fails, retries the LLM call once before failing gracefully.

### Reviewer Agent
Evaluates content on four dimensions (age appropriateness, correctness, clarity, coverage), each scored 1–5. Produces field-referenced feedback (e.g., `explanation.text`, `mcqs[1].question`) so issues are traceable. Pass/fail is determined by code-level thresholds, not left to the LLM.

### Refiner Agent
Takes a failing draft plus the reviewer's field-level feedback and produces an improved version. The orchestrator caps refinement at 2 attempts — if content still fails after that, it's rejected.

### Tagger Agent
Classifies approved content only. Outputs subject, topic, grade, difficulty level, content types, and Bloom's taxonomy level.

## Schemas

### Generator Output (ContentArtifact)
```json
{
  "explanation": { "text": "...", "grade": 5 },
  "mcqs": [
    {
      "question": "...",
      "options": ["A", "B", "C", "D"],
      "correct_index": 1
    }
  ],
  "teacher_notes": {
    "learning_objective": "...",
    "common_misconceptions": ["..."]
  }
}
```

### Reviewer Output (ReviewReport)
```json
{
  "scores": {
    "age_appropriateness": 5,
    "correctness": 5,
    "clarity": 4,
    "coverage": 4
  },
  "pass": true,
  "feedback": [
    { "field": "explanation.text", "issue": "Sentence too complex" }
  ]
}
```

### Tagger Output (Tags)
```json
{
  "subject": "Mathematics",
  "topic": "Fractions",
  "grade": 5,
  "difficulty": "Medium",
  "content_type": ["Explanation", "Quiz"],
  "blooms_level": "Understanding"
}
```

### RunArtifact (Full Lifecycle)
```json
{
  "run_id": "uuid",
  "input": { "user_id": "u123", "grade": 5, "topic": "Fractions" },
  "attempts": [
    {
      "attempt": 1,
      "draft": { "..." },
      "review": { "..." },
      "refined": null,
      "errors": []
    }
  ],
  "final": {
    "status": "approved",
    "content": { "..." },
    "tags": { "..." }
  },
  "timestamps": {
    "started_at": "2025-01-01T00:00:00Z",
    "finished_at": "2025-01-01T00:00:05Z"
  }
}
```

## Quality Gates

Pass/fail thresholds enforced in code (`agents/reviewer.py`):

| Dimension | Minimum Score |
|---|---|
| Age Appropriateness | ≥ 4 |
| Correctness | ≥ 4 |
| Clarity | ≥ 4 |
| Coverage | ≥ 3 |
| **Average (all four)** | **≥ 4.0** |

All conditions must hold simultaneously for content to pass. The reviewer LLM produces the scores, but the pass/fail decision is applied deterministically in Python.

## Orchestration Flow

```
1. Generate draft (1 internal schema retry)
2. Review draft
3. If PASS → Tag → APPROVED
4. If FAIL → Refine (attempt 1) → Review
   a. If PASS → Tag → APPROVED
   b. If FAIL → Refine (attempt 2) → Review
      i.  If PASS → Tag → APPROVED
      ii. If FAIL → REJECTED
```

**Retry bounds:**
- Generator schema validation retry: 1
- Refinement attempts: max 2
- Review: runs after every draft/refinement

All steps are logged in the RunArtifact regardless of outcome.

## Persistence

SQLite database (`edu_pipeline.db`, auto-created on first run).

Single `run_artifacts` table with metadata columns (`user_id`, `status`, `grade`, `topic`) for indexing, plus the full RunArtifact stored as JSON.

## Setup

### 1. Clone and install

```bash
git clone <your-repo-url>
cd edu-agent-pipeline
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux
pip install -r requirements.txt
```

### 2. Configure API key

Get a key from [Google AI Studio](https://aistudio.google.com/apikey).

```bash
cp .env.example .env
# edit .env and paste your key
```

### 3. Run the app

**Streamlit UI:**
```bash
streamlit run app.py
```

**FastAPI (API-only):**
```bash
uvicorn api:app --reload
```

API docs at `http://localhost:8000/docs`.

## API Usage

```bash
# Generate content
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"user_id": "u123", "grade": 5, "topic": "Fractions as parts of a whole"}'

# View history
curl "http://localhost:8000/history?user_id=u123"
```

## Testing

```bash
pytest tests/ -v
```

All tests mock the LLM client — no API key needed.

| Test | What It Covers |
|---|---|
| `test_schema_validation.py` | Generator returns invalid output → pipeline rejects gracefully with error trail |
| `test_refine_pass.py` | Draft fails review → refiner fixes it → passes second review → approved with tags |
| `test_refine_reject.py` | Draft fails → 2 refinement attempts both fail → rejected, no tags, all attempts logged |

## Project Structure

```
edu-agent-pipeline/
├── agents/
│   ├── __init__.py
│   ├── generator.py       # Content generation with schema retry
│   ├── reviewer.py        # Quantitative scoring + pass/fail gating
│   ├── refiner.py         # Feedback-driven content improvement
│   └── tagger.py          # Classification of approved content
├── tests/
│   ├── test_schema_validation.py
│   ├── test_refine_pass.py
│   └── test_refine_reject.py
├── api.py                 # FastAPI endpoints
├── app.py                 # Streamlit UI
├── llm.py                 # LLM client wrapper (single mock point)
├── orchestrator.py        # Deterministic pipeline → RunArtifact
├── prompts.py             # Prompt templates for all agents
├── schemas.py             # Pydantic models (strict contracts)
├── storage.py             # SQLite persistence
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Trade-offs

- **Full RunArtifact as JSON in SQLite** — keeps the audit trail intact without schema migrations. Could normalize later, but not needed at this scale.
- **Pass/fail in code, not LLM** — LLMs are non-deterministic; applying thresholds in Python ensures consistent gating across runs.
- **2 refinement attempts max** — bounds API cost and prevents infinite retry loops on inherently difficult topics.
- **Single `llm.py` module** — one mock point for all tests. Swapping LLM providers is a one-file change.
- **Tagger failure doesn't reject content** — if content passes review but tagging fails, it's still approved (tags are metadata, not quality).
- **Google Gemini (free tier)** — easy for reviewers to test without billing setup.

## Tech Stack

- Python 3.10+
- Streamlit (UI)
- FastAPI + Uvicorn (API)
- Pydantic v2 (data validation)
- SQLite (persistence)
- Google Gen AI SDK (LLM)
- pytest (testing)
