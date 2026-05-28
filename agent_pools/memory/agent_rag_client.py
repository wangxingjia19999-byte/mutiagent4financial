"""
Agent RAG Client - ChromaDB-based RAG for the Alpha101 paper (1601.00991v3.pdf).

Builds a vector index from the PDF on first use, then supports similarity queries.
"""

import os
import chromadb
from chromadb.utils import embedding_functions

MEMORY_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(MEMORY_DIR, '../..'))
PDF_PATH = os.path.join(PROJECT_ROOT, "knowledge", "1601.00991v3.pdf")
CHROMA_DB_PATH = os.path.join(MEMORY_DIR, "chroma_rag_db")

_rag_instance = None


def _parse_pdf(pdf_path: str) -> str:
    """Extract full text from a PDF file."""
    from pypdf import PdfReader
    reader = PdfReader(pdf_path)
    parts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            parts.append(text)
    return "\n".join(parts)


def _chunk_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> list:
    """Split text into overlapping chunks."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
    )
    return splitter.split_text(text)


class AgentRAGClient:
    """
    RAG client for the Alpha101 paper. Builds the vector index from the PDF
    on first use and persists it to disk for subsequent runs.
    """

    def __init__(self, collection_name: str = "alpha101_paper"):
        self.client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        self.embedding_func = embedding_functions.DefaultEmbeddingFunction()
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embedding_func,
        )
        self._ensure_index()

    def _ensure_index(self):
        """Build the vector index from the PDF if the collection is empty."""
        if self.collection.count() > 0:
            return
        if not os.path.exists(PDF_PATH):
            print(f"PDF not found at {PDF_PATH}, RAG will be empty.")
            return

        print(f"Building RAG index from {PDF_PATH} ...")
        full_text = _parse_pdf(PDF_PATH)
        chunks = _chunk_text(full_text)
        print(f"Split PDF into {len(chunks)} chunks.")

        ids = [f"pdf_chunk_{i}" for i in range(len(chunks))]
        metadatas = [{"source": "1601.00991v3.pdf", "chunk_index": i} for i in range(len(chunks))]
        self.collection.add(documents=chunks, metadatas=metadatas, ids=ids)
        print(f"RAG index built with {len(chunks)} chunks.")

    def query(self, query_text: str, n_results: int = 5) -> list:
        """Query the paper for relevant passages."""
        if self.collection.count() == 0:
            return []

        results = self.collection.query(query_texts=[query_text], n_results=n_results)
        matched = []
        if results and results.get('documents') and len(results['documents']) > 0:
            for doc, meta in zip(results['documents'][0], results.get('metadatas', [[]])[0]):
                source = meta.get('source', 'unknown') if meta else 'unknown'
                matched.append(f"[{source}]:\n{doc}")
        return matched


def get_rag_client() -> AgentRAGClient:
    """Get or create the singleton RAG client."""
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = AgentRAGClient()
    return _rag_instance
