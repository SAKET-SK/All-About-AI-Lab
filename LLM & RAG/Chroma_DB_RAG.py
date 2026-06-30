"""
ChromaDB RAG System Exercise
"""

# TODO: Import necessary libraries
# Hint: You'll need chromadb, openai, pandas, time, json, typing, numpy, datetime, uuid, os, pathlib
import chromadb
from chromadb.config import Settings
import openai
from openai import OpenAI

# TODO: Add remaining imports here
import pandas as pd
import numpy as np
import time
import json
import os
import uuid
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional


# TODO: Define embedding configurations for different strategies
# Create configurations for OpenAI embeddings and local alternatives
EMBEDDING_CONFIGS = {
    "openai_embeddings": {
        # TODO: Set provider to "openai"
        "provider": "openai",
        # TODO: Choose OpenAI embedding model (hint: text-embedding-3-small is cost-effective)
        "model": "text-embedding-3-small",
        # TODO: Set dimensions (hint: 1536 for text-embedding-3-small)
        "dimensions": 1536,
        "description": "OpenAI embeddings with excellent semantic understanding"
    },
    "local_embeddings": {
        # TODO: Set provider to "sentence_transformers"
        "provider": "sentence_transformers",
        # TODO: Choose local model (hint: all-MiniLM-L6-v2 is lightweight)
        "model": "all-MiniLM-L6-v2",
        # TODO: Set dimensions (hint: 384 for all-MiniLM-L6-v2)
        "dimensions": 384,
        "description": "Local embeddings for cost-effective processing"
    }
}

# TODO: Define collection configurations for different document types
# Create configurations for technical docs, FAQ support, and knowledge base
COLLECTION_CONFIGS = {
    "tech_docs": {
        # TODO: Set collection name
        "name": "technical_documentation",
        # TODO: Define metadata fields for technical documentation
        "metadata_fields": ["source", "category", "difficulty", "last_updated"],
        "description": "Technical documentation with structured metadata"
    },
    "faq_support": {
        # TODO: Set collection name
        "name": "faq_customer_support",
        # TODO: Define metadata fields for FAQ support
        "metadata_fields": ["category", "priority", "department", "tags"],
        "description": "FAQ database for customer support automation"
    },
    "knowledge_base": {
        # TODO: Set collection name
        "name": "general_knowledge_base",
        # TODO: Define metadata fields for general knowledge
        "metadata_fields": ["source", "topic", "author", "date_added"],
        "description": "General knowledge base for information retrieval"
    }
}

# TODO: Create sample documents for testing
# Define realistic business documents with content and metadata
SAMPLE_DOCUMENTS = {
    "tech_docs": [
        {
            "id": "tech_001",
            # TODO: Add content about ChromaDB (200-300 words)
            "content": (
                "ChromaDB is an open-source embedding database designed to make it easy to build "
                "applications with large language models by giving them long-term memory and "
                "knowledge. It provides a simple, developer-friendly API for storing, indexing, "
                "and querying vector embeddings alongside their associated metadata and documents. "
                "ChromaDB supports persistent storage, allowing collections to be saved to disk and "
                "reloaded across sessions, which makes it well suited for production RAG pipelines. "
                "Under the hood, ChromaDB uses approximate nearest neighbor search to efficiently "
                "find the most semantically similar vectors to a given query embedding, even across "
                "millions of documents. Developers can create multiple collections, each with its "
                "own embedding function, and attach rich metadata to every document for filtering "
                "during search. ChromaDB integrates seamlessly with popular embedding providers such "
                "as OpenAI, Cohere, and Hugging Face sentence-transformers, as well as with LLM "
                "frameworks like LangChain and LlamaIndex. It can run fully in-memory for quick "
                "prototyping, as an embedded library within a Python application, or as a standalone "
                "client-server deployment for larger scale production workloads. Common use cases "
                "include semantic search, recommendation systems, question answering over private "
                "documents, and retrieval-augmented generation. Because it is open source and "
                "lightweight, ChromaDB has become a popular first choice for teams building their "
                "first RAG system before potentially scaling to larger vector databases."
            ),
            "metadata": {
                # TODO: Add appropriate metadata
                "source": "internal_wiki",
                "category": "vector_database",
                "difficulty": "intermediate",
                "last_updated": "2025-06-01"
            }
        },
        {
            "id": "tech_002",
            # TODO: Add content about RAG systems (200-300 words)
            "content": (
                "Retrieval-Augmented Generation (RAG) is an architecture that combines a retrieval "
                "system with a generative large language model to produce responses grounded in "
                "external, up-to-date, or proprietary information. Instead of relying solely on "
                "knowledge baked into a model's parameters during training, a RAG system first "
                "searches a knowledge base, typically stored as vector embeddings in a database like "
                "ChromaDB, for documents relevant to a user's query. These retrieved documents are "
                "then inserted into the prompt as context, allowing the language model to generate "
                "an answer that cites or reflects specific source material. This approach "
                "significantly reduces hallucination, since the model can ground its response in "
                "real text rather than guessing from memorized patterns. RAG also makes it possible "
                "to update a system's knowledge simply by adding new documents to the retrieval "
                "index, without needing to retrain or fine-tune the underlying model. A typical RAG "
                "pipeline involves four stages: chunking and embedding source documents, storing "
                "those embeddings in a vector database, performing similarity search against a query "
                "embedding at inference time, and finally constructing a prompt that combines the "
                "retrieved context with the user's question before passing it to the LLM. RAG "
                "systems are widely used for customer support bots, internal documentation search, "
                "legal and medical research assistants, and any application where accuracy and "
                "traceability to source material matter."
            ),
            "metadata": {
                # TODO: Add appropriate metadata
                "source": "internal_wiki",
                "category": "rag_architecture",
                "difficulty": "intermediate",
                "last_updated": "2025-06-05"
            }
        },
        {
            "id": "tech_003",
            # TODO: Add content about vector embeddings (200-300 words)
            "content": (
                "Vector embeddings are numerical representations of text, images, or other data "
                "that capture semantic meaning in a high-dimensional space. When text is converted "
                "into an embedding, similar concepts end up close together in that space, while "
                "unrelated concepts are far apart, even if they don't share any exact keywords. This "
                "property is what enables semantic search: instead of matching literal words, a "
                "system can find documents that mean something similar to a query. Embeddings are "
                "typically generated by neural network models trained on massive text corpora, such "
                "as OpenAI's text-embedding-3-small or open-source sentence-transformer models like "
                "all-MiniLM-L6-v2. The dimensionality of an embedding, for example 1536 dimensions "
                "for text-embedding-3-small or 384 for all-MiniLM-L6-v2, determines how much "
                "information can be encoded but also affects storage size and search speed. To "
                "compare embeddings, systems commonly use cosine similarity or Euclidean distance, "
                "which measure how close two vectors are in the embedding space. Vector databases "
                "like ChromaDB use specialized indexing structures, such as HNSW graphs, to perform "
                "approximate nearest neighbor search efficiently, even across millions of vectors. "
                "Choosing the right embedding model involves tradeoffs between accuracy, cost, "
                "latency, and dimensionality, and is one of the most important design decisions when "
                "building a retrieval-augmented generation system."
            ),
            "metadata": {
                # TODO: Add appropriate metadata
                "source": "internal_wiki",
                "category": "embeddings",
                "difficulty": "beginner",
                "last_updated": "2025-05-20"
            }
        }
    ],
    "faq_support": [
        {
            "id": "faq_001",
            # TODO: Add FAQ about password reset
            "content": (
                "How do I reset my password? To reset your password, go to the login page and click "
                "'Forgot Password'. Enter the email address associated with your account and click "
                "Submit. You will receive a password reset link via email within a few minutes. "
                "Click the link, choose a new password that is at least 8 characters long, and "
                "confirm it. If you don't receive the email, check your spam folder or contact "
                "support for further assistance."
            ),
            "metadata": {
                # TODO: Add appropriate metadata for customer support
                "category": "account_management",
                "priority": "high",
                "department": "technical_support",
                "tags": ["password", "login", "account_access"]
            }
        },
        {
            "id": "faq_002",
            # TODO: Add FAQ about business hours
            "content": (
                "What are your business hours? Our customer support team is available Monday "
                "through Friday from 9:00 AM to 6:00 PM Eastern Time, and Saturday from 10:00 AM "
                "to 2:00 PM Eastern Time. We are closed on Sundays and major holidays. For urgent "
                "issues outside of business hours, you can submit a support ticket through our help "
                "center and our team will respond as soon as we reopen."
            ),
            "metadata": {
                # TODO: Add appropriate metadata
                "category": "general_information",
                "priority": "low",
                "department": "customer_service",
                "tags": ["hours", "availability", "contact"]
            }
        },
        {
            "id": "faq_003",
            # TODO: Add FAQ about subscription upgrade
            "content": (
                "How do I upgrade my subscription plan? To upgrade your subscription, log in to "
                "your account and navigate to Settings > Billing > Subscription Plan. Select the "
                "plan you would like to upgrade to and click 'Upgrade Now'. Your new plan will take "
                "effect immediately, and you will be charged a prorated amount for the remainder of "
                "your current billing cycle. You can downgrade or cancel at any time from the same "
                "page."
            ),
            "metadata": {
                # TODO: Add appropriate metadata
                "category": "billing",
                "priority": "medium",
                "department": "billing_support",
                "tags": ["subscription", "upgrade", "billing"]
            }
        }
    ]
}


class ChromaDBRAGSystem:
    """
    A comprehensive RAG system implementation using ChromaDB for vector storage and retrieval.

    TODO: Complete this class to implement a production-ready RAG system with:
    - ChromaDB integration for vector storage
    - Embedding generation and management
    - Document ingestion and retrieval
    - RAG response generation
    """

    def __init__(self, embedding_config: str = "openai_embeddings", persist_directory: str = "./chroma_db"):
        """
        Initialize the ChromaDB RAG system with specified configuration.

        TODO: Complete this method to:
        1. Store configuration parameters
        2. Initialize ChromaDB client with persistent storage
        3. Initialize OpenAI client for embeddings and generation
        4. Set up collections dictionary
        5. Print initialization status

        Args:
            embedding_config (str): Configuration key for embedding strategy
            persist_directory (str): Directory for persistent storage
        """
        # TODO: Store embedding configuration
        self.embedding_config = EMBEDDING_CONFIGS[embedding_config]
        self.persist_directory = persist_directory

        # TODO: Initialize ChromaDB client with persistent storage
        # Hint: Use chromadb.PersistentClient with path and settings
        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )

        # TODO: Initialize OpenAI client for embeddings and generation
        # SECURITY NOTE: Use environment variables for API keys in production
        self.openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

        # TODO: Initialize collections dictionary
        self.collections = {}

        # TODO: Print initialization status
        print(f"🚀 ChromaDB RAG System initialized")

    def create_collection(self, collection_key: str):
        """
        Create a new ChromaDB collection with specified configuration.

        TODO: Complete this method to:
        1. Validate collection_key exists in COLLECTION_CONFIGS
        2. Get collection configuration
        3. Delete existing collection if it exists (for development)
        4. Create new collection with appropriate settings
        5. Store collection in self.collections
        6. Handle errors gracefully

        Args:
            collection_key (str): Key from COLLECTION_CONFIGS

        Returns:
            chromadb.Collection: The created collection object
        """
        # TODO: Validate collection_key
        if collection_key not in COLLECTION_CONFIGS:
            raise ValueError(f"Unknown collection configuration: {collection_key}")

        # TODO: Get configuration and create collection
        config = COLLECTION_CONFIGS[collection_key]
        collection_name = config["name"]

        print(f"\n📁 Creating collection: {collection_name}")

        try:
            # TODO: Delete existing collection if it exists
            existing = [c.name for c in self.client.list_collections()]
            if collection_name in existing:
                self.client.delete_collection(name=collection_name)

            # TODO: Create new collection
            collection = self.client.create_collection(
                name=collection_name,
                metadata={"description": config["description"]}
            )

            # TODO: Store in self.collections
            self.collections[collection_key] = collection

            # TODO: Print success message
            print(f"✅ Collection '{collection_name}' created successfully")
            return collection
        except Exception as e:
            print(f"❌ Error creating collection: {str(e)}")
            raise

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts using the configured embedding model.

        TODO: Complete this method to:
        1. Handle OpenAI embedding generation
        2. Support local embedding generation (optional)
        3. Include proper error handling
        4. Return list of embedding vectors

        Args:
            texts (List[str]): List of texts to embed

        Returns:
            List[List[float]]: List of embedding vectors
        """
        print(f"🔄 Generating embeddings for {len(texts)} texts...")

        try:
            if self.embedding_config["provider"] == "openai":
                # TODO: Use OpenAI embeddings API
                # Hint: Use self.openai_client.embeddings.create()
                response = self.openai_client.embeddings.create(
                    model=self.embedding_config["model"],
                    input=texts
                )
                embeddings = [item.embedding for item in response.data]
                return embeddings

            else:
                # TODO: Handle local embeddings (optional)
                print("⚠️  Local embeddings not implemented in this example")
                return []

        except Exception as e:
            print(f"❌ Error generating embeddings: {str(e)}")
            raise

    def add_documents(self, collection_key: str, documents: List[Dict]) -> None:
        """
        Add documents to a ChromaDB collection with embeddings and metadata.

        TODO: Complete this method to:
        1. Validate collection exists
        2. Extract texts, IDs, and metadata from documents
        3. Generate embeddings for texts
        4. Add documents to collection with embeddings
        5. Handle errors and provide status updates

        Args:
            collection_key (str): Key identifying the target collection
            documents (List[Dict]): List of document dictionaries with content and metadata
        """
        # TODO: Validate collection exists
        if collection_key not in self.collections:
            raise ValueError(f"Collection {collection_key} not found. Create it first.")

        # TODO: Get collection and extract document data
        collection = self.collections[collection_key]

        print(f"\n📄 Adding {len(documents)} documents to {collection.name}")

        # TODO: Extract texts, IDs, and metadata
        ids = [doc["id"] for doc in documents]
        texts = [doc["content"] for doc in documents]
        metadatas = [doc["metadata"] for doc in documents]

        # TODO: Generate embeddings
        embeddings = self.generate_embeddings(texts)

        # TODO: Add documents to collection
        collection.add(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas
        )

        # TODO: Print success status
        print(f"✅ Successfully added {len(documents)} documents to {collection.name}")

    def search_documents(self, collection_key: str, query: str, n_results: int = 3,
                          metadata_filter: Optional[Dict] = None) -> Dict:
        """
        Search for relevant documents using semantic similarity.

        TODO: Complete this method to:
        1. Validate collection exists
        2. Generate embedding for query
        3. Perform similarity search with optional metadata filtering
        4. Format and return results with similarity scores

        Args:
            collection_key (str): Key identifying the collection to search
            query (str): Search query text
            n_results (int): Number of results to return
            metadata_filter (Optional[Dict]): Metadata filters to apply

        Returns:
            Dict: Search results with documents, distances, and metadata
        """
        # TODO: Validate collection exists
        if collection_key not in self.collections:
            raise ValueError(f"Collection {collection_key} not found. Create it first.")

        collection = self.collections[collection_key]

        # TODO: Generate query embedding
        query_embedding = self.generate_embeddings([query])[0]

        # TODO: Perform similarity search
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=metadata_filter if metadata_filter else None
        )

        # TODO: Format and return results
        formatted_results = {
            "query": query,
            "documents": results["documents"][0] if results["documents"] else [],
            "metadatas": results["metadatas"][0] if results["metadatas"] else [],
            "distances": results["distances"][0] if results["distances"] else [],
            "ids": results["ids"][0] if results["ids"] else []
        }
        return formatted_results

    def generate_rag_response(self, collection_key: str, query: str, n_context: int = 3,
                               model: str = "gpt-4o-mini") -> Dict:
        """
        Generate a response using Retrieval-Augmented Generation.

        TODO: Complete this method to:
        1. Retrieve relevant context documents
        2. Prepare context for generation
        3. Create prompt with context
        4. Generate response using OpenAI
        5. Format comprehensive response with metadata

        Args:
            collection_key (str): Collection to search for context
            query (str): User query to answer
            n_context (int): Number of context documents to retrieve
            model (str): OpenAI model to use for generation

        Returns:
            Dict: RAG response with context, answer, and metadata
        """
        print(f"\n🤖 Generating RAG response")
        print(f"   Query: '{query}'")

        start_time = time.time()

        # TODO: Retrieve relevant context
        search_results = self.search_documents(collection_key, query, n_results=n_context)
        retrieval_time = time.time() - start_time

        # TODO: Prepare context for generation
        context_docs = search_results["documents"]
        context_text = "\n\n".join(
            [f"[Document {i+1}]\n{doc}" for i, doc in enumerate(context_docs)]
        )

        # TODO: Create prompt with context
        prompt = (
            f"You are a helpful assistant. Use the following context documents to answer "
            f"the user's question. If the answer is not contained in the context, say so.\n\n"
            f"Context:\n{context_text}\n\n"
            f"Question: {query}\n\n"
            f"Answer:"
        )

        # TODO: Generate response using OpenAI
        generation_start = time.time()
        completion = self.openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that answers questions based on provided context."},
                {"role": "user", "content": prompt}
            ]
        )
        generation_time = time.time() - generation_start
        answer = completion.choices[0].message.content

        # TODO: Format and return comprehensive response
        total_time = time.time() - start_time
        return {
            "question": query,
            "answer": answer,
            "context_sources": [
                {
                    "document": doc,
                    "metadata": meta,
                    "distance": dist
                }
                for doc, meta, dist in zip(
                    search_results["documents"],
                    search_results["metadatas"],
                    search_results["distances"]
                )
            ],
            "performance": {
                "retrieval_time_sec": round(retrieval_time, 3),
                "generation_time_sec": round(generation_time, 3),
                "total_time_sec": round(total_time, 3)
            },
            "model_used": model,
            "collection": collection_key
        }

    def display_rag_response(self, rag_response: Dict) -> None:
        """
        Display RAG response in a formatted, readable way.

        TODO: Complete this method to:
        1. Display question and answer clearly
        2. Show context sources with similarity scores
        3. Display performance metrics
        4. Format output for readability

        Args:
            rag_response (Dict): RAG response dictionary from generate_rag_response
        """
        # TODO: Format and display RAG response
        # Include: question, answer, context sources, performance metrics
        print("\n" + "=" * 60)
        print(f"❓ Question: {rag_response['question']}")
        print("-" * 60)
        print(f"💡 Answer:\n{rag_response['answer']}")
        print("-" * 60)
        print("📚 Context Sources:")
        for i, source in enumerate(rag_response["context_sources"], 1):
            print(f"  [{i}] Distance: {source['distance']:.4f}")
            print(f"      Metadata: {source['metadata']}")
            preview = source["document"][:150].replace("\n", " ")
            print(f"      Preview: {preview}...")
        print("-" * 60)
        perf = rag_response["performance"]
        print(
            f"⏱️  Retrieval: {perf['retrieval_time_sec']}s | "
            f"Generation: {perf['generation_time_sec']}s | "
            f"Total: {perf['total_time_sec']}s"
        )
        print("=" * 60)


def demonstrate_chromadb_rag():
    """
    Comprehensive demonstration of ChromaDB RAG system capabilities.

    TODO: Complete this function to:
    1. Initialize the RAG system
    2. Create collections for different document types
    3. Add sample documents to collections
    4. Test various query types
    5. Display results and performance metrics
    """
    print("🚀 ChromaDB RAG System Demonstration")
    print("=" * 60)

    # TODO: Initialize the RAG system
    rag_system = ChromaDBRAGSystem()

    # TODO: Create collections
    rag_system.create_collection("tech_docs")
    rag_system.create_collection("faq_support")

    # TODO: Add sample documents
    rag_system.add_documents("tech_docs", SAMPLE_DOCUMENTS["tech_docs"])
    rag_system.add_documents("faq_support", SAMPLE_DOCUMENTS["faq_support"])

    # TODO: Test various queries
    test_queries = [
        ("tech_docs", "What is ChromaDB used for?"),
        ("tech_docs", "How do vector embeddings work?"),
        ("faq_support", "How can I reset my password?"),
    ]

    # TODO: Display results
    for collection_key, query in test_queries:
        response = rag_system.generate_rag_response(collection_key, query)
        rag_system.display_rag_response(response)


# TODO: Example usage - uncomment and test when ready
# Run the comprehensive demonstration
# demonstrate_chromadb_rag()

# TODO: Additional examples you can implement:

# Example 1: Custom metadata filtering
# rag_system = ChromaDBRAGSystem()
# rag_system.create_collection("tech_docs")
# rag_system.add_documents("tech_docs", SAMPLE_DOCUMENTS["tech_docs"])
# filtered_results = rag_system.search_documents(
#     "tech_docs",
#     "database information",
#     metadata_filter={"category": "Database"}
# )
#
# Example 2: Batch processing multiple queries
# queries = ["What is RAG?", "How do embeddings work?", "ChromaDB features"]
# for query in queries:
#     response = rag_system.generate_rag_response("tech_docs", query)
#     rag_system.display_rag_response(response)

"""
EXERCISE COMPLETION CHECKLIST:
☑ Import all necessary libraries
☑ Complete EMBEDDING_CONFIGS with appropriate models and parameters
☑ Fill in COLLECTION_CONFIGS with meaningful names and metadata fields
☑ Create comprehensive SAMPLE_DOCUMENTS with realistic content
☑ Implement ChromaDBRAGSystem.__init__() with proper initialization
☑ Complete create_collection() with ChromaDB collection creation
☑ Implement generate_embeddings() with OpenAI API integration
☑ Complete add_documents() with embedding generation and storage
☑ Implement search_documents() with similarity search and filtering
☑ Complete generate_rag_response() with full RAG pipeline
☑ Implement display_rag_response() with formatted output
☑ Complete demonstrate_chromadb_rag() with comprehensive testing
☐ Test your implementation with the example usage
☐ Add your own API key and test the complete workflow

BONUS CHALLENGES:
☐ Add support for local embedding models using sentence-transformers
☐ Implement batch processing for large document collections
☐ Add metadata-based filtering and advanced search capabilities
☐ Create a web interface for the RAG system using Flask or FastAPI
☐ Implement document update and deletion functionality
☐ Add support for different file formats (PDF, Word, etc.)
☐ Create performance monitoring and analytics dashboard
☐ Implement user authentication and access control
☐ Add support for multi-modal documents (text + images)
☐ Create automated document ingestion from external sources
"""
