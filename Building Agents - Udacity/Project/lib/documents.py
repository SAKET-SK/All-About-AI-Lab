from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import uuid
from collections.abc import MutableSequence


@dataclass
class Document:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = field(default_factory=str)
    metadata: Dict[str, Any] = None

class Corpus(MutableSequence):
    def __init__(self, documents: Optional[List[Document]] = None):
        self._documents = documents or []

    def __getitem__(self, index):
        return self._documents[index]

    def __setitem__(self, index, value: Document):
        if not isinstance(value, Document):
            raise TypeError("Collection only supports Document items")
        self._documents[index] = value

    def __delitem__(self, index):
        del self._documents[index]

    def __len__(self):
        return len(self._documents)

    def insert(self, index, value: Document):
        if not isinstance(value, Document):
            raise TypeError("Collection only supports Document items")
        self._documents.insert(index, value)

    def to_dict(self) -> Dict[str, List[Any]]:
        """
        Convert the corpus to a dictionary format suitable for batch operations.
        
        This method extracts all document contents, metadata, and IDs into
        separate lists, which is the format typically expected by vector
        databases and other batch processing systems. This allows for efficient
        bulk operations on the entire corpus.
        
        Returns:
            Dict[str, List[Any]]: Dictionary containing:
                - 'contents': List of all document content strings
                - 'metadatas': List of all document metadata dictionaries
                - 'ids': List of all document ID strings
                
        Example:
            >>> corpus = Corpus([doc1, doc2])
            >>> batch_data = corpus.to_dict()
            >>> chroma_collection.add(
            ...     documents=batch_data['contents'],
            ...     metadatas=batch_data['metadatas'],
            ...     ids=batch_data['ids']
            ... )
        """
        
        # Use zip with unpacking to efficiently extract all fields
        # Handle empty corpus case by providing empty defaults
        contents, metadatas, ids = zip(*(
            (doc.content, doc.metadata, doc.id) for doc in self._documents
        )) if self._documents else ([], [], [])

        return {
            'contents': list(contents),
            'metadatas': list(metadatas),
            'ids': list(ids)
        }
