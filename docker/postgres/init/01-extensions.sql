-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";

-- Create schemas
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS storage;
CREATE SCHEMA IF NOT EXISTS vectors;
CREATE SCHEMA IF NOT EXISTS app;

-- Grant permissions
GRANT ALL ON SCHEMA auth TO postgres;
GRANT ALL ON SCHEMA storage TO postgres;
GRANT ALL ON SCHEMA vectors TO postgres;
GRANT ALL ON SCHEMA app TO postgres;