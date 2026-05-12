import os
import chromadb
from chromadb.utils import embedding_functions

KNOWLEDGE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(KNOWLEDGE_DIR, "chroma_db")

class FactorRAGClient:
    """
    RAG Client for Alpha101 Factors using ChromaDB.
    This provides similarity search over the knowledge base.
    """
    def __init__(self, collection_name="alpha_factors"):
        # We use PersistentClient to save the DB locally
        self.client = chromadb.PersistentClient(path=DB_PATH)
        
        # Use default sentence transformer embedding
        self.embedding_func = embedding_functions.DefaultEmbeddingFunction()
        
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embedding_func
        )

    def add_documents(self, texts, metadatas=None, ids=None):
        if not texts:
            return
        if ids is None:
            ids = [f"doc_{i}" for i in range(len(texts))]
        self.collection.add(
            documents=texts,
            metadatas=metadatas,
            ids=ids
        )
        print(f"✅ Added {len(texts)} documents to vector DB collection.")

    def query(self, query_text, n_results=5):
        """
        Query the best matching factors from the knowledge base.
        """
        if self.collection.count() == 0:
            return []
            
        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results
        )
        
        # Format results into a clean list of strings
        matched_docs = []
        if results and 'documents' in results and len(results['documents']) > 0:
            docs = results['documents'][0]
            metadatas = results.get('metadatas', [[]])[0]
            
            for doc, meta in zip(docs, metadatas):
                source = meta.get('source', 'unknown')
                matched_docs.append(f"[{source}]:\n{doc}")
                
        return matched_docs
