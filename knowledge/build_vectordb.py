import os
import sys

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from knowledge.rag_client import FactorRAGClient

def build_alpha101_db():
    md_path = os.path.join(PROJECT_ROOT, "data", "alpha101.md")
    if not os.path.exists(md_path):
        print(f"File not found: {md_path}")
        return
    
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Split by markdown headers
    raw_chunks = content.split('\n## ')
    
    cleaned_chunks = []
    for i, chunk in enumerate(raw_chunks):
        if i > 0: 
            chunk = "## " + chunk
        
        chunk = chunk.strip()
        if chunk:
            cleaned_chunks.append(chunk)

    print(f"Parsed {len(cleaned_chunks)} factor blocks from alpha101.md")
    
    client = FactorRAGClient()
    
    # Generate tracking IDs and metadata
    ids = [f"alpha101_{i}" for i in range(len(cleaned_chunks))]
    metadatas = [{"source": "alpha101.md", "chunk_index": i} for i in range(len(cleaned_chunks))]
    
    # Add to ChromaDB
    client.add_documents(cleaned_chunks, metadatas=metadatas, ids=ids)
    print(f"Vector DB successfully initialized at {os.path.join(PROJECT_ROOT, 'knowledge', 'chroma_db')}")

if __name__ == "__main__":
    build_alpha101_db()
