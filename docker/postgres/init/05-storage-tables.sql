-- File storage metadata
CREATE TABLE storage.files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    bucket VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    size INTEGER,
    mime_type VARCHAR(100),
    storage_path VARCHAR(500) NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Storage buckets
CREATE TABLE storage.buckets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) UNIQUE NOT NULL,
    public BOOLEAN DEFAULT FALSE,
    file_size_limit INTEGER,
    allowed_mime_types TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create default buckets
INSERT INTO storage.buckets (name, public, file_size_limit, allowed_mime_types) VALUES
    ('avatars', true, 5242880, ARRAY['image/jpeg', 'image/png', 'image/gif']),
    ('documents', false, 10485760, ARRAY['application/pdf', 'text/plain', 'application/msword']),
    ('images', false, 20971520, ARRAY['image/jpeg', 'image/png', 'image/gif', 'image/webp']);

-- Create indexes
CREATE INDEX idx_files_user_id ON storage.files(user_id);
CREATE INDEX idx_files_bucket ON storage.files(bucket);
CREATE UNIQUE INDEX idx_files_bucket_name ON storage.files(bucket, name);

-- Add update triggers
CREATE TRIGGER update_storage_files_updated_at BEFORE UPDATE ON storage.files
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_storage_buckets_updated_at BEFORE UPDATE ON storage.buckets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();