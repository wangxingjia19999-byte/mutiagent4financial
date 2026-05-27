import os
import sys

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from knowledge.rag_client import FactorRAGClient
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

def build_pdf_db(pdf_filename="1601.00991v3.pdf"):
    """
    Parse a PDF file, chunk it using RecursiveCharacterTextSplitter, 
    and store the chunks into ChromaDB.
    """
    pdf_path = os.path.join(PROJECT_ROOT, "knowledge", pdf_filename)
    if not os.path.exists(pdf_path):
        print(f"File not found: {pdf_path}")
        return
        
    print(f"Reading PDF: {pdf_filename}...")
    reader = PdfReader(pdf_path)
    
    # Extract text from all pages
    full_text = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text:
            full_text.append(text)
            
    combined_text = "\n".join(full_text)
    
    # Initialize splitter
    # 策略：RecursiveCharacterTextSplitter 是业界标准的 RAG 切分器
    # 它会按顺序切割大块文本： 1. 段落 (\n\n) -> 2. 句子 (\n) -> 3. 词 (空格)
    # chunk_size=1000：保证每个文本片段不会过长，超出大模型上下文，也利于 Embedding。
    # chunk_overlap=200：切片之间保留部分重复内容，防止一句话/一个公式被生硬地劈成两半，导致语义丢失。
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len
    )
    
    # Do chunking
    chunks = splitter.split_text(combined_text)
    print(f"Split PDF into {len(chunks)} chunks using chunk_size=1000, overlap=200")
    
    client = FactorRAGClient()
    
    # Generate metadata and IDs
    ids = [f"pdf_{pdf_filename}_{i}" for i in range(len(chunks))]
    metadatas = [{"source": pdf_filename, "chunk_index": i} for i in range(len(chunks))]
    
    # Add to DB
    client.add_documents(chunks, metadatas=metadatas, ids=ids)
    print(f"Successfully added PDF {pdf_filename} to the vector DB.")

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
    # 1. 灌入 Markdown 格式的 Alpha101 因子
    build_alpha101_db()
    # 2. 灌入 PDF 格式的研报 (1601.00991v3.pdf 是 Alpha101 论文)
    build_pdf_db("1601.00991v3.pdf")
