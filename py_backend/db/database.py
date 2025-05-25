import os
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Database configuration from environment variables
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "claraverse")
DB_USER = os.getenv("DB_USER", "clara")
DB_PASSWORD = os.getenv("DB_PASSWORD", "clara_secure_password")

# Construct database URL
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Create engine with pgvector extension
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Verify connections before using
    echo=False  # Set to True for SQL debugging
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()

# Dependency to get DB session
def get_db():
    """
    Get database session.
    Usage in FastAPI:
    
    @app.get("/items/")
    def read_items(db: Session = Depends(get_db)):
        return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Initialize pgvector extension
def init_pgvector():
    """Initialize pgvector extension in the database."""
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        logger.info("pgvector extension initialized")
    except Exception as e:
        logger.error(f"Failed to initialize pgvector: {e}")
        raise

# Test database connection
def test_connection():
    """Test database connection."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            logger.info("Database connection successful")
            return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False

# Initialize database
def init_db():
    """Initialize database with required extensions and tables."""
    try:
        # Test connection
        if not test_connection():
            raise Exception("Cannot connect to database")
        
        # Initialize pgvector
        init_pgvector()
        
        # Import all models to register them with Base
        from .models import User, Session, RefreshToken, Document, Embedding
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized successfully")
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise