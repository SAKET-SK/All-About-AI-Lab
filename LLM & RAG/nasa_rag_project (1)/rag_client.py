import chromadb
import os
from chromadb.config import Settings
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from typing import Dict, List, Optional
from pathlib import Path


def discover_chroma_backends() -> Dict[str, Dict[str, str]]:
    """Discover available ChromaDB backends in the project directory"""
    backends = {}
    current_dir = Path(".")

    # TODO: Create list of directories that match specific criteria
    # (directory type and name pattern — any folder containing "chroma" in its name)
    chroma_dirs = [
        d for d in current_dir.iterdir()
        if d.is_dir() and "chroma" in d.name.lower()
    ]

    # TODO: Loop through each discovered directory
    for chroma_dir in chroma_dirs:

        # TODO: Wrap connection attempt in try-except block for error handling
        try:
            # TODO: Initialize database client with directory path and configuration settings
            client = chromadb.PersistentClient(
                path=str(chroma_dir),
                settings=Settings(anonymized_telemetry=False),
            )

            # TODO: Retrieve list of available collections from the database
            collections = client.list_collections()

            # TODO: Loop through each collection found
            for collection in collections:

                # TODO: Create unique identifier key combining directory and collection names
                key = f"{chroma_dir.name}/{collection.name}"

                # TODO: Get document count with fallback for unsupported operations
                try:
                    doc_count = collection.count()
                except Exception:
                    doc_count = "unknown"

                # TODO: Build information dictionary containing all required fields
                backends[key] = {
                    # TODO: Store directory path as string
                    "directory": str(chroma_dir),
                    # TODO: Store collection name
                    "collection_name": collection.name,
                    # TODO: Create user-friendly display name
                    "display_name": f"{chroma_dir.name} › {collection.name} ({doc_count} chunks)",
                }

        # TODO: Handle connection or access errors gracefully
        except Exception as e:
            # TODO: Create fallback entry for inaccessible directories
            key = chroma_dir.name
            backends[key] = {
                # TODO: Include error information in display name with truncation
                "display_name": f"{chroma_dir.name} (error: {str(e)[:40]})",
                # TODO: Set appropriate fallback values for missing information
                "directory": str(chroma_dir),
                "collection_name": "",
            }

    # TODO: Return complete backends dictionary with all discovered collections
    return backends


def initialize_rag_system(chroma_dir: str, collection_name: str,
                          embedding_model: str = "text-embedding-3-small"):
    """
    Initialize the RAG system with specified backend.

    IMPORTANT: the collection MUST be reopened with the same OpenAIEmbeddingFunction
    and embedding model that was used during ingestion in embedding_pipeline.py.
    Without this, ChromaDB falls back to its default embedding model and produces
    vectors that are incompatible with the stored OpenAI vectors, breaking retrieval.
    """
    try:
        # TODO: Create a chromadb PersistentClient
        client = chromadb.PersistentClient(
            path=chroma_dir,
            settings=Settings(anonymized_telemetry=False),
        )

        # Supply the same embedding function used at ingestion time so that
        # query_texts=[query] is vectorised with the correct model.
        api_key = os.environ.get("CHROMA_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
        embedding_fn = OpenAIEmbeddingFunction(
            api_key=api_key,
            model_name=embedding_model,
        )

        # TODO: Return the collection with the collection_name
        collection = client.get_collection(
            name=collection_name,
            embedding_function=embedding_fn,
        )
        return collection, True, None

    except Exception as e:
        return None, False, str(e)


def retrieve_documents(
    collection,
    query: str,
    n_results: int = 3,
    mission_filter: Optional[str] = None,
) -> Optional[Dict]:
    """Retrieve relevant documents from ChromaDB with optional filtering"""

    # TODO: Initialize filter variable to None (represents no filtering)
    where_filter = None

    # TODO: Check if filter parameter exists and is not set to "all" or equivalent
    if mission_filter and mission_filter.lower() not in ("all", "all missions", ""):

        # TODO: If filter conditions are met, create filter dictionary
        # ChromaDB metadata filter format: {"field": {"$eq": "value"}}
        where_filter = {"mission": {"$eq": mission_filter}}

    # TODO: Execute database query with the following parameters
    results = collection.query(
        # TODO: Pass search query in the required format
        query_texts=[query],
        # TODO: Set maximum number of results to return
        n_results=n_results,
        # TODO: Apply conditional filter (None for no filtering, dict for specific filtering)
        where=where_filter,
        include=["documents", "metadatas", "distances"],
    )

    # TODO: Return query results to caller
    return results


def format_context(documents: List[str], metadatas: List[Dict]) -> str:
    """Format retrieved documents into a clean, attributed context string"""
    if not documents:
        return ""

    # TODO: Initialize list with header text for context section
    context_parts = ["=== RETRIEVED CONTEXT ===\n"]

    # Deduplicate by content while preserving best (lowest distance) order
    seen_contents = set()
    deduped = []
    for doc, meta in zip(documents, metadatas):
        normalized = doc.strip()
        if normalized not in seen_contents:
            seen_contents.add(normalized)
            deduped.append((doc, meta))

    # TODO: Loop through paired documents and their metadata using enumeration
    for idx, (doc, meta) in enumerate(deduped, start=1):

        # TODO: Extract mission information from metadata with fallback value
        mission = meta.get("mission", "Unknown Mission")
        # TODO: Clean up mission name formatting (replace underscores, capitalize)
        mission = mission.replace("_", " ").title()

        # TODO: Extract source information from metadata with fallback value
        source = meta.get("source", meta.get("filepath", "Unknown Source"))
        # Keep only the filename portion for readability
        source = Path(source).name if source != "Unknown Source" else source

        # TODO: Extract category information from metadata with fallback value
        category = meta.get("category", "general")
        # TODO: Clean up category name formatting (replace underscores, capitalize)
        category = category.replace("_", " ").title()

        # TODO: Create formatted source header with index number and extracted information
        header = (
            f"--- Source {idx} | Mission: {mission} | "
            f"File: {source} | Category: {category} ---"
        )
        # TODO: Add source header to context parts list
        context_parts.append(header)

        # TODO: Check document length and truncate if necessary (max 800 chars per chunk)
        max_chunk_len = 800
        content = doc.strip()
        if len(content) > max_chunk_len:
            content = content[:max_chunk_len] + "… [truncated]"

        # TODO: Add truncated or full document content to context parts list
        context_parts.append(content)
        context_parts.append("")  # blank line between sources

    context_parts.append("=== END OF CONTEXT ===")

    # TODO: Join all context parts with newlines and return formatted string
    return "\n".join(context_parts)
