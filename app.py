"""
Streamlit UI for the Educational Content Agent Pipeline.

Layout:
  - Sidebar: grade selector + topic input + run button
  - Main area: three collapsible sections showing each pipeline stage
  - Status bar with real-time updates during execution

Nothing fancy — the point is to make the agent flow visible and obvious.
"""

import os
from dotenv import load_dotenv

# load .env before anything else touches the API key
load_dotenv()

import streamlit as st
import json
from pipeline import run_pipeline

# ── Page config ─────────────────────────────────────────────────────
st.set_page_config(
    page_title="EduAgent Pipeline",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Custom CSS for a cleaner look ───────────────────────────────────
st.markdown("""
<style>
    /* tighten up the default streamlit spacing */
    .block-container { padding-top: 2rem; }
    
    /* status badges */
    .badge-pass {
        background-color: #22c55e;
        color: white;
        padding: 4px 12px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 14px;
    }
    .badge-fail {
        background-color: #ef4444;
        color: white;
        padding: 4px 12px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 14px;
    }
    
    /* mcq card styling */
    .mcq-card {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
    }
    
    /* pipeline flow indicator */
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
</style>
""", unsafe_allow_html=True)


# ── Sidebar inputs ──────────────────────────────────────────────────
with st.sidebar:
    st.title("🎓 EduAgent Pipeline")
    st.markdown("Generate and review educational content using AI agents.")
    st.divider()

    grade = st.number_input(
        "Student Grade Level",
        min_value=1,
        max_value=12,
        value=4,
        step=1,
        help="Content difficulty adapts to the grade level"
    )

    topic = st.text_input(
        "Topic",
        value="Types of angles",
        placeholder="e.g., Photosynthesis, Fractions, Solar System",
        help="What should the lesson cover?"
    )

    st.divider()
    run_clicked = st.button("▶ Run Pipeline", type="primary", use_container_width=True)

    # show the input JSON for reference
    st.markdown("##### Input JSON")
    st.json({"grade": grade, "topic": topic})

    st.divider()
    st.caption("Built with Streamlit + Google Gemini")


# ── Helper functions for rendering content ──────────────────────────

def render_explanation(explanation_text):
    """Display the explanation in a readable format."""
    st.markdown(explanation_text)


def render_mcqs(mcqs_list):
    """Render each MCQ as a styled card."""
    for i, mcq in enumerate(mcqs_list, 1):
        with st.container():
            st.markdown(f"**Question {i}:** {mcq['question']}")
            
            cols = st.columns(2)
            labels = ["A", "B", "C", "D"]
            for j, option in enumerate(mcq["options"]):
                col = cols[j % 2]
                # highlight the correct answer
                if labels[j] == mcq["answer"]:
                    col.markdown(f"✅ **{labels[j]}.** {option}")
                else:
                    col.markdown(f"⬜ **{labels[j]}.** {option}")
            
            st.divider()


def render_review(review_data):
    """Show review status and feedback items."""
    status = review_data["status"]
    
    if status == "pass":
        st.markdown('<span class="badge-pass">✓ PASS</span>', unsafe_allow_html=True)
        st.success("Content meets all quality criteria.")
    else:
        st.markdown('<span class="badge-fail">✗ FAIL</span>', unsafe_allow_html=True)
        if review_data.get("feedback"):
            st.markdown("**Issues found:**")
            for fb in review_data["feedback"]:
                st.markdown(f"- ⚠️ {fb}")


def render_flow_diagram(stage):
    """Simple text-based pipeline flow indicator at the top."""
    stages = {
        "idle": ("pending", "pending", "pending"),
        "generating": ("active", "pending", "pending"),
        "reviewing": ("done", "active", "pending"),
        "refining": ("done", "done", "active"),
        "complete": ("done", "done", "done"),
    }
    
    gen_cls, rev_cls, ref_cls = stages.get(stage, stages["idle"])
    
    st.markdown(f"""
    <div style="text-align: center; margin: 16px 0;">
        <span class="flow-step flow-{gen_cls}">1. Generate</span>
        <span style="color: #94a3b8;">→</span>
        <span class="flow-step flow-{rev_cls}">2. Review</span>
        <span style="color: #94a3b8;">→</span>
        <span class="flow-step flow-{ref_cls}">3. Refine (if needed)</span>
    </div>
    """, unsafe_allow_html=True)


# ── Main area ───────────────────────────────────────────────────────

st.title("Educational Content Pipeline")
st.markdown("Two AI agents work together: one **generates** learning content, "
            "the other **reviews** it. If the review fails, the content is "
            "automatically refined using the reviewer's feedback.")

# run the pipeline when button is clicked
if run_clicked:
    if not topic.strip():
        st.error("Please enter a topic before running the pipeline.")
    else:
        # progress tracking
        status_placeholder = st.empty()
        progress_bar = st.progress(0)
        step_count = [0]  # mutable container for the callback

        def on_status(msg):
            step_count[0] += 1
            # rough progress estimate (max ~6 steps if refinement happens)
            progress_bar.progress(min(step_count[0] / 6, 1.0))
            status_placeholder.info(msg)

        try:
            result = run_pipeline(grade, topic, status_callback=on_status)
            progress_bar.progress(1.0)
            status_placeholder.success("Pipeline complete!")

            # store in session state so it persists across reruns
            st.session_state["result"] = result.model_dump()

        except Exception as e:
            progress_bar.empty()
            status_placeholder.error(f"Pipeline error: {str(e)}")
            st.stop()

# ── Display results if we have them ─────────────────────────────────

if "result" in st.session_state:
    result = st.session_state["result"]
    
    # figure out what stage we reached
    has_refinement = result.get("refined") is not None
    render_flow_diagram("complete")

    # ── Section 1: Generated Content (Draft) ────────────────────
    st.header("📝 Stage 1: Generated Content (Draft)")
    
    tab_pretty, tab_json = st.tabs(["Formatted View", "Raw JSON"])
    
    with tab_pretty:
        st.subheader("Explanation")
        render_explanation(result["generated"]["explanation"])
        
        st.subheader("Quiz Questions")
        render_mcqs(result["generated"]["mcqs"])
    
    with tab_json:
        st.json(result["generated"])

    # ── Section 2: Reviewer Verdict ─────────────────────────────
    st.header("🔍 Stage 2: Reviewer Verdict")
    render_review(result["review"])
    
    with st.expander("View reviewer output JSON"):
        st.json(result["review"])

    # ── Section 3: Refined Content (only if review failed) ──────
    if has_refinement:
        st.header("🔄 Stage 3: Refined Content")
        st.info("The reviewer found issues with the initial content. "
                "Below is the refined version generated using the reviewer's feedback.")
        
        tab_pretty2, tab_json2 = st.tabs(["Formatted View", "Raw JSON"])
        
        with tab_pretty2:
            st.subheader("Explanation (Refined)")
            render_explanation(result["refined"]["explanation"])
            
            st.subheader("Quiz Questions (Refined)")
            render_mcqs(result["refined"]["mcqs"])
        
        with tab_json2:
            st.json(result["refined"])

        # second review result
        if result.get("refined_review"):
            st.header("🔍 Stage 3b: Second Review")
            render_review(result["refined_review"])
            
            with st.expander("View second review JSON"):
                st.json(result["refined_review"])
    else:
        st.header("🔄 Stage 3: Refinement")
        st.success("No refinement needed — content passed review on the first attempt! 🎉")

    # ── Full pipeline JSON dump (for debugging / demo) ──────────
    with st.expander("📦 View Complete Pipeline Result (JSON)"):
        st.json(result)

else:
    # nothing run yet — show a placeholder
    render_flow_diagram("idle")
    st.info("👈 Configure grade and topic in the sidebar, then click **Run Pipeline** to start.")
