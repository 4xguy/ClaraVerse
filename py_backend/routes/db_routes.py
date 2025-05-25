from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging

from ..db.database import get_db
from ..auth.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/db", tags=["database"])

# Request/Response models
class QueryRequest(BaseModel):
    query: str
    params: Optional[List[Any]] = []

class TransactionRequest(BaseModel):
    queries: List[QueryRequest]

# Whitelist of allowed table prefixes for security
ALLOWED_SCHEMAS = ["app", "vectors", "storage"]

def validate_query(query: str) -> bool:
    """Validate query for security."""
    # Convert to lowercase for checking
    query_lower = query.lower().strip()
    
    # Block dangerous operations
    dangerous_keywords = ["drop", "truncate", "delete from auth", "update auth", "insert into auth"]
    for keyword in dangerous_keywords:
        if keyword in query_lower:
            return False
    
    # Only allow SELECT for auth schema
    if "auth." in query_lower and not query_lower.startswith("select"):
        return False
    
    return True

@router.post("/query")
def execute_query(
    request: QueryRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Execute a database query."""
    # Validate query
    if not validate_query(request.query):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Query not allowed for security reasons"
        )
    
    try:
        # Add user context to queries that need it
        query = request.query
        params = request.params or []
        
        # If query references user data, inject user_id
        if "user_id" in query and "user_id" not in [p for p in params if isinstance(p, dict)]:
            query = query.replace("user_id = ?", "user_id = :user_id")
            params = {"user_id": str(current_user.id), **dict(enumerate(params))}
        
        # Execute query
        result = db.execute(text(query), params if isinstance(params, dict) else dict(enumerate(params)))
        
        # Handle different query types
        if query.lower().strip().startswith("select"):
            rows = []
            for row in result:
                rows.append(dict(row._mapping))
            return {"rows": rows}
        else:
            # For INSERT, UPDATE, DELETE
            db.commit()
            return {"rows": [], "affected": result.rowcount}
            
    except Exception as e:
        logger.error(f"Query execution error: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query execution failed: {str(e)}"
        )

@router.post("/transaction")
def execute_transaction(
    request: TransactionRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Execute multiple queries in a transaction."""
    # Validate all queries first
    for query_req in request.queries:
        if not validate_query(query_req.query):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="One or more queries not allowed for security reasons"
            )
    
    try:
        results = []
        
        # Execute queries in transaction
        for query_req in request.queries:
            query = query_req.query
            params = query_req.params or []
            
            # Add user context if needed
            if "user_id" in query and "user_id" not in [p for p in params if isinstance(p, dict)]:
                query = query.replace("user_id = ?", "user_id = :user_id")
                params = {"user_id": str(current_user.id), **dict(enumerate(params))}
            
            result = db.execute(text(query), params if isinstance(params, dict) else dict(enumerate(params)))
            
            if query.lower().strip().startswith("select"):
                rows = []
                for row in result:
                    rows.append(dict(row._mapping))
                results.append({"rows": rows})
            else:
                results.append({"rows": [], "affected": result.rowcount})
        
        # Commit transaction
        db.commit()
        
        return {"results": results}
        
    except Exception as e:
        logger.error(f"Transaction execution error: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transaction failed: {str(e)}"
        )