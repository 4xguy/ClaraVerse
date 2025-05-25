from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import openai
import os
import logging
from uuid import UUID

from ..db.database import get_db
from ..db.models import Embedding, Document, DocumentChunk
from ..auth.auth import get_current_user, get_current_user_optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vectors", tags=["vectors"])

# Configure OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# Request/Response models
class EmbedRequest(BaseModel):
    text: str

class DocumentRequest(BaseModel):
    content: str
    metadata: Optional[Dict[str, Any]] = {}

class LargeDocumentRequest(BaseModel):
    name: str
    content: str
    type: str
    metadata: Optional[Dict[str, Any]] = {}

class SearchRequest(BaseModel):
    query: str
    limit: int = 5
    threshold: float = 0.8

class EmbedResponse(BaseModel):
    embedding: List[float]

class DocumentResponse(BaseModel):
    id: str
    content: str
    metadata: Dict[str, Any]
    created_at: str
    updated_at: str

class SearchResult(BaseModel):
    id: str
    content: str
    metadata: Dict[str, Any]
    distance: float
    document_name: Optional[str] = None

# Helper functions
def create_embedding(text: str) -> List[float]:
    """Create embedding using OpenAI API."""
    try:
        response = openai.embeddings.create(
            model="text-embedding-ada-002",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Failed to create embedding: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create embedding: {str(e)}"
        )

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """Split text into chunks with overlap."""
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
        # Try to find a natural break point
        if end < len(text):
            last_period = text.rfind('.', start, end)
            last_newline = text.rfind('\n', start, end)
            break_point = max(last_period, last_newline)
            
            if break_point > start + chunk_size - overlap:
                end = break_point + 1
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        start = end - overlap
    
    return chunks

@router.post("/embed", response_model=EmbedResponse)
def create_embedding_endpoint(request: EmbedRequest):
    """Create embedding for text."""
    embedding = create_embedding(request.text)
    return {"embedding": embedding}

@router.post("/documents", response_model=DocumentResponse)
def add_document(
    request: DocumentRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add a document to the vector store."""
    # Create embedding
    embedding = create_embedding(request.content)
    
    # Store in database
    doc = Embedding(
        user_id=current_user.id,
        content=request.content,
        embedding=embedding,
        metadata=request.metadata
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    
    return {
        "id": str(doc.id),
        "content": doc.content,
        "metadata": doc.metadata,
        "created_at": doc.created_at.isoformat(),
        "updated_at": doc.updated_at.isoformat()
    }

@router.post("/documents/large", response_model=Dict[str, str])
def add_large_document(
    request: LargeDocumentRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add a large document with chunking."""
    # Create document record
    doc = Document(
        user_id=current_user.id,
        name=request.name,
        type=request.type,
        size=len(request.content),
        content=request.content,
        metadata=request.metadata
    )
    db.add(doc)
    db.flush()  # Get document ID without committing
    
    # Chunk the content
    chunks = chunk_text(request.content)
    
    # Process chunks
    for i, chunk in enumerate(chunks):
        embedding = create_embedding(chunk)
        
        chunk_record = DocumentChunk(
            document_id=doc.id,
            chunk_index=i,
            content=chunk,
            embedding=embedding,
            metadata={"chunk_index": i}
        )
        db.add(chunk_record)
    
    db.commit()
    
    return {"id": str(doc.id)}

@router.post("/search", response_model=List[SearchResult])
def search_documents(
    request: SearchRequest,
    current_user = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """Search for similar documents."""
    # Create query embedding
    query_embedding = create_embedding(request.query)
    
    # Build query
    query = """
        SELECT id, content, metadata, 
               1 - (embedding <=> :embedding::vector) as similarity
        FROM vectors.embeddings
        WHERE 1 - (embedding <=> :embedding::vector) > :threshold
    """
    
    params = {
        "embedding": f"[{','.join(map(str, query_embedding))}]",
        "threshold": request.threshold
    }
    
    if current_user:
        query += " AND user_id = :user_id"
        params["user_id"] = current_user.id
    
    query += " ORDER BY similarity DESC LIMIT :limit"
    params["limit"] = request.limit
    
    # Execute query
    result = db.execute(text(query), params)
    
    # Format results
    results = []
    for row in result:
        results.append({
            "id": str(row.id),
            "content": row.content,
            "metadata": row.metadata,
            "distance": 1 - row.similarity
        })
    
    return results

@router.post("/search/chunks", response_model=List[SearchResult])
def search_document_chunks(
    request: SearchRequest,
    current_user = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """Search in document chunks."""
    # Create query embedding
    query_embedding = create_embedding(request.query)
    
    # Build query
    query = """
        SELECT 
            c.id,
            c.content,
            c.metadata,
            d.name as document_name,
            1 - (c.embedding <=> :embedding::vector) as similarity
        FROM vectors.document_chunks c
        JOIN vectors.documents d ON c.document_id = d.id
        WHERE 1 - (c.embedding <=> :embedding::vector) > :threshold
    """
    
    params = {
        "embedding": f"[{','.join(map(str, query_embedding))}]",
        "threshold": request.threshold
    }
    
    if current_user:
        query += " AND d.user_id = :user_id"
        params["user_id"] = current_user.id
    
    query += " ORDER BY similarity DESC LIMIT :limit"
    params["limit"] = request.limit
    
    # Execute query
    result = db.execute(text(query), params)
    
    # Format results
    results = []
    for row in result:
        results.append({
            "id": str(row.id),
            "content": row.content,
            "metadata": row.metadata,
            "document_name": row.document_name,
            "distance": 1 - row.similarity
        })
    
    return results

@router.get("/documents", response_model=List[DocumentResponse])
def get_user_documents(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's documents."""
    docs = db.query(Embedding).filter(
        Embedding.user_id == current_user.id
    ).order_by(Embedding.created_at.desc()).all()
    
    return [
        {
            "id": str(doc.id),
            "content": doc.content,
            "metadata": doc.metadata,
            "created_at": doc.created_at.isoformat(),
            "updated_at": doc.updated_at.isoformat()
        }
        for doc in docs
    ]

@router.delete("/documents/{document_id}")
def delete_document(
    document_id: UUID,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a document."""
    doc = db.query(Embedding).filter(
        Embedding.id == document_id,
        Embedding.user_id == current_user.id
    ).first()
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    db.delete(doc)
    db.commit()
    
    return {"message": "Document deleted successfully"}

@router.delete("/documents/large/{document_id}")
def delete_large_document(
    document_id: UUID,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a large document and its chunks."""
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Chunks will be deleted automatically due to CASCADE
    db.delete(doc)
    db.commit()
    
    return {"message": "Document deleted successfully"}

@router.post("/upload")
async def upload_file_for_vectorization(
    file: UploadFile = File(...),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload a file for vectorization."""
    # Read file content
    content = await file.read()
    text_content = content.decode('utf-8', errors='ignore')
    
    # Create document
    doc = Document(
        user_id=current_user.id,
        name=file.filename,
        type=file.content_type or 'text/plain',
        size=len(content),
        content=text_content,
        metadata={"filename": file.filename}
    )
    db.add(doc)
    db.flush()
    
    # Chunk and vectorize
    chunks = chunk_text(text_content)
    for i, chunk in enumerate(chunks):
        embedding = create_embedding(chunk)
        
        chunk_record = DocumentChunk(
            document_id=doc.id,
            chunk_index=i,
            content=chunk,
            embedding=embedding,
            metadata={"chunk_index": i}
        )
        db.add(chunk_record)
    
    db.commit()
    
    return {"id": str(doc.id)}

@router.get("/stats")
def get_vector_stats(
    current_user = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """Get vector database statistics."""
    # Build query
    query = """
        SELECT 
            COUNT(DISTINCT e.id) as total_embeddings,
            COUNT(DISTINCT d.id) as total_documents,
            COUNT(DISTINCT c.id) as total_chunks,
            AVG(LENGTH(c.content)) as average_chunk_size
        FROM vectors.embeddings e
        FULL JOIN vectors.documents d ON d.user_id = e.user_id
        LEFT JOIN vectors.document_chunks c ON c.document_id = d.id
    """
    
    params = {}
    if current_user:
        query += " WHERE e.user_id = :user_id OR d.user_id = :user_id"
        params["user_id"] = current_user.id
    
    result = db.execute(text(query), params).first()
    
    return {
        "total_documents": int(result.total_embeddings or 0) + int(result.total_documents or 0),
        "total_chunks": int(result.total_chunks or 0),
        "average_chunk_size": float(result.average_chunk_size or 0)
    }