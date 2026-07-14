#!/usr/bin/env python3
"""
NASA RAG Chat with RAGAS Evaluation Integration

Enhanced version of the simple RAG chat that includes real-time evaluation
and feedback collection for continuous improvement.
"""

import streamlit as st
import os
import json
import pandas as pd

import ragas_evaluator
import rag_client
import llm_client

from pathlib import Path
from typing import Dict, List, Optional

# RAGAS imports
try:
    from ragas import SingleTurnSample
    RAGAS_AVAILABLE = True
except ImportError:
    RAGAS_AVAILABLE = False
    st.warning("RAGAS not available. Install with: pip install ragas")

# Page configuration
st.set_page_config(
    page_title="NASA RAG Chat with Evaluation",
    page_icon="🚀",
    layout="wide"
)

# ---------------------------------------------------------------------------
# Helper wrappers around the backend modules
# ---------------------------------------------------------------------------

def discover_chroma_backends() -> Dict[str, Dict[str, str]]:
    """Discover available ChromaDB backends in the project directory."""
    return rag_client.discover_chroma_backends()


@st.cache_resource
def initialize_rag_system(chroma_dir: str, collection_name: str):
    """Initialize the RAG system with specified backend (cached for performance)."""
    try:
        return rag_client.initialize_rag_system(chroma_dir, collection_name)
    except Exception as e:
        return None, False, str(e)


def retrieve_documents(
    collection,
    query: str,
    n_results: int = 3,
    mission_filter: Optional[str] = None,
) -> Optional[Dict]:
    """Retrieve relevant documents from ChromaDB with optional mission filtering."""
    try:
        return rag_client.retrieve_documents(collection, query, n_results, mission_filter)
    except Exception as e:
        st.error(f"Error retrieving documents: {e}")
        return None


def format_context(documents: List[str], metadatas: List[Dict]) -> str:
    """Format retrieved documents into context."""
    return rag_client.format_context(documents, metadatas)


def generate_response(
    openai_key: str,
    user_message: str,
    context: str,
    conversation_history: List[Dict],
    model: str = "gpt-3.5-turbo",
) -> str:
    """Generate response using OpenAI with context."""
    try:
        return llm_client.generate_response(
            openai_key, user_message, context, conversation_history, model
        )
    except Exception as e:
        return f"Error generating response: {e}"


def evaluate_response_quality(
    question: str, answer: str, contexts: List[str]
) -> Dict[str, float]:
    """Evaluate response quality using RAGAS metrics."""
    try:
        return ragas_evaluator.evaluate_response_quality(question, answer, contexts)
    except Exception as e:
        return {"error": f"Evaluation failed: {str(e)}"}


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

def display_evaluation_metrics(scores: Dict[str, float]):
    """Display evaluation metrics in the sidebar."""
    if "error" in scores:
        st.sidebar.error(f"Evaluation Error: {scores['error']}")
        return

    st.sidebar.subheader("📊 Response Quality")

    for metric_name, score in scores.items():
        if isinstance(score, (int, float)):
            # Colour-code based on score
            if score >= 0.8:
                color = "green"
            elif score >= 0.6:
                color = "orange"
            else:
                color = "red"

            st.sidebar.metric(
                label=metric_name.replace("_", " ").title(),
                value=f"{score:.3f}",
                delta=None,
            )
            # Add progress bar
            st.sidebar.progress(score)


