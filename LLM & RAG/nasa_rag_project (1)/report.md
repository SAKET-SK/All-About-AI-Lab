# NASA RAG Chat System — Project Report

## 1. Project Overview

This project implements a **Retrieval-Augmented Generation (RAG)** system for querying NASA space mission documents. It combines semantic search via ChromaDB with OpenAI's language models to provide accurate, source-grounded answers about Apollo 11, Apollo 13, and the Challenger disaster. A real-time RAGAS evaluation layer scores every response for faithfulness and relevancy.

---

## 2. System Architecture

```
User Question
     │
     ▼
[chat.py - Streamlit UI]
     │
     ├──► [rag_client.py]  ──► ChromaDB (semantic search, mission filter)
     │         │
     │         ▼
     │    Retrieved Chunks + Metadata
     │
     ├──► [llm_client.py]  ──► OpenAI GPT (grounded answer generation)
     │
     └──► [ragas_evaluator.py] ──► RAGAS scores (Faithfulness, Relevancy, BLEU, ROUGE)
```

**Offline (one-time setup):**
```
Raw .txt Files  ──► [embedding_pipeline.py] ──► ChromaDB (embeddings + metadata)
```

---

## 3. File Descriptions

### `embedding_pipeline.py`
- Scans `apollo11/`, `apollo13/`, `challenger/` directories for `.txt` files
- Chunks text using configurable `--chunk-size` and `--chunk-overlap` CLI flags
- Applies sentence-boundary-aware splitting with consistent overlap
- Embeds each chunk using OpenAI `text-embedding-3-small`
- Stores chunks in ChromaDB with metadata: `source`, `mission`, `file_type`, `document_category`, `chunk_index`
- Supports `--update-mode skip|update|replace` for re-processing
- `--stats-only` flag prints total chunk count + breakdown by mission

**Example usage:**
```bash
python embedding_pipeline.py \
  --openai-key sk-... \
  --data-path ./data \
  --chroma-dir ./chroma_db_openai \
  --collection-name nasa_space_missions_text \
  --chunk-size 500 \
  --chunk-overlap 100 \
  --update-mode skip
```

### `rag_client.py`
- Connects to ChromaDB PersistentClient
- Issues cosine-similarity queries using the user question embedding
- Configurable `n_results` (top-k) at runtime
- Supports mission metadata filtering (`Apollo 11`, `Apollo 13`, `Challenger`)
- Formats retrieved chunks into a clean context string with clear separators and source attributions
- Deduplicates chunks by content before formatting

### `llm_client.py`
- Defines a NASA expert system prompt that instructs the model to cite sources and express uncertainty when context is insufficient
- Manages multi-turn conversation history (role + content per turn)
- Passes constructed context + user query to OpenAI Chat Completions API
- Uses `temperature=0.2` for factual, grounded responses

### `ragas_evaluator.py`
- Computes **Response Relevancy** and **Faithfulness** (required)
- Also computes **BLEU Score** and **ROUGE Score** (additional metrics)
- Accepts `(question, answer, contexts)` triple and returns `Dict[str, float]`
- Handles empty/malformed inputs with clear error messages — no crashes
- `batch_evaluate()` helper runs evaluation over a list of items and returns per-item + aggregate mean scores

### `chat.py`
- Streamlit web application tying all components together
- Sidebar: ChromaDB backend selector, OpenAI API key, model selector, n_docs slider, mission filter, RAGAS toggle
- Inline evaluation scores displayed under each response
- Batch evaluation runner loads `evaluation_dataset.txt` and displays results table + bar chart

---

## 4. Evaluation Dataset

File: `evaluation_dataset.txt`  
Contains **10 questions** spanning all required categories:

| # | Category | Mission |
|---|---|---|
| 1 | Overview | Apollo 11 |
| 2 | Technical | Apollo 13 |
| 3 | Emergency | Apollo 13 |
| 4 | Disaster Analysis | Challenger |
| 5 | Crew | Apollo 11 |
| 6 | Timeline | Apollo 11 |
| 7 | Emergency | Apollo 13 |
| 8 | Disaster Analysis | Challenger |
| 9 | Crew | Challenger |
| 10 | Technical | Apollo 11 |

---

## 5. RAGAS Metrics Explained

| Metric | Type | What it measures |
|---|---|---|
| **Response Relevancy** | LLM-based | Does the answer address the question? |
| **Faithfulness** | LLM-based | Is the answer grounded in retrieved context? |
| **BLEU Score** | Reference-based | N-gram precision of generated answer vs gold reference answer |
| **ROUGE Score** | Reference-based | Recall-based overlap of generated answer vs gold reference answer |

BLEU and ROUGE require a genuine reference (gold) answer to produce meaningful scores.
They are only computed during batch evaluation where `evaluation_dataset.txt` supplies
a `REFERENCE:` line for each question. In live chat mode (no reference available),
only Response Relevancy and Faithfulness are computed.

Scores range from 0.0 to 1.0. Green ≥ 0.8, Orange ≥ 0.6, Red < 0.6.

---

## 6. How to Run

### Step 1 — Install dependencies
```bash
pip install chromadb openai ragas langchain-openai streamlit pandas
```

### Step 2 — Run embedding pipeline
```bash
python embedding_pipeline.py --openai-key sk-... --data-path ./data --update-mode skip
```

### Step 3 — Launch chat app
```bash
streamlit run chat.py
```

### Step 4 — Run batch evaluation
In the Streamlit sidebar, click **"Run Batch Evaluation"** with `evaluation_dataset.txt` selected.

---

## 7. Design Decisions

- **Sentence-boundary chunking** preserves semantic coherence better than hard character splits
- **`temperature=0.2`** keeps LLM responses factual and close to retrieved context
- **Per-metric try/except** in RAGAS evaluator ensures one failing metric never crashes the UI
- **Mission metadata filter** allows users to scope queries to a single mission, reducing noise
- **`--update-mode replace`** enables clean re-processing when source documents are updated

