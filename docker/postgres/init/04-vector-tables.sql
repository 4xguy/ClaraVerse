-- Vector embeddings table for RAG
CREATE TABLE vectors.embeddings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding vector(1536), -- OpenAI embedding dimension
    model VARCHAR(100) DEFAULT 'text-embedding-ada-002',
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Documents table for RAG source tracking
CREATE TABLE vectors.documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL,
    size INTEGER,
    content TEXT,
    file_path VARCHAR(500),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Document chunks for better RAG performance
CREATE TABLE vectors.document_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES vectors.documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for vector similarity search
CREATE INDEX idx_embeddings_vector ON vectors.embeddings 
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX idx_document_chunks_vector ON vectors.document_chunks 
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Regular indexes
CREATE INDEX idx_embeddings_user_id ON vectors.embeddings(user_id);
CREATE INDEX idx_documents_user_id ON vectors.documents(user_id);
CREATE INDEX idx_document_chunks_document_id ON vectors.document_chunks(document_id);

-- Add update triggers
CREATE TRIGGER update_vectors_embeddings_updated_at BEFORE UPDATE ON vectors.embeddings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_vectors_documents_updated_at BEFORE UPDATE ON vectors.documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();