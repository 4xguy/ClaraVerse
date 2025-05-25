import os
import sys
import socket
import logging
import signal
import traceback
import time
import argparse
from datetime import datetime
from contextlib import contextmanager
from fastapi import FastAPI, HTTPException, Request, File, UploadFile, Form, Depends, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import tempfile
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any
import json
from pydantic import BaseModel

# Import our DocumentAI class
from ragDbClara import DocumentAI
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.document_loaders import CSVLoader
from langchain_community.document_loaders import TextLoader  # Fixed import

# Import Speech2Text
from Speech2Text import Speech2Text

# Import auth and database routes
from routes.auth_routes import router as auth_router
from routes.db_routes import router as db_router
from routes.vector_routes import router as vector_router
from db.database import get_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("clara-backend")

# Store start time
START_TIME = datetime.now().isoformat()

# Parse command line arguments
parser = argparse.ArgumentParser(description='Clara Backend Server')
parser.add_argument('--host', type=str, default='127.0.0.1', help='Host to bind to')
parser.add_argument('--port', type=int, default=5000, help='Port to bind to')
args = parser.parse_args()

# Use the provided host and port
HOST = args.host
PORT = args.port

logger.info(f"Starting server on {HOST}:{PORT}")

# Setup FastAPI
app = FastAPI(title="Clara Backend API", version="1.0.0")

# Import and include the diffusers API router
try:
    from diffusers_api import router as diffusers_router
    app.include_router(diffusers_router, prefix="/diffusers")
except Exception as e:
    logger.warning(f"Diffusers API not loaded: {e}")

# Include auth and database routers
app.include_router(auth_router, prefix="/auth", tags=["authentication"])
app.include_router(db_router, prefix="/db", tags=["database"])
app.include_router(vector_router, prefix="/vector", tags=["vector"])

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Add global exception middleware
@app.middleware("http")
async def catch_exceptions_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        logger.error(f"Request to {request.url} failed: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "detail": traceback.format_exc()}
        )

# Note: Database initialization is now handled by PostgreSQL
# The tables are created via SQL scripts in docker/postgres/init/
# No need for SQLite initialization anymore

# Create a persistent directory for vector databases
vectordb_dir = os.path.join(os.path.expanduser("~"), ".clara", "vectordb")
temp_vectordb_dir = os.path.join(vectordb_dir, "temp")  # Add directory for temporary collections
os.makedirs(vectordb_dir, exist_ok=True)
os.makedirs(temp_vectordb_dir, exist_ok=True)  # Create temp directory

# Initialize DocumentAI singleton cache
doc_ai_cache = {}

def get_doc_ai(collection_name: str = "default_collection"):
    """Create or retrieve the DocumentAI instance from cache"""
    global doc_ai_cache
    
    # Return cached instance if it exists
    if collection_name in doc_ai_cache:
        return doc_ai_cache[collection_name]
    
    # Create new instance if not in cache
    if collection_name.startswith("temp_collection_"):
        # Use temp directory for temporary collections
        persist_dir = os.path.join(temp_vectordb_dir, collection_name)
    else:
        # Use regular directory for permanent collections
        persist_dir = os.path.join(vectordb_dir, collection_name)
    
    os.makedirs(persist_dir, exist_ok=True)
    
    # Create new instance and cache it
    doc_ai_cache[collection_name] = DocumentAI(
        persist_directory=persist_dir,
        collection_name=collection_name
    )
    
    return doc_ai_cache[collection_name]

# Speech2Text instance cache
speech2text_instance = None

def get_speech2text():
    """Create or retrieve the Speech2Text instance from cache"""
    global speech2text_instance
    
    if speech2text_instance is None:
        # Use tiny model with CPU for maximum compatibility
        speech2text_instance = Speech2Text(
            model_size="tiny",
            device="cpu",
            compute_type="int8"
        )
    
    return speech2text_instance

# Pydantic models for request/response
class ChatRequest(BaseModel):
    query: str
    collection_name: str = "default_collection"
    system_template: Optional[str] = None
    k: int = 4
    filter: Optional[Dict[str, Any]] = None

class SearchRequest(BaseModel):
    query: str
    collection_name: str = "default_collection"
    k: int = 4
    filter: Optional[Dict[str, Any]] = None

class CollectionCreate(BaseModel):
    name: str
    description: Optional[str] = None

@app.get("/")
def read_root():
    """Root endpoint for basic health check"""
    return {
        "status": "ok", 
        "service": "Clara Backend", 
        "port": PORT,
        "uptime": str(datetime.now() - datetime.fromisoformat(START_TIME)),
        "start_time": START_TIME
    }

@app.get("/test")
def read_test(db=Depends(get_db)):
    """Test endpoint that returns data from the database"""
    try:
        cursor = db.cursor()
        # Test with a simple query
        cursor.execute("SELECT 1 as id, 'Hello from PostgreSQL' as value")
        row = cursor.fetchone()
        
        if row:
            return JSONResponse(content={"id": row[0], "value": row[1], "port": PORT})
        return JSONResponse(content={"error": "No data found", "port": PORT})
    except Exception as e:
        logger.error(f"Error in /test endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "port": PORT,
        "uptime": str(datetime.now() - datetime.fromisoformat(START_TIME))
    }

# Document management endpoints
@app.post("/collections")
async def create_collection(collection: CollectionCreate, db=Depends(get_db)):
    """Create a new collection"""
    try:
        cursor = db.cursor()
        
        # First check if collection exists
        cursor.execute(
            "SELECT name FROM collections WHERE name = %s",
            (collection.name,)
        )
        existing = cursor.fetchone()
        
        if existing:
            return JSONResponse(
                status_code=409,
                content={"detail": f"Collection '{collection.name}' already exists"}
            )
        
        # Create the collection
        try:
            cursor.execute(
                """
                INSERT INTO collections (name, description)
                VALUES (%s, %s)
                """,
                (collection.name, collection.description or "")
            )
            db.commit()
        except Exception as e:
            db.rollback()
            # Handle race condition where collection was created between our check and insert
            if "duplicate key" in str(e).lower():
                return JSONResponse(
                    status_code=409,
                    content={"detail": f"Collection '{collection.name}' already exists"}
                )
            raise
        
        # Initialize vector store for the collection
        get_doc_ai(collection.name)
        
        return {"message": f"Collection '{collection.name}' created successfully"}
        
    except Exception as e:
        logger.error(f"Error creating collection: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        )

@app.get("/collections")
def list_collections(db=Depends(get_db)):
    """List all available document collections"""
    try:
        cursor = db.cursor()
        cursor.execute("SELECT name, description, document_count, created_at FROM collections")
        columns = [desc[0] for desc in cursor.description]
        collections = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return {"collections": collections}
    except Exception as e:
        logger.error(f"Error listing collections: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/collections/{collection_name}")
async def delete_collection(collection_name: str, db=Depends(get_db)):
    """Delete a collection and all its documents"""
    try:
        # Delete from vector store first
        doc_ai = get_doc_ai(collection_name)
        
        # Get all document chunks for this collection
        cursor = db.cursor()
        cursor.execute("""
            SELECT dc.chunk_id
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE d.collection_name = %s
        """, (collection_name,))
        chunk_ids = [row[0] for row in cursor.fetchall()]
        
        if chunk_ids:
            # Delete chunks from vector store
            doc_ai.delete_documents(chunk_ids)
        
        # Delete all documents and chunks from PostgreSQL
        cursor.execute("DELETE FROM documents WHERE collection_name = %s", (collection_name,))
        
        # Delete collection record
        cursor.execute("DELETE FROM collections WHERE name = %s", (collection_name,))
        db.commit()
        
        # Remove from cache to force recreation
        if collection_name in doc_ai_cache:
            del doc_ai_cache[collection_name]
            
        return {"message": f"Collection {collection_name} deleted successfully"}
        
    except Exception as e:
        logger.error(f"Error deleting collection: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/collections/recreate")
async def recreate_collection(collection_name: str = "default_collection", db=Depends(get_db)):
    """Recreate a collection by deleting and reinitializing it"""
    try:
        # Get persist directory path
        persist_dir = os.path.join(vectordb_dir, collection_name)
        if collection_name.startswith("temp_collection_"):
            persist_dir = os.path.join(temp_vectordb_dir, collection_name)

        # Remove from cache first to ensure we don't have any lingering instances
        if collection_name in doc_ai_cache:
            del doc_ai_cache[collection_name]

        # Delete the directory completely if it exists
        if os.path.exists(persist_dir):
            try:
                shutil.rmtree(persist_dir)
                logger.info(f"Deleted persist directory: {persist_dir}")
            except Exception as e:
                logger.error(f"Error deleting directory: {e}")
                # Even if directory deletion fails, continue with recreation

        # Delete all documents from the database
        cursor = db.cursor()
        # Delete all documents and chunks from PostgreSQL
        cursor.execute("DELETE FROM document_chunks WHERE document_id IN (SELECT id FROM documents WHERE collection_name = %s)", (collection_name,))
        cursor.execute("DELETE FROM documents WHERE collection_name = %s", (collection_name,))
        cursor.execute("DELETE FROM collections WHERE name = %s", (collection_name,))
        db.commit()

        # Create directory for new collection
        os.makedirs(persist_dir, exist_ok=True)
        
        # Get a fresh DocumentAI instance
        doc_ai = DocumentAI(
            persist_directory=persist_dir,
            collection_name=collection_name
        )
        
        # Store in cache
        doc_ai_cache[collection_name] = doc_ai
        
        # Create new collection record
        cursor.execute(
            "INSERT INTO collections (name, description) VALUES (%s, %s)",
            (collection_name, f"Recreated collection {collection_name}")
        )
        db.commit()
        
        return {
            "message": f"Collection {collection_name} recreated successfully",
            "collection_name": collection_name
        }
        
    except Exception as e:
        logger.error(f"Error recreating collection: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    collection_name: str = Form("default_collection"),
    metadata: str = Form("{}"),
    db=Depends(get_db)
):
    """Upload a document file (PDF, CSV, or plain text) and add it to the vector store"""
    # Check if collection exists, create if not
    try:
        cursor = db.cursor()
        cursor.execute("SELECT name FROM collections WHERE name = %s", (collection_name,))
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO collections (name, description) VALUES (%s, %s)",
                (collection_name, f"Auto-created for {file.filename}")
            )
            db.commit()
    except Exception as e:
        logger.error(f"Error checking/creating collection: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
    # Create a temporary directory to save the uploaded file
    with tempfile.TemporaryDirectory() as temp_dir:
        file_path = Path(temp_dir) / file.filename
        
        # Save uploaded file
        try:
            with open(file_path, "wb") as f:
                shutil.copyfileobj(file.file, f)
        except Exception as e:
            logger.error(f"Error saving file: {e}")
            raise HTTPException(status_code=500, detail=f"Could not save file: {str(e)}")
        
        # Process the file based on extension
        file_extension = file.filename.lower().split('.')[-1]
        documents = []
        file_type = file_extension
        
        try:
            if file_extension == 'pdf':
                loader = PyPDFLoader(str(file_path))
                documents = loader.load()
            elif file_extension == 'csv':
                loader = CSVLoader(file_path=str(file_path))
                documents = loader.load()
            elif file_extension in ['txt', 'md', 'html']:
                loader = TextLoader(str(file_path))
                documents = loader.load()
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_extension}")
            
            # Get or create DocumentAI with specific collection - use cache
            doc_ai = get_doc_ai(collection_name)
            
            # Parse metadata if provided
            try:
                meta_dict = json.loads(metadata)
                
                # Add file metadata to each document
                for doc in documents:
                    doc.metadata.update(meta_dict)
                    doc.metadata["source_file"] = file.filename
                    doc.metadata["file_type"] = file_extension
            except json.JSONDecodeError:
                logger.warning(f"Invalid metadata JSON: {metadata}")
            
            # Add documents to vector store
            doc_ids = doc_ai.add_documents(documents)
            
            # Update database
            cursor = db.cursor()
            cursor.execute(
                "INSERT INTO documents (filename, file_type, collection_name, metadata) VALUES (%s, %s, %s, %s) RETURNING id",
                (file.filename, file_type, collection_name, metadata)
            )
            document_id = cursor.fetchone()[0]
            
            # Store the relationship between document and its chunks
            for chunk_id in doc_ids:
                cursor.execute(
                    "INSERT INTO document_chunks (document_id, chunk_id) VALUES (%s, %s)",
                    (document_id, chunk_id)
                )
            
            # Update document count in collection
            cursor.execute(
                "UPDATE collections SET document_count = document_count + %s WHERE name = %s",
                (1, collection_name)  # Only count the original document, not chunks
            )
            db.commit()
            
            return {
                "status": "success",
                "filename": file.filename,
                "collection": collection_name,
                "document_count": len(documents),
                "document_ids": doc_ids[:5] + ['...'] if len(doc_ids) > 5 else doc_ids
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"Error processing document: {str(e)}")

