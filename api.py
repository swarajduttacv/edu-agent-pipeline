"""
FastAPI endpoints for the governed content pipeline.

POST /generate — runs the full pipeline, returns a RunArtifact
GET /history   — returns stored artifacts for a user
"""

import os
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from schemas import GenerateRequest, RunArtifact
from orchestrator import run_pipeline
from storage import get_history


app = FastAPI(
    title="EduAgent Pipeline — Governed Content API",
    description="Auditable AI pipeline for educational content generation",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/generate", response_model=RunArtifact)
async def generate(request: GenerateRequest):
    """Run the full pipeline and return a complete RunArtifact.

    Even if the run fails (schema errors, repeated review failures),
    the response will still be a complete artifact with
    final.status="rejected" and the error trail in attempts.
    """
    artifact = run_pipeline(request)
    return artifact


@app.get("/history", response_model=list[RunArtifact])
async def history(user_id: str = Query(..., description="User ID to look up")):
    """Return stored RunArtifacts for a user, most recent first."""
    return get_history(user_id)
