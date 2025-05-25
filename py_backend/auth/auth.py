import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..db.database import get_db
from ..db.models import User, Session as DBSession, RefreshToken

# Configuration
SECRET_KEY = os.getenv("JWT_SECRET", "your-super-secret-jwt-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 7 * 24 * 60  # 7 days
REFRESH_TOKEN_EXPIRE_DAYS = 30

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer
security = HTTPBearer()

class AuthService:
    """Authentication service for handling user authentication and authorization."""
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def get_password_hash(password: str) -> str:
        """Hash a password."""
        return pwd_context.hash(password)
    
    @staticmethod
    def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def create_refresh_token(data: Dict[str, Any]) -> str:
        """Create a JWT refresh token."""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def decode_token(token: str) -> Dict[str, Any]:
        """Decode and validate a JWT token."""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    @staticmethod
    def create_user(db: Session, email: str, password: str, metadata: Optional[Dict] = None) -> User:
        """Create a new user."""
        # Check if user exists
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already exists"
            )
        
        # Create user
        hashed_password = AuthService.get_password_hash(password)
        user = User(
            email=email,
            encrypted_password=hashed_password,
            metadata=metadata or {}
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    
    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
        """Authenticate a user by email and password."""
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return None
        if not AuthService.verify_password(password, user.encrypted_password):
            return None
        return user
    
    @staticmethod
    def create_session(db: Session, user: User) -> Dict[str, Any]:
        """Create a new session for a user."""
        # Create tokens
        access_token = AuthService.create_access_token(
            data={"sub": str(user.id), "email": user.email}
        )
        refresh_token = AuthService.create_refresh_token(
            data={"sub": str(user.id), "email": user.email}
        )
        
        # Calculate expiration times
        access_expires = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        refresh_expires = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        
        # Store session in database
        db_session = DBSession(
            user_id=user.id,
            token=access_token,
            expires_at=access_expires
        )
        db.add(db_session)
        
        # Store refresh token
        db_refresh = RefreshToken(
            user_id=user.id,
            token=refresh_token,
            expires_at=refresh_expires
        )
        db.add(db_refresh)
        
        db.commit()
        
        return {
            "user": {
                "id": str(user.id),
                "email": user.email,
                "email_verified": user.email_verified,
                "created_at": user.created_at.isoformat(),
                "updated_at": user.updated_at.isoformat(),
                "metadata": user.metadata
            },
            "token": access_token,
            "refreshToken": refresh_token
        }
    
    @staticmethod
    def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), 
                        db: Session = Depends(get_db)) -> User:
        """Get current authenticated user from JWT token."""
        token = credentials.credentials
        
        # Decode token
        payload = AuthService.decode_token(token)
        user_id = payload.get("sub")
        
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            )
        
        # Check if session exists
        session = db.query(DBSession).filter(
            DBSession.token == token,
            DBSession.expires_at > datetime.utcnow()
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired or invalid",
            )
        
        # Get user
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        
        return user
    
    @staticmethod
    def refresh_access_token(db: Session, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token using refresh token."""
        # Decode refresh token
        payload = AuthService.decode_token(refresh_token)
        
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
        
        user_id = payload.get("sub")
        
        # Check if refresh token exists and is valid
        db_refresh = db.query(RefreshToken).filter(
            RefreshToken.token == refresh_token,
            RefreshToken.expires_at > datetime.utcnow()
        ).first()
        
        if not db_refresh:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )
        
        # Get user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        
        # Delete old refresh token
        db.delete(db_refresh)
        
        # Create new session
        return AuthService.create_session(db, user)
    
    @staticmethod
    def logout(db: Session, token: str) -> None:
        """Logout user by deleting session."""
        session = db.query(DBSession).filter(DBSession.token == token).first()
        if session:
            db.delete(session)
            db.commit()

# Dependency to get current user
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), 
                     db: Session = Depends(get_db)) -> User:
    """FastAPI dependency to get current authenticated user."""
    return AuthService.get_current_user(credentials, db)

# Optional: Dependency to get current user or None
def get_current_user_optional(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security), 
                              db: Session = Depends(get_db)) -> Optional[User]:
    """FastAPI dependency to get current authenticated user or None."""
    if not credentials:
        return None
    try:
        return AuthService.get_current_user(credentials, db)
    except HTTPException:
        return None