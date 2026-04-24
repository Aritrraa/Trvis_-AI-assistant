import os
import shutil
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyPDFLoader, TextLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# ------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------
# DB_DIR is the folder where our "Memory" (the vector database) will be saved.
DB_DIR = "chroma_db"
# DATA_DIR is the folder where we will store the raw PDF and Text files.
DATA_DIR = "data"

# We use a global variable so we don't have to load the database multiple times.
_vectorstore = None

def get_embeddings():
    """
    Embeddings are how AI understands text. It converts sentences into numbers.
    We are using a small, beginner-friendly model called 'all-MiniLM-L6-v2'.
    It is very fast and doesn't require a giant download.
    """
    return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

def get_vectorstore():
    """
    This function gets our database ready. 
    If the database already exists on the computer, it loads it.
    If it doesn't exist, it creates a new empty one.
    """
    global _vectorstore
    
    # If we already loaded it during this run, just return it
    if _vectorstore is not None:
        return _vectorstore
        
    # Make sure the 'data' folder exists
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Check if the database folder already exists
    if os.path.exists(DB_DIR):
        print("Loading existing Chroma database...")
        _vectorstore = Chroma(persist_directory=DB_DIR, embedding_function=get_embeddings())
    else:
        print("Creating a new Chroma database...")
        # We start with a tiny dummy document just to create the database structure
        _vectorstore = Chroma.from_texts(
            texts=["TRVIS Memory Initialized."], 
            embedding=get_embeddings(),
            persist_directory=DB_DIR
        )
        
        # Read any files that might already be in the data folder
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
    This function takes a simple text string (like a conversation)
    and saves it permanently into the AI's database.
    """
    global _vectorstore
    if _vectorstore is None:
        get_vectorstore()
        
    _vectorstore.add_texts([text])

def get_retriever():
    """
    This gives the LangChain Agent a "search tool".
    We increased 'k' to 15 so it grabs a massive amount of text 
    (basically the entire document), allowing Trvis to summarize 
    and give broad advice instead of just finding specific facts!
    """
    vs = get_vectorstore()
    return vs.as_retriever(search_kwargs={"k": 15})
