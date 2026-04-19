# EduAgent Pipeline — AI-Powered Educational Content Generator & Reviewer

A two-agent pipeline that generates age-appropriate educational content and then reviews it for quality. If the review fails, the system automatically refines the content using the reviewer's feedback — all visible in real time through a Streamlit UI.

## How It Works

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Generator    │ ──> │  Reviewer    │ ──> │  Refined     │
│  Agent        │     │  Agent       │     │  (if needed) │
│               │     │              │     │              │
│ grade + topic │     │ pass / fail  │     │ uses feedback│
│ → explanation │     │ + feedback   │     │ to improve   │
│ → 3 MCQs      │     │              │     │              │
└──────────────┘     └──────────────┘     └──────────────┘
```

**Generator Agent** takes a grade level and topic, then produces a structured JSON response containing a kid-friendly explanation and 3 multiple-choice questions.

**Reviewer Agent** evaluates the generated content against criteria: age appropriateness, factual correctness, clarity, and structural compliance. Returns a pass/fail verdict with actionable feedback.

If the reviewer says "fail", the pipeline feeds the feedback back to the generator for **one refinement attempt**, then reviews again.

## Setup

### 1. Clone and install dependencies

```bash
git clone <your-repo-url>
cd edu-agent-pipeline
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux
pip install -r requirements.txt
```

### 2. Configure API key

This project uses Google Gemini (free tier). Get an API key from [Google AI Studio](https://aistudio.google.com/apikey).

```bash
# Option A: create a .env file
cp .env.example .env
# edit .env and paste your key

# Option B: set environment variable directly
set GOOGLE_API_KEY=your_key_here        # Windows
# export GOOGLE_API_KEY=your_key_here   # Mac/Linux
```

### 3. Run the app

```bash
streamlit run app.py
```

The app opens at `http://localhost:8501`. Pick a grade, type a topic, and hit "Run Pipeline".

## Project Structure

```
edu-agent-pipeline/
├── app.py              # Streamlit UI — displays the pipeline flow
├── pipeline.py         # Orchestrates generator → reviewer → (retry)
├── agents.py           # GeneratorAgent and ReviewerAgent classes
├── schemas.py          # Pydantic models (strict JSON contracts)
├── prompts.py          # Prompt templates for both agents
├── requirements.txt    # Python dependencies
├── .env.example        # API key template
└── README.md           # This file
```

## Data Contracts

### Generator Input
```json
{
  "grade": 4,
  "topic": "Types of angles"
}
```

### Generator Output
```json
{
  "explanation": "An angle is formed when two lines meet at a point...",
  "mcqs": [
    {
      "question": "What do we call an angle less than 90 degrees?",
      "options": ["Acute angle", "Right angle", "Obtuse angle", "Straight angle"],
      "answer": "A"
    }
  ]
}
```

### Reviewer Output
```json
{
  "status": "pass",
  "feedback": []
}
```

Or on failure:
```json
{
  "status": "fail",
  "feedback": [
    "The explanation uses the word 'perpendicular' which is too advanced for grade 2",
    "Question 3 has two correct options"
  ]
}
```

## Design Decisions

- **Google Gemini** over OpenAI — free tier makes it easy for reviewers to test without billing setup
- **Pydantic validation** — every LLM response is validated against a strict schema before it reaches the UI, so malformed outputs get caught early
- **Single retry cap** — keeps the pipeline deterministic and avoids runaway API calls
- **Status callbacks** — the UI shows real-time progress so you can see exactly which agent is working at each step
- **Low temperature (0.4)** — balances creativity with structural consistency in outputs

## Tech Stack

- Python 3.10+
- Streamlit (UI)
- Pydantic v2 (data validation)
- Google Gen AI SDK (LLM)
