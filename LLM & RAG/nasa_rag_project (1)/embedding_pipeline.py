#!/usr/bin/env python3
"""
ChromaDB Embedding Pipeline for NASA Space Mission Data - Text Files Only

This script reads parsed text data from various NASA space mission folders and creates
a permanent ChromaDB collection with OpenAI embeddings for RAG applications.
Optimized to process only text files to avoid duplication with JSON versions.

Supported data sources:
- Apollo 11 extracted data (text files only)
- Apollo 13 extracted data (text files only)
- Apollo 11 Textract extracted data (text files only)
- Challenger transcribed audio data (text files only)
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import chromadb
from chromadb.config import Settings
import openai
from openai import OpenAI
import hashlib
import time
from datetime import datetime
import argparse
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('chroma_embedding_text_only.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ChromaEmbeddingPipelineTextOnly:
    """Pipeline for creating ChromaDB collections with OpenAI embeddings - Text files only"""

    def __init__(self,
                 openai_api_key: str,
                 chroma_persist_directory: str = "./chroma_db",
                 collection_name: str = "nasa_space_missions_text",
                 embedding_model: str = "text-embedding-3-small",
                 chunk_size: int = 1000,
                 chunk_overlap: int = 200):
        """
        Initialize the embedding pipeline

        Args:
            openai_api_key: OpenAI API key
            chroma_persist_directory: Directory to persist ChromaDB
            collection_name: Name of the ChromaDB collection
            embedding_model: OpenAI embedding model to use
            chunk_size: Maximum size of text chunks  (CLI: --chunk-size)
            chunk_overlap: Overlap between chunks    (CLI: --chunk-overlap)
        """
        # TODO: Initialize OpenAI client
        self.openai_client = OpenAI(api_key=openai_api_key)

        # TODO: Store configuration parameters
        self.embedding_model = embedding_model
        self.chunk_size = chunk_size          # configurable at runtime via CLI
        self.chunk_overlap = chunk_overlap    # configurable at runtime via CLI
        self.collection_name = collection_name

        # TODO: Initialize ChromaDB client  (--chroma-dir CLI flag)
        self.chroma_client = chromadb.PersistentClient(
            path=chroma_persist_directory,
            settings=Settings(anonymized_telemetry=False),
        )

        # TODO: Create or get collection with OpenAI embedding function
        embedding_fn = OpenAIEmbeddingFunction(
            api_key=openai_api_key,
            model_name=embedding_model,
        )
        self.collection = self.chroma_client.get_or_create_collection(
            name=collection_name,
            embedding_function=embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            f"Collection '{collection_name}' ready — "
            f"{self.collection.count()} documents already stored."
        )

    # ------------------------------------------------------------------
    # Chunking
    # ------------------------------------------------------------------

    def chunk_text(self, text: str, metadata: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
        """
        Split text into chunks with overlap.
        Invariants enforced:
          - Every emitted chunk is <= self.chunk_size characters (no strip() after sizing).
          - Overlap is exactly self.chunk_overlap characters taken from the END of the
            previously stored chunk boundary (not from end of a trimmed string).
          - Every iteration advances start strictly forward, preventing infinite loops.
          - 0 <= chunk_overlap < chunk_size is asserted on entry.
        """
        # Guard: enforce invariant on parameters
        assert 0 <= self.chunk_overlap < self.chunk_size, (
            f"chunk_overlap ({self.chunk_overlap}) must be >= 0 and < chunk_size ({self.chunk_size})"
        )

        # TODO: Handle short texts that don't need chunking
        if not text or not text.strip():
            return []

        if len(text) <= self.chunk_size:
            chunk_meta = {**metadata, "chunk_index": 0, "total_chunks": 1}
            return [(text, chunk_meta)]

        # TODO: Implement chunking logic with overlap
        chunks: List[Tuple[str, Dict[str, Any]]] = []
        start = 0

        while start < len(text):
            end = start + self.chunk_size

            if end >= len(text):
                # Last chunk — take everything remaining, no boundary search needed
                chunk_end = len(text)
            else:
                # TODO: Try to break at sentence boundaries
                # Only accept a boundary that guarantees forward progress:
                # it must be strictly greater than (start + chunk_overlap) so the
                # next start = chunk_end - chunk_overlap is always > current start.
                min_boundary = start + self.chunk_overlap + 1
                boundary = -1
                for punct in (". ", ".\n", "! ", "?\n", "? ", "!\n"):
                    pos = text.rfind(punct, min_boundary, end)
                    if pos != -1:
                        candidate = pos + len(punct)
                        if candidate > boundary:
                            boundary = candidate

                if boundary != -1:
                    chunk_end = boundary          # sentence boundary found — progress guaranteed
                else:
                    chunk_end = end               # hard character boundary fallback

            # Emit the raw slice — NO strip() so overlap length is exact
            chunk = text[start:chunk_end]

            if chunk:
                # TODO: Create metadata for each chunk
                chunk_meta = {
                    **metadata,
                    "chunk_index": len(chunks),
                }
                chunks.append((chunk, chunk_meta))

            if chunk_end >= len(text):
                break

            # TODO: Apply chunk_overlap consistently between consecutive chunks
            # Next start is calculated from the STORED chunk_end, not a trimmed string,
            # so overlap is always exactly self.chunk_overlap characters.
            new_start = chunk_end - self.chunk_overlap

            # Safety: guarantee strict forward progress even if logic above slips
            if new_start <= start:
                new_start = start + 1

            start = new_start

        # Back-fill total_chunks now that we know the count
        total = len(chunks)
        chunks = [(c, {**m, "total_chunks": total}) for c, m in chunks]

        return chunks

    # ------------------------------------------------------------------
    # Document existence / update helpers
    # ------------------------------------------------------------------

    def check_document_exists(self, doc_id: str) -> bool:
        """
        Check if a document with the given ID already exists in the collection.

        Args:
            doc_id: Document ID to check

        Returns:
            True if document exists, False otherwise
        """
        # TODO: Query collection for document ID
        result = self.collection.get(ids=[doc_id])
        # TODO: Return True if exists, False otherwise
        return len(result["ids"]) > 0

    def update_document(self, doc_id: str, text: str, metadata: Dict[str, Any]) -> bool:
        """Update an existing document in the collection."""
        try:
            embedding = self.get_embedding(text)
            self.collection.update(
                ids=[doc_id],
                documents=[text],
                metadatas=[metadata],
                embeddings=[embedding],
            )
            logger.debug(f"Updated document: {doc_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating document {doc_id}: {e}")
            return False

    def delete_documents_by_source(self, source_pattern: str) -> int:
        """Delete all documents from a specific source."""
        try:
            all_docs = self.collection.get()
            ids_to_delete = [
                all_docs["ids"][i]
                for i, meta in enumerate(all_docs["metadatas"])
                if source_pattern in meta.get("source", "")
            ]
            if ids_to_delete:
                self.collection.delete(ids=ids_to_delete)
                logger.info(f"Deleted {len(ids_to_delete)} documents matching: {source_pattern}")
                return len(ids_to_delete)
            logger.info(f"No documents found matching: {source_pattern}")
            return 0
        except Exception as e:
            logger.error(f"Error deleting documents by source: {e}")
            return 0

    def get_file_documents(self, file_path: Path) -> List[str]:
        """Get all document IDs for a specific file."""
        try:
            source = file_path.stem
            mission = self.extract_mission_from_path(file_path)
            all_docs = self.collection.get()
            return [
                all_docs["ids"][i]
                for i, meta in enumerate(all_docs["metadatas"])
                if meta.get("source") == source and meta.get("mission") == mission
            ]
        except Exception as e:
            logger.error(f"Error getting file documents: {e}")
            return []

    # ------------------------------------------------------------------
    # Embedding
    # ------------------------------------------------------------------

    def get_embedding(self, text: str) -> List[float]:
        """
        Get OpenAI embedding for text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as list of floats
        """
        try:
            # TODO: Call OpenAI embeddings API
            response = self.openai_client.embeddings.create(
                input=text,
                model=self.embedding_model,
            )
            # TODO: Return embedding vector
            return response.data[0].embedding

        except Exception as e:
            # TODO: Error handling
            logger.error(f"Error generating embedding: {e}")
            raise

    # ------------------------------------------------------------------
    # ID generation
    # ------------------------------------------------------------------

    def generate_document_id(self, file_path: Path, metadata: Dict[str, Any]) -> str:
        """
        Generate a stable document ID based on file path and chunk position.

        TODO: Create consistent ID format
        TODO: Use mission, source, and chunk_index
        Format: mission_source_chunk_0001
        """
        mission = metadata.get("mission", "unknown")
        source = metadata.get("source", file_path.stem)
        chunk_index = metadata.get("chunk_index", 0)
        # Sanitise so the ID stays filesystem / ChromaDB safe
        safe_source = source.replace(" ", "_").replace("/", "-")
        return f"{mission}__{safe_source}__chunk_{chunk_index:04d}"

    # ------------------------------------------------------------------
    # File processing
    # ------------------------------------------------------------------

    def process_text_file(self, file_path: Path) -> List[Tuple[str, Dict[str, Any]]]:
        """Process a plain text file with enhanced metadata extraction."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            if not content.strip():
                return []

            metadata = {
                "source": file_path.stem,
                "file_path": str(file_path),
                "file_type": "text",
                "content_type": "full_text",
                "mission": self.extract_mission_from_path(file_path),
                "data_type": self.extract_data_type_from_path(file_path),
                "document_category": self.extract_document_category_from_filename(file_path.name),
                "file_size": len(content),
                "processed_timestamp": datetime.now().isoformat(),
            }

            return self.chunk_text(content, metadata)

        except Exception as e:
            logger.error(f"Error processing text file {file_path}: {e}")
            return []

    def extract_mission_from_path(self, file_path: Path) -> str:
        path_str = str(file_path).lower()
        if "apollo11" in path_str or "apollo_11" in path_str:
            return "Apollo 11"
        elif "apollo13" in path_str or "apollo_13" in path_str:
            return "Apollo 13"
        elif "challenger" in path_str:
            return "Challenger"
        return "unknown"

    def extract_data_type_from_path(self, file_path: Path) -> str:
        path_str = str(file_path).lower()
        if "transcript" in path_str:
            return "transcript"
        elif "textract" in path_str:
            return "textract_extracted"
        elif "audio" in path_str:
            return "audio_transcript"
        elif "flight_plan" in path_str:
            return "flight_plan"
        return "document"

    def extract_document_category_from_filename(self, filename: str) -> str:
        fn = filename.lower()
        if "pao" in fn:
            return "public_affairs_officer"
        elif "cm" in fn:
            return "command_module"
        elif "tec" in fn:
            return "technical"
        elif "flight_plan" in fn:
            return "flight_plan"
        elif "mission_audio" in fn:
            return "mission_audio"
        elif "ntrs" in fn:
            return "nasa_archive"
        elif "19900066485" in fn:
            return "technical_report"
        elif "19710015566" in fn:
            return "mission_report"
        elif "full_text" in fn:
            return "complete_document"
        return "general_document"

    def scan_text_files_only(self, base_path: str) -> List[Path]:
        """Scan data directories for .txt files only."""
        base_path = Path(base_path)
        files_to_process: List[Path] = []

        for data_dir in ("apollo11", "apollo13", "challenger"):
            dir_path = base_path / data_dir
            if dir_path.exists():
                text_files = list(dir_path.glob("**/*.txt"))
                files_to_process.extend(text_files)
                logger.info(f"Found {len(text_files)} text files in {data_dir}")

        filtered = [
            f for f in files_to_process
            if not f.name.startswith(".")
            and "summary" not in f.name.lower()
            and f.suffix.lower() == ".txt"
        ]

        logger.info(f"Total text files to process: {len(filtered)}")
        mission_counts: Dict[str, int] = {}
        for fp in filtered:
            m = self.extract_mission_from_path(fp)
            mission_counts[m] = mission_counts.get(m, 0) + 1
        for m, c in mission_counts.items():
            logger.info(f"  {m}: {c} files")

        return filtered

    # ------------------------------------------------------------------
    # Batch add / update
    # ------------------------------------------------------------------

    def add_documents_to_collection(
        self,
        documents: List[Tuple[str, Dict[str, Any]]],
        file_path: Path,
        batch_size: int = 50,
        update_mode: str = "skip",
    ) -> Dict[str, int]:
        """
        Add documents to ChromaDB collection in batches with update handling.

        update_mode options (--update-mode CLI flag):
            'skip'    – skip chunks that already exist   (default)
            'update'  – call collection.update() for existing chunks
            'replace' – delete ALL existing chunks from this file, then re-add
        """
        if not documents:
            return {"added": 0, "updated": 0, "skipped": 0}

        stats = {"added": 0, "updated": 0, "skipped": 0}

        # TODO: Handle 'replace' mode — wipe existing chunks for this file first
        if update_mode == "replace":
            existing_ids = self.get_file_documents(file_path)
            if existing_ids:
                self.collection.delete(ids=existing_ids)
                logger.info(f"Replaced {len(existing_ids)} existing chunks for {file_path.name}")

        # TODO: Process documents in batches
        for batch_start in range(0, len(documents), batch_size):
            batch = documents[batch_start: batch_start + batch_size]

            ids_to_add: List[str] = []
            texts_to_add: List[str] = []
            metas_to_add: List[Dict] = []
            embeddings_to_add: List[List[float]] = []

            for text, metadata in batch:
                # TODO: Generate document ID
                doc_id = self.generate_document_id(file_path, metadata)

                # TODO: Check if exists
                exists = self.check_document_exists(doc_id)

                if exists:
                    if update_mode == "update":
                        # TODO: Update existing document
                        success = self.update_document(doc_id, text, metadata)
                        if success:
                            stats["updated"] += 1
                    else:
                        # skip mode (or replace already wiped them above)
                        stats["skipped"] += 1
                    continue

                # New document — collect for batch add
                try:
                    # TODO: Get embedding via OpenAI API
                    embedding = self.get_embedding(text)
                    ids_to_add.append(doc_id)
                    texts_to_add.append(text)
                    metas_to_add.append(metadata)
                    embeddings_to_add.append(embedding)
                except Exception as e:
                    logger.error(f"Embedding error for {doc_id}: {e}")

            # TODO: Add batch to ChromaDB collection
            if ids_to_add:
                try:
                    self.collection.add(
                        ids=ids_to_add,
                        documents=texts_to_add,
                        metadatas=metas_to_add,
                        embeddings=embeddings_to_add,
                    )
                    stats["added"] += len(ids_to_add)
                    logger.debug(f"Added batch of {len(ids_to_add)} documents.")
                except Exception as e:
                    logger.error(f"Error adding batch to collection: {e}")

        # TODO: Return statistics
        return stats

    # ------------------------------------------------------------------
    # Orchestrator
    # ------------------------------------------------------------------

    def process_all_text_data(self, base_path: str, update_mode: str = "skip") -> Dict[str, Any]:
        """Process all text files and add to ChromaDB."""
        stats: Dict[str, Any] = {
            "files_processed": 0,
            "documents_added": 0,
            "documents_updated": 0,
            "documents_skipped": 0,
            "errors": 0,
            "total_chunks": 0,
            "missions": {},
        }

        # TODO: Get files to process
        files = self.scan_text_files_only(base_path)

        # TODO: Loop through each file
        for file_path in files:
            try:
                mission = self.extract_mission_from_path(file_path)

                # TODO: Process file into chunks
                documents = self.process_text_file(file_path)
                if not documents:
                    logger.warning(f"No content extracted from {file_path}")
                    continue

                # TODO: Add to collection with update mode
                file_stats = self.add_documents_to_collection(
                    documents, file_path, update_mode=update_mode
                )

                # TODO: Update statistics
                stats["files_processed"] += 1
                stats["total_chunks"] += len(documents)
                stats["documents_added"] += file_stats["added"]
                stats["documents_updated"] += file_stats["updated"]
                stats["documents_skipped"] += file_stats["skipped"]

                # Mission-level breakdown
                if mission not in stats["missions"]:
                    stats["missions"][mission] = {
                        "files": 0, "chunks": 0,
                        "added": 0, "updated": 0, "skipped": 0,
                    }
                stats["missions"][mission]["files"] += 1
                stats["missions"][mission]["chunks"] += len(documents)
                stats["missions"][mission]["added"] += file_stats["added"]
                stats["missions"][mission]["updated"] += file_stats["updated"]
                stats["missions"][mission]["skipped"] += file_stats["skipped"]

                logger.info(
                    f"[{mission}] {file_path.name}: "
                    f"{len(documents)} chunks | "
                    f"added={file_stats['added']} "
                    f"updated={file_stats['updated']} "
                    f"skipped={file_stats['skipped']}"
                )

            # TODO: Handle errors gracefully
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                stats["errors"] += 1

        return stats

    # ------------------------------------------------------------------
    # Info / query helpers
    # ------------------------------------------------------------------

    def get_collection_info(self) -> Dict[str, Any]:
        """Get information about the ChromaDB collection."""
        # TODO: Return collection name, document count, metadata
        return {
            "collection_name": self.collection_name,
            "document_count": self.collection.count(),
            "embedding_model": self.embedding_model,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
        }

    def query_collection(self, query_text: str, n_results: int = 5) -> Dict[str, Any]:
        """Perform a test query and return results."""
        # TODO: Perform test query and return results
        return self.collection.query(
            query_texts=[query_text],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )

    def get_collection_stats(self) -> Dict[str, Any]:
        """Get detailed statistics about the collection (used by --stats-only)."""
        try:
            all_docs = self.collection.get()

            if not all_docs["metadatas"]:
                return {"error": "No documents in collection"}

            stats: Dict[str, Any] = {
                "total_documents": len(all_docs["metadatas"]),
                "missions": {},
                "data_types": {},
                "document_categories": {},
                "file_types": {},
            }

            for meta in all_docs["metadatas"]:
                for key, field in (
                    ("missions", "mission"),
                    ("data_types", "data_type"),
                    ("document_categories", "document_category"),
                    ("file_types", "file_type"),
                ):
                    val = meta.get(field, "unknown")
                    stats[key][val] = stats[key].get(val, 0) + 1

            return stats

        except Exception as e:
            logger.error(f"Error getting collection stats: {e}")
            return {"error": str(e)}


