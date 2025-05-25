from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any

from ..db.database import get_db
from ..auth.auth import AuthService, security, get_current_user

router = APIRouter(prefix="/api/auth", tags=["authentication"])

# Request/Response models
class SignUpRequest(BaseModel):
    email: EmailStr
    password: str
    metadata: Optional[Dict[str, Any]] = None

class SignInRequest(BaseModel):
    email: EmailStr
    password: str

class RefreshTokenRequest(BaseModel):
    refreshToken: str

class UpdateMetadataRequest(BaseModel):
    metadata: Dict[str, Any]

class AuthResponse(BaseModel):
    user: Dict[str, Any]
    token: str
    refreshToken: str

@router.post("/signup", response_model=AuthResponse)
def sign_up(request: SignUpRequest, db: Session = Depends(get_db)):
    """Sign up a new user."""
    try:
        # Create user
        user = AuthService.create_user(db, request.email, request.password, request.metadata)
        
        # Create session
        session_data = AuthService.create_session(db, user)
        
        return session_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/signin", response_model=AuthResponse)
def sign_in(request: SignInRequest, db: Session = Depends(get_db)):
    """Sign in an existing user."""
    # Authenticate user
    user = AuthService.authenticate_user(db, request.email, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create session
    session_data = AuthService.create_session(db, user)
    
    return session_data

@router.post("/signout")
def sign_out(credentials: HTTPAuthorizationCredentials = Depends(security), 
             db: Session = Depends(get_db)):
    """Sign out the current user."""
    AuthService.logout(db, credentials.credentials)
    return {"message": "Successfully signed out"}

@router.get("/validate")
def validate_session(current_user = Depends(get_current_user)):
    """Validate the current session and return user info."""
    return {
        "user": {
            "id": str(current_user.id),
            "email": current_user.email,
            "email_verified": current_user.email_verified,
            "created_at": current_user.created_at.isoformat(),
            "updated_at": current_user.updated_at.isoformat(),
            "metadata": current_user.metadata
        }
    }

@router.post("/refresh", response_model=AuthResponse)
def refresh_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Refresh access token using refresh token."""
    try:
        session_data = AuthService.refresh_access_token(db, request.refreshToken)
        return session_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.patch("/users/{user_id}/metadata")
def update_user_metadata(
    user_id: str,
    request: UpdateMetadataRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user metadata."""
    # Check if user is updating their own metadata
    if str(current_user.id) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot update other user's metadata"
        )
    
    # Update metadata
    current_user.metadata = {**current_user.metadata, **request.metadata}
    db.commit()
    db.refresh(current_user)
    
    return {
        "user": {
            "id": str(current_user.id),
            "email": current_user.email,
            "email_verified": current_user.email_verified,
            "created_at": current_user.created_at.isoformat(),
            "updated_at": current_user.updated_at.isoformat(),
            "metadata": current_user.metadata
        }
    }