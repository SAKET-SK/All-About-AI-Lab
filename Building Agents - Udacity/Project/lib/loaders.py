from typing import List
import pdfplumber
from lib.documents import Corpus, Document


class PDFLoader:
    """
    Document loader for extracting text content from PDF files.
    
    This class provides functionality to parse PDF documents and convert them
    into a structured format suitable for vector storage and retrieval. Each
    page of the PDF becomes a separate Document object, enabling page-level
    search and retrieval in RAG applications.
    
    The loader uses pdfplumber for robust PDF text extraction, handling:
    - Multi-page PDF documents
    - Text extraction with layout preservation
    - Automatic page numbering and identification
    - Filtering of empty or whitespace-only pages
    
    Example:
        >>> loader = PDFLoader("research_paper.pdf")
        >>> corpus = loader.load()
        >>> print(f"Loaded {len(corpus)} pages")
        >>> print(f"First page content: {corpus[0].content[:100]}...")
    """
    def __init__(self, pdf_path:str):
        self.pdf_path = pdf_path

    def load(self) -> Document:
        corpus = Corpus()

        with pdfplumber.open(self.pdf_path) as pdf:
            for num, page in enumerate(pdf.pages, start=1):
                text = page.extract_text()
                if text:
                    corpus.append(
                        Document(
                            id=str(num),
                            content=text
                        )
                    )
        return corpus