# ──────────────────────────────────────────────────────────────────────────────
# CLI entry-point
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ChromaDB Embedding Pipeline for NASA Data")
    parser.add_argument("--data-path", default=".", help="Path to data directories")
    parser.add_argument("--openai-key", required=True, help="OpenAI API key")
    parser.add_argument("--chroma-dir", default="./chroma_db_openai", help="ChromaDB persist directory")
    parser.add_argument("--collection-name", default="nasa_space_missions_text", help="Collection name")
    parser.add_argument("--embedding-model", default="text-embedding-3-small", help="OpenAI embedding model")
    parser.add_argument("--chunk-size", type=int, default=500, help="Text chunk size (characters)")
    parser.add_argument("--chunk-overlap", type=int, default=100, help="Chunk overlap size (characters)")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size for processing")
    parser.add_argument(
        "--update-mode",
        choices=["skip", "update", "replace"],
        default="skip",
        help="How to handle existing documents: skip | update | replace",
    )
    parser.add_argument("--test-query", help="Test query after processing")
    parser.add_argument("--stats-only", action="store_true", help="Only show collection statistics")
    parser.add_argument("--delete-source", help="Delete all documents from a specific source pattern")

    args = parser.parse_args()

    logger.info("Initializing ChromaDB Embedding Pipeline…")
    pipeline = ChromaEmbeddingPipelineTextOnly(
        openai_api_key=args.openai_key,
        chroma_persist_directory=args.chroma_dir,
        collection_name=args.collection_name,
        embedding_model=args.embedding_model,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )

    if args.delete_source:
        deleted = pipeline.delete_documents_by_source(args.delete_source)
        logger.info(f"Deleted {deleted} documents matching: {args.delete_source}")
        return

    # --stats-only: print collection size + per-mission aggregate then exit
    if args.stats_only:
        logger.info("=== Collection Statistics ===")
        stats = pipeline.get_collection_stats()
        logger.info(f"Total documents/chunks : {stats.get('total_documents', 'N/A')}")
        logger.info(f"By mission             : {stats.get('missions', {})}")
        logger.info(f"By data type           : {stats.get('data_types', {})}")
        logger.info(f"By document category   : {stats.get('document_categories', {})}")
        return

    logger.info(f"Starting text data processing — update-mode: {args.update_mode}")
    start_time = time.time()

    stats = pipeline.process_all_text_data(args.data_path, update_mode=args.update_mode)

    elapsed = time.time() - start_time
    logger.info("=" * 60)
    logger.info("PROCESSING COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Files processed        : {stats['files_processed']}")
    logger.info(f"Total chunks created   : {stats['total_chunks']}")
    logger.info(f"Documents added        : {stats['documents_added']}")
    logger.info(f"Documents updated      : {stats['documents_updated']}")
    logger.info(f"Documents skipped      : {stats['documents_skipped']}")
    logger.info(f"Errors                 : {stats['errors']}")
    logger.info(f"Processing time        : {elapsed:.2f}s")

    logger.info("\nMission breakdown:")
    for mission, ms in stats["missions"].items():
        logger.info(
            f"  {mission}: {ms['files']} files, {ms['chunks']} chunks "
            f"(added={ms['added']} updated={ms['updated']} skipped={ms['skipped']})"
        )

    info = pipeline.get_collection_info()
    logger.info(f"\nCollection             : {info['collection_name']}")
    logger.info(f"Total docs in ChromaDB : {info['document_count']}")

    if args.test_query:
        logger.info(f"\nTest query: '{args.test_query}'")
        results = pipeline.query_collection(args.test_query)
        if results and "documents" in results:
            for i, doc in enumerate(results["documents"][0][:3]):
                logger.info(f"  Result {i+1}: {doc[:200]}…")

    logger.info("Pipeline completed successfully!")


if __name__ == "__main__":
    main()
