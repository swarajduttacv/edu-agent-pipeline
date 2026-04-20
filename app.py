"""
Streamlit UI for the Governed Educational Content Pipeline.

Layout:
  - Sidebar: user ID + grade + topic + run button
  - Main area: pipeline flow, attempt logs, final decision, tags
  - History tab: past runs for the current user

Extends the Part 1 UI with audit trail visualization, scores,
field-level feedback, and refinement attempt tracking.
"""

import os
from dotenv import load_dotenv

load_dotenv()

import streamlit as st

# bridge Streamlit Cloud secrets to env vars
try:
    if "GOOGLE_API_KEY" in st.secrets:
        os.environ["GOOGLE_API_KEY"] = st.secrets["GOOGLE_API_KEY"]
except FileNotFoundError:
    pass

import json
from schemas import GenerateRequest, RunArtifact
from orchestrator import run_pipeline
from storage import get_history

# ── Page config ─────────────────────────────────────────────────────
st.set_page_config(
    page_title="EduAgent Pipeline v2",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Custom CSS ──────────────────────────────────────────────────────
st.markdown("""
<style>
    .block-container { padding-top: 2rem; }

    .badge-approved {
        background-color: #22c55e;
        color: white;
        padding: 4px 14px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 14px;
    }
    .badge-rejected {
        background-color: #ef4444;
        color: white;
        padding: 4px 14px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 14px;
    }
    .badge-pass {
        background-color: #22c55e;
        color: white;
        padding: 3px 10px;
        border-radius: 10px;
        font-weight: 600;
        font-size: 12px;
    }
    .badge-fail {
        background-color: #ef4444;
        color: white;
        padding: 3px 10px;
        border-radius: 10px;
        font-weight: 600;
        font-size: 12px;
    }

    .score-bar {
        display: inline-block;
        height: 8px;
        border-radius: 4px;
        margin-right: 8px;
    }

    .flow-step {
        display: inline-block;
        padding: 6px 16px;
        border-radius: 20px;
        margin: 0 4px;
        font-size: 13px;
        font-weight: 500;
    }
    .flow-active { background: #3b82f6; color: white; }
    .flow-done { background: #22c55e; color: white; }
    .flow-pending { background: #e2e8f0; color: #64748b; }
    .flow-failed { background: #ef4444; color: white; }
</style>
""", unsafe_allow_html=True)


# ── Sidebar ─────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🎓 EduAgent Pipeline v2")
    st.markdown("Governed, auditable AI content generation.")
    st.divider()

    tab_gen, tab_hist = st.tabs(["Generate", "History"])

    with tab_gen:
        user_id = st.text_input(
            "User ID",
            value="user_01",
            help="Identifier used to track your generation history"
        )

        grade = st.number_input(
            "Student Grade Level",
            min_value=1, max_value=12, value=5, step=1,
            help="Content difficulty adapts to the grade level"
        )

        topic = st.text_input(
            "Topic",
            value="Fractions as parts of a whole",
            placeholder="e.g., Photosynthesis, Fractions, Solar System",
            help="What should the lesson cover?"
        )

        st.divider()
        run_clicked = st.button("▶ Run Pipeline", type="primary", use_container_width=True)

        st.markdown("##### Input JSON")
        st.json({"user_id": user_id, "grade": grade, "topic": topic})

    with tab_hist:
        hist_user = st.text_input("Look up User ID", value="user_01", key="hist_user")
        load_hist = st.button("📜 Load History", use_container_width=True)

    st.divider()
    st.caption("Built with Streamlit + Google Gemini + FastAPI")


# ── Helper renderers ────────────────────────────────────────────────

def render_flow(status):
    """Pipeline flow indicator."""
    if status == "approved":
        classes = ("flow-done", "flow-done", "flow-done", "flow-done")
    elif status == "rejected":
        classes = ("flow-done", "flow-done", "flow-failed", "flow-pending")
    else:
        classes = ("flow-pending", "flow-pending", "flow-pending", "flow-pending")

    gen, rev, ref, tag = classes
    st.markdown(f"""
    <div style="text-align: center; margin: 16px 0;">
        <span class="flow-step {gen}">1. Generate</span>
        <span style="color: #94a3b8;">→</span>
        <span class="flow-step {rev}">2. Review</span>
        <span style="color: #94a3b8;">→</span>
        <span class="flow-step {ref}">3. Refine</span>
        <span style="color: #94a3b8;">→</span>
        <span class="flow-step {tag}">4. Tag</span>
    </div>
    """, unsafe_allow_html=True)


def render_scores(scores_dict):
    """Render review scores as colored metrics."""
    cols = st.columns(4)
    labels = {
        "age_appropriateness": "Age Fit",
        "correctness": "Correct",
        "clarity": "Clarity",
        "coverage": "Coverage",
    }
    for col, (key, label) in zip(cols, labels.items()):
        val = scores_dict.get(key, 0)
        color = "#22c55e" if val >= 4 else "#f59e0b" if val >= 3 else "#ef4444"
        col.metric(label, f"{val}/5")


def render_feedback(feedback_list):
    """Render field-level feedback items."""
    if not feedback_list:
        st.success("No issues found.")
        return
    for item in feedback_list:
        if isinstance(item, dict):
            field = item.get("field", "?")
            issue = item.get("issue", "")
            st.markdown(f"- ⚠️ **`{field}`** — {issue}")
        else:
            st.markdown(f"- ⚠️ {item}")


def render_content(content_dict):
    """Render ContentArtifact in a readable format."""
    if not content_dict:
        st.warning("No content available.")
        return

    # explanation
    exp = content_dict.get("explanation", {})
    st.markdown(f"**Explanation (Grade {exp.get('grade', '?')}):**")
    st.markdown(exp.get("text", ""))

    # MCQs
    st.markdown("**Quiz Questions:**")
    for i, mcq in enumerate(content_dict.get("mcqs", []), 1):
        st.markdown(f"**Q{i}.** {mcq['question']}")
        for j, opt in enumerate(mcq["options"]):
            marker = "✅" if j == mcq.get("correct_index") else "⬜"
            st.markdown(f"  {marker} {opt}")
        st.markdown("")

    # teacher notes
    notes = content_dict.get("teacher_notes", {})
    if notes:
        st.markdown(f"**Learning Objective:** {notes.get('learning_objective', '')}")
        misconceptions = notes.get("common_misconceptions", [])
        if misconceptions:
            st.markdown("**Common Misconceptions:**")
            for m in misconceptions:
                st.markdown(f"- {m}")


def render_tags(tags_dict):
    """Render classification tags."""
    if not tags_dict:
        st.info("No tags (content was not approved).")
        return
    cols = st.columns(3)
    cols[0].markdown(f"**Subject:** {tags_dict.get('subject', '?')}")
    cols[1].markdown(f"**Difficulty:** {tags_dict.get('difficulty', '?')}")
    cols[2].markdown(f"**Bloom's Level:** {tags_dict.get('blooms_level', '?')}")

    content_types = tags_dict.get("content_type", [])
    if content_types:
        st.markdown(f"**Content Types:** {', '.join(content_types)}")


def render_artifact(artifact_dict):
    """Render a complete RunArtifact."""
    final = artifact_dict.get("final", {})
    status = final.get("status", "unknown")
    attempts = artifact_dict.get("attempts", [])
    timestamps = artifact_dict.get("timestamps", {})

    # status badge
    badge_class = "badge-approved" if status == "approved" else "badge-rejected"
    st.markdown(
        f'<span class="{badge_class}">{status.upper()}</span>',
        unsafe_allow_html=True
    )

    render_flow(status)

    # timestamps
    st.caption(
        f"Started: {timestamps.get('started_at', '?')} | "
        f"Finished: {timestamps.get('finished_at', '?')}"
    )

    # each attempt as an expander
    for attempt in attempts:
        attempt_num = attempt.get("attempt", "?")
        label = f"Attempt {attempt_num}"

        # add context to the label
        review = attempt.get("review")
        if review:
            passed = review.get("passed", False)
            label += f" — {'PASS' if passed else 'FAIL'}"

        with st.expander(label, expanded=(attempt_num == len(attempts))):
            # draft (only attempt 1 has this)
            if attempt.get("draft"):
                st.subheader("Draft")
                render_content(attempt["draft"])
                st.divider()

            # refined content (attempts 2+)
            if attempt.get("refined"):
                st.subheader("Refined Content")
                render_content(attempt["refined"])
                st.divider()

            # review scores
            if review:
                st.subheader("Review Scores")
                scores = review.get("scores", {})
                render_scores(scores)
                avg = sum(scores.values()) / max(len(scores), 1)
                st.caption(f"Average: {avg:.1f}/5.0")
                st.markdown("")
                render_feedback(review.get("feedback", []))

            # errors
            errors = attempt.get("errors", [])
            if errors:
                st.subheader("Errors")
                for err in errors:
                    st.error(err)

    # final approved content
    if status == "approved" and final.get("content"):
        st.header("✅ Approved Content")
        render_content(final["content"])

        if final.get("tags"):
            st.header("🏷️ Tags")
            render_tags(final["tags"])

    # full JSON dump
    with st.expander("📦 View Complete RunArtifact (JSON)"):
        st.json(artifact_dict)


# ── Main area ───────────────────────────────────────────────────────

st.title("Educational Content Pipeline")
st.markdown(
    "Four AI agents work together: **Generator** creates content, "
    "**Reviewer** scores it quantitatively, **Refiner** improves it "
    "if needed (up to 2 attempts), and **Tagger** classifies approved content. "
    "Every run produces a complete audit trail."
)

# ── Run pipeline ────────────────────────────────────────────────────
if run_clicked:
    if not topic.strip():
        st.error("Please enter a topic before running the pipeline.")
    else:
        status_placeholder = st.empty()
        progress_bar = st.progress(0)
        step_count = [0]

        def on_status(msg):
            step_count[0] += 1
            progress_bar.progress(min(step_count[0] / 10, 1.0))
            status_placeholder.info(msg)

        try:
            request = GenerateRequest(
                user_id=user_id,
                grade=grade,
                topic=topic,
            )
            artifact = run_pipeline(request, status_callback=on_status)
            progress_bar.progress(1.0)

            if artifact.final.status == "approved":
                status_placeholder.success("Pipeline complete — content approved! ✅")
            else:
                status_placeholder.warning("Pipeline complete — content rejected ❌")

            st.session_state["result"] = artifact.model_dump(by_alias=True)

        except Exception as e:
            progress_bar.empty()
            status_placeholder.error(f"Pipeline error: {str(e)}")
            st.stop()

# ── Display current result ──────────────────────────────────────────
if "result" in st.session_state:
    st.divider()
    render_artifact(st.session_state["result"])

elif not run_clicked:
    render_flow("idle")
    st.info("👈 Configure inputs in the sidebar, then click **Run Pipeline** to start.")

# ── History view ────────────────────────────────────────────────────
if load_hist:
    st.divider()
    st.header(f"📜 History for {hist_user}")

    history = get_history(hist_user)
    if not history:
        st.info("No runs found for this user.")
    else:
        for i, art in enumerate(history):
            art_dict = art.model_dump(by_alias=True)
            status = art_dict["final"]["status"]
            ts = art_dict["timestamps"]["started_at"][:19]
            badge = "badge-approved" if status == "approved" else "badge-rejected"

            with st.expander(
                f"Run {art_dict['run_id'][:8]}... — {art_dict['input']['topic']} "
                f"(Grade {art_dict['input']['grade']}) — {ts}"
            ):
                render_artifact(art_dict)