def run_batch_evaluation(openai_key: str, eval_file: str, collection, n_docs: int):
    """
    Load evaluation_dataset.txt / test_questions.json, run end-to-end evaluation
    for each question and display per-question + aggregate results.
    """
    # ── Load questions ──────────────────────────────────────────────────────
    questions = []
    path = Path(eval_file)

    if not path.exists():
        st.error(f"Evaluation file not found: {eval_file}")
        return

    if path.suffix == ".json":
        with open(path) as f:
            data = json.load(f)
        # Support {"questions": [...]} or plain list
        questions = data if isinstance(data, list) else data.get("questions", [])
    else:  # .txt — one question per non-empty line
        with open(path) as f:
            questions = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    if not questions:
        st.warning("No questions found in evaluation file.")
        return

    st.info(f"Running batch evaluation on {len(questions)} questions…")
    rows = []
    progress = st.progress(0)

    for idx, item in enumerate(questions):
        # Each item can be a plain string or a dict with "question" key
        question = item if isinstance(item, str) else item.get("question", str(item))

        # Retrieve
        docs_result = retrieve_documents(collection, question, n_docs)
        documents, metadatas = [], []
        if docs_result and docs_result.get("documents"):
            documents = docs_result["documents"][0]  # list of chunk strings
            metadatas = docs_result["metadatas"][0]  # list of metadata dicts

        context = format_context(documents, metadatas) if documents else ""

        # Generate
        answer = generate_response(openai_key, question, context, [])

        # Evaluate
        scores = evaluate_response_quality(question, answer, documents)

        row = {"question": question, "answer": answer}
        row.update(scores)
        rows.append(row)

        progress.progress((idx + 1) / len(questions))

    # ── Display results ──────────────────────────────────────────────────────
    df = pd.DataFrame(rows)
    st.subheader("📋 Per-Question Results")
    st.dataframe(df, use_container_width=True)

    # Aggregate (mean) for numeric metric columns
    metric_cols = [c for c in df.columns if c not in ("question", "answer", "error")]
    if metric_cols:
        numeric_df = df[metric_cols].apply(pd.to_numeric, errors="coerce")
        st.subheader("📈 Aggregate Scores (Mean)")
        st.dataframe(numeric_df.mean().rename("mean").to_frame(), use_container_width=True)
        st.bar_chart(numeric_df.mean())


# ---------------------------------------------------------------------------
# Main Streamlit app
# ---------------------------------------------------------------------------

def main():
    st.title("🚀 NASA Space Mission Chat with Evaluation")
    st.markdown("Chat with AI about NASA space missions with real-time quality evaluation")

    # ── Session state ────────────────────────────────────────────────────────
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "current_backend" not in st.session_state:
        st.session_state.current_backend = None
    if "last_evaluation" not in st.session_state:
        st.session_state.last_evaluation = None
    if "last_contexts" not in st.session_state:
        st.session_state.last_contexts = []

    # ── Sidebar ──────────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("⚙️ Configuration")

        # Discover available backends
        with st.spinner("Discovering ChromaDB backends…"):
            available_backends = discover_chroma_backends()

        if not available_backends:
            st.error("No ChromaDB backends found!")
            st.info("Please run the embedding pipeline first:\n`python embedding_pipeline.py`")
            st.stop()

        # Backend selection
        st.subheader("🗄️ ChromaDB Backend")
        backend_options = {k: v["display_name"] for k, v in available_backends.items()}
        selected_backend_key = st.selectbox(
            "Select Document Collection",
            options=list(backend_options.keys()),
            format_func=lambda x: backend_options[x],
            help="Choose which document collection to use for retrieval",
        )
        selected_backend = available_backends[selected_backend_key]

        # API Key
        st.subheader("🔑 OpenAI Settings")
        openai_key = st.text_input(
            "OpenAI API Key",
            type="password",
            value=os.getenv("OPENAI_API_KEY", ""),
            help="Enter your OpenAI API key",
        )

        if not openai_key:
            st.warning("Please enter your OpenAI API key")
            st.stop()
        else:
            os.environ["CHROMA_OPENAI_API_KEY"] = openai_key

        # Model selection
        model_choice = st.selectbox(
            "OpenAI Model",
            options=["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo-preview"],
            help="Choose the OpenAI model for responses",
        )

        # Retrieval settings
        st.subheader("🔍 Retrieval Settings")
        n_docs = st.slider("Documents to retrieve", 1, 10, 3)

        # ── Mission filter (NEW) ─────────────────────────────────────────────
        st.subheader("🛸 Mission Filter")
        MISSIONS = ["All Missions", "Apollo 11", "Apollo 13", "Challenger"]
        selected_mission = st.selectbox(
            "Filter by Mission",
            options=MISSIONS,
            help="Restrict retrieved documents to a specific NASA mission",
        )
        mission_filter = None if selected_mission == "All Missions" else selected_mission

        # Evaluation settings
        st.subheader("📊 Evaluation Settings")
        enable_evaluation = st.checkbox("Enable RAGAS Evaluation", value=RAGAS_AVAILABLE)

        # Batch evaluation section
        st.subheader("🧪 Batch Evaluation")
        eval_file = st.text_input(
            "Evaluation file",
            value="evaluation_dataset.txt",
            help="Path to evaluation_dataset.txt or test_questions.json",
        )
        run_batch = st.button("▶️ Run Batch Evaluation", disabled=not openai_key)

        # Re-initialize when backend changes
        if st.session_state.current_backend != selected_backend_key:
            st.session_state.current_backend = selected_backend_key
            st.cache_resource.clear()

        # Display last evaluation metrics
        if st.session_state.last_evaluation and enable_evaluation:
            display_evaluation_metrics(st.session_state.last_evaluation)

    # ── Initialize RAG system ────────────────────────────────────────────────
    with st.spinner("Initializing RAG system…"):
        collection, success, error = initialize_rag_system(
            selected_backend["directory"],
            selected_backend["collection_name"],
        )

    if not success:
        st.error(f"Failed to initialize RAG system: {error}")
        st.stop()

    # ── Batch evaluation (runs in main area) ─────────────────────────────────
    if run_batch:
        run_batch_evaluation(openai_key, eval_file, collection, n_docs)
        st.stop()  # Don't show chat UI after batch run

    # ── Chat messages ────────────────────────────────────────────────────────
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # ── Chat input ───────────────────────────────────────────────────────────
    if prompt := st.chat_input("Ask about NASA space missions…"):
        # Add user message to history
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate assistant response
        with st.chat_message("assistant"):
            with st.spinner("Searching documents and generating response…"):

                # 1. Retrieve relevant documents (with optional mission filter)
                docs_result = retrieve_documents(
                    collection,
                    prompt,
                    n_docs,
                    mission_filter,          # ← passes selected mission
                )

                # 2. Build context from all retrieved chunks
                documents_list: List[str] = []
                metadatas_list: List[Dict] = []

                if docs_result and docs_result.get("documents"):
                    documents_list = docs_result["documents"][0]   # list of chunk strings
                    metadatas_list = docs_result["metadatas"][0]   # list of metadata dicts

                context = (
                    format_context(documents_list, metadatas_list)
                    if documents_list
                    else ""
                )
                st.session_state.last_contexts = documents_list

                # 3. Generate LLM response
                response = generate_response(
                    openai_key,
                    prompt,
                    context,
                    st.session_state.messages[:-1],   # history excluding current turn
                    model_choice,
                )
                st.markdown(response)

            # 4. Evaluate response quality if enabled
            if enable_evaluation and RAGAS_AVAILABLE:
                with st.spinner("Evaluating response quality…"):
                    evaluation_scores = evaluate_response_quality(
                        prompt,
                        response,
                        documents_list,
                    )
                st.session_state.last_evaluation = evaluation_scores

                # Show a quick inline summary
                if "error" not in evaluation_scores:
                    cols = st.columns(len(evaluation_scores))
                    for col, (metric, score) in zip(cols, evaluation_scores.items()):
                        if isinstance(score, (int, float)):
                            col.metric(
                                label=metric.replace("_", " ").title(),
                                value=f"{score:.3f}",
                            )

        # Add assistant response to history
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.rerun()


if __name__ == "__main__":
    main()