@app.get("/documents")
async def list_documents(collection_name: Optional[str] = None, db=Depends(get_db)):
    """List all documents, optionally filtered by collection"""
    try:
        cursor = db.cursor()
        
        query = """
            SELECT d.id, d.filename, d.file_type, d.collection_name, d.metadata, 
                   d.created_at, COUNT(dc.id) as chunk_count 
            FROM documents d
            LEFT JOIN document_chunks dc ON d.id = dc.document_id
        """
        
        params = []
        if collection_name:
            query += " WHERE d.collection_name = %s"
            params.append(collection_name)
            
        query += " GROUP BY d.id, d.filename, d.file_type, d.collection_name, d.metadata, d.created_at"
        
        cursor.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        documents = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        return {"documents": documents}
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error listing documents: {str(e)}")

@app.delete("/documents/{document_id}")
async def delete_document(document_id: int, db=Depends(get_db)):
    """Delete a document and all its chunks from the database and vector store"""
    try:
        # Get document details and chunk IDs
        cursor = db.cursor()
        cursor.execute(
            "SELECT collection_name FROM documents WHERE id = %s", 
            (document_id,)
        )
        document = cursor.fetchone()
        
        if not document:
            raise HTTPException(status_code=404, detail=f"Document with ID {document_id} not found")
            
        collection_name = document[0]
        
        # Get all chunks related to this document
        cursor.execute(
            "SELECT chunk_id FROM document_chunks WHERE document_id = %s", 
            (document_id,)
        )
        chunks = [row[0] for row in cursor.fetchall()]
        
        # Get DocumentAI instance for this collection
        doc_ai = get_doc_ai(collection_name)
        
        # Delete chunks from vector store
        if chunks:
            doc_ai.delete_documents(chunks)
        
        # Delete document chunks first (in case CASCADE doesn't work)
        cursor.execute(
            "DELETE FROM document_chunks WHERE document_id = %s", 
            (document_id,)
        )
        
        # Delete the document itself
        cursor.execute(
            "DELETE FROM documents WHERE id = %s", 
            (document_id,)
        )
        
        # Update document count in collection
        cursor.execute(
            "UPDATE collections SET document_count = document_count - 1 WHERE name = %s AND document_count > 0",
            (collection_name,)
        )
        db.commit()
        
        return {
            "status": "success", 
            "message": f"Document {document_id} and its {len(chunks)} chunks deleted"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error deleting document: {str(e)}")

# Improved helper function to validate and format filters
def format_chroma_filter(filter_dict: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Format a filter dictionary to be compatible with Chroma"""
    if not filter_dict:
        return None
        
    chroma_filter = {}
    for key, value in filter_dict.items():
        # Skip empty values
        if value is None or (isinstance(value, dict) and not value):
            continue
            
        if isinstance(value, dict):
            # Check if it has valid operators
            if not any(op.startswith('$') for op in value.keys()):
                # Convert to $eq if no operators
                chroma_filter[key] = {"$eq": value}
            else:
                # Already has operators
                chroma_filter[key] = value
        else:
            # Simple value, convert to $eq
            chroma_filter[key] = {"$eq": value}
    
    # Return None if the filter ended up empty
    return chroma_filter if chroma_filter else None

@app.post("/documents/search")
async def search_documents(request: SearchRequest):
    """Search documents in the vector store for ones similar to the query"""
    try:
        # Get DocumentAI with specific collection from cache
        doc_ai = get_doc_ai(request.collection_name)
        
        # Format the filter if provided, otherwise pass None
        formatted_filter = format_chroma_filter(request.filter)
        
        # Perform similarity search
        results = doc_ai.similarity_search(
            query=request.query,
            k=request.k,
            filter=formatted_filter
        )
        
        # Format results
        formatted_results = []
        for doc in results:
            formatted_results.append({
                "content": doc.page_content,
                "metadata": doc.metadata,
                "score": doc.metadata.get("score", None)  # Some vector stores return scores
            })
        
        return {
            "query": request.query,
            "collection": request.collection_name,
            "results": formatted_results
        }
    except Exception as e:
        logger.error(f"Error searching documents: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error searching documents: {str(e)}")

@app.post("/chat")
async def chat_with_documents(request: ChatRequest):
    """Chat with the AI using documents as context"""
    try:
        # Get DocumentAI with specific collection from cache
        doc_ai = get_doc_ai(request.collection_name)
        
        # Use default or custom system template
        system_template = request.system_template
        
        # Format the filter if provided, otherwise pass None
        formatted_filter = format_chroma_filter(request.filter)
        
        # Get response from AI
        if system_template:
            response = doc_ai.chat_with_context(
                query=request.query,
                k=request.k,
                filter=formatted_filter,
                system_template=system_template
            )
        else:
            response = doc_ai.chat_with_context(
                query=request.query,
                k=request.k,
                filter=formatted_filter
            )
        
        return {
            "query": request.query,
            "collection": request.collection_name,
            "response": response
        }
    except Exception as e:
        logger.error(f"Error in chat: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error in chat: {str(e)}")

# Direct chat without documents
@app.post("/chat/direct")
async def direct_chat(query: str, system_prompt: Optional[str] = None):
    """Chat directly with the AI without document context"""
    try:
        # Get DocumentAI instance
        doc_ai = get_doc_ai()
        
        # Use default or custom system prompt
        system_prompt = system_prompt or "You are a helpful assistant."
        
        # Get response from AI
        response = doc_ai.chat(
            user_message=query,
            system_prompt=system_prompt
        )
        
        return {
            "query": query,
            "response": response
        }
    except Exception as e:
        logger.error(f"Error in direct chat: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error in direct chat: {str(e)}")

# Audio transcription endpoint
@app.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    beam_size: int = Form(5),
    initial_prompt: Optional[str] = Form(None)
):
    """Transcribe an audio file using faster-whisper (CPU mode)"""
    # Validate file extension
    supported_formats = ['mp3', 'wav', 'flac', 'm4a', 'ogg', 'opus']
    file_extension = file.filename.lower().split('.')[-1]
    
    if file_extension not in supported_formats:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported audio format: {file_extension}. Supported formats: {', '.join(supported_formats)}"
        )
    
    # Read file content
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty audio file")
    except Exception as e:
        logger.error(f"Error reading audio file: {e}")
        raise HTTPException(status_code=500, detail=f"Error reading audio file: {str(e)}")
    
    # Get Speech2Text instance
    try:
        s2t = get_speech2text()
    except Exception as e:
        logger.error(f"Error initializing Speech2Text: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to initialize Speech2Text: {str(e)}")
    
    # Transcribe the audio
    try:
        result = s2t.transcribe_bytes(
            content,
            language=language,
            beam_size=beam_size,
            initial_prompt=initial_prompt
        )
        
        return {
            "status": "success",
            "filename": file.filename,
            "transcription": result
        }
    except Exception as e:
        logger.error(f"Error transcribing audio: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error transcribing audio: {str(e)}")

# Handle graceful shutdown
def handle_exit(signum, frame):
    logger.info(f"Received signal {signum}, shutting down gracefully")
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, handle_exit)
signal.signal(signal.SIGTERM, handle_exit)

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting server on {HOST}:{PORT}")
    
    # Start the server with reload=False to prevent duplicate processes
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        log_level="info",
        reload=False  # Change this to false to prevent multiple processes
    )
