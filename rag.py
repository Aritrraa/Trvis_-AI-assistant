import os
import shutil
import threading
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyPDFLoader, TextLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# ------------------------------------------------------------------
# CONFIGURATION & THREAD SYNCHRONIZATION
# ------------------------------------------------------------------
DB_DIR = "chroma_db"
DATA_DIR = "data"

# Thread-safe re-entrant lock to prevent race conditions during background logging
_rag_lock = threading.RLock()
_vectorstore = None
_embeddings = None

def get_embeddings():
    """
    Cached, thread-safe embeddings model. Uses explicit CPU allocation
    to prevent PyTorch meta tensor race conditions when threads initialize.
    """
    global _embeddings
    if _embeddings is not None:
        return _embeddings
        
    with _rag_lock:
        if _embeddings is None:
            _embeddings = HuggingFaceEmbeddings(
                model_name="all-MiniLM-L6-v2",
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True}
            )
        return _embeddings

def get_vectorstore():
    """
    Thread-safe database getter.
    """
    global _vectorstore
    if _vectorstore is not None:
        return _vectorstore
        
    with _rag_lock:
        if _vectorstore is not None:
            return _vectorstore
            
        os.makedirs(DATA_DIR, exist_ok=True)
        embeddings = get_embeddings()
        
        if os.path.exists(DB_DIR):
            print("Loading existing Chroma database...")
            _vectorstore = Chroma(persist_directory=DB_DIR, embedding_function=embeddings)
        else:
            print("Creating a new Chroma database...")
            _vectorstore = Chroma.from_texts(
                texts=["TRVIS Memory Initialized."], 
                embedding=embeddings,
                persist_directory=DB_DIR
            )
            ingest_all_documents()
            
        return _vectorstore

def ingest_all_documents():
    """
    This function reads ALL files in the 'data' folder and saves them to the database.
    """
    global _vectorstore
    if _vectorstore is None:
        get_vectorstore()
        
    # Set up loaders to read PDFs and Text files
    pdf_loader = DirectoryLoader(DATA_DIR, glob="**/*.pdf", loader_cls=PyPDFLoader)
    txt_loader = DirectoryLoader(DATA_DIR, glob="**/*.txt", loader_cls=TextLoader)
    
    docs = []
    
    # Try to load the PDFs
    try:
        docs.extend(pdf_loader.load())
    except Exception as e:
        print(f"Skipped PDF loading: {e}")
        
    # Try to load the Text files
    try:
        docs.extend(txt_loader.load())
    except Exception as e:
        print(f"Skipped Text loading: {e}")
        
    if not docs:
        return None

    # We cannot feed a massive PDF to the AI all at once. 
    # We must split it into "chunks" of 1000 characters.
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = text_splitter.split_documents(docs)
    
    # Add these chunks to our database
    if splits:
        _vectorstore.add_documents(splits)
        print(f"Successfully added {len(docs)} files into the database.")

def ingest_single_file(file_path):
    """
    This function is used by the UPLOAD button in the UI.
    It takes one single file, copies it to the data folder, and adds it to the database.
    """
    global _vectorstore
    if _vectorstore is None:
        get_vectorstore()
        
    os.makedirs(DATA_DIR, exist_ok=True)
    filename = os.path.basename(file_path)
    dest_path = os.path.join(DATA_DIR, filename)
    
    # 1. Copy the file into our 'data' folder
    if os.path.abspath(file_path) != os.path.abspath(dest_path):
        shutil.copy2(file_path, dest_path)
        
    # 2. Read the file
    if filename.endswith(".pdf"):
        loader = PyPDFLoader(dest_path)
    else:
        # For text files, try to read standard text, fallback if weird characters exist
        try:
            loader = TextLoader(dest_path, encoding='utf-8')
            loader.load() # Test if it works
        except:
            loader = TextLoader(dest_path)
            
    docs = loader.load()
    
    # 3. Split it into chunks
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = text_splitter.split_documents(docs)
    
    # 4. Save chunks to database
    if splits:
        _vectorstore.add_documents(splits)
        return len(splits)
    return 0

def add_to_memory(text):
    """
    Safely saves a conversation snippet into long-term vector memory.
    Synchronized with _rag_lock to prevent multi-threaded database corruption.
    """
    try:
        with _rag_lock:
            vs = get_vectorstore()
            vs.add_texts([text])
    except Exception as e:
        print(f"Memory logging skipped: {e}")

def get_retriever():
    """
    This gives the LangChain Agent a "search tool".
    We increased 'k' to 15 so it grabs a massive amount of text 
    (basically the entire document), allowing Trvis to summarize 
    and give broad advice instead of just finding specific facts!
    """
    vs = get_vectorstore()
    return vs.as_retriever(search_kwargs={"k": 15})
