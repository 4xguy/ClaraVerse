# Supabase to PostgreSQL + PGVector Migration Guide

This guide details the complete process of replacing Supabase with a self-hosted PostgreSQL database with PGVector extension for the ClaraVerse application.

## Overview

### Current State (Supabase)
- Authentication via Supabase Auth
- Data storage in Supabase PostgreSQL
- Real-time subscriptions (if used)
- Storage buckets for files
- Row Level Security (RLS) policies

### Target State (PostgreSQL + PGVector)
- Custom authentication system
- PostgreSQL with PGVector extension
- Vector embeddings for RAG functionality
- File storage alternatives (local/S3/MinIO)
- Application-level security

## Pre-Migration Checklist

- [ ] Audit all Supabase usage in the codebase
- [ ] Document current database schema
- [ ] List all authentication flows
- [ ] Identify file storage usage
- [ ] Note any real-time features
- [ ] Plan downtime window (if needed)

## Step-by-Step Migration Process

### Phase 1: Analysis and Planning

#### 1.1 Audit Supabase Usage
Search for all Supabase references:
```bash
# Files to check
grep -r "supabase" --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" .
grep -r "@supabase" --include="*.json" .
grep -r "SUPABASE" --include="*.env*" .
```

Key files to examine:
- `/src/supabaseClient.ts` - Main client configuration
- `/src/components/**/*.tsx` - Component usage
- `/src/services/**/*.ts` - Service layer usage
- `/src/utils/**/*.ts` - Utility functions

#### 1.2 Document Current Schema
Extract and document:
- Tables and their relationships
- Indexes
- RLS policies
- Functions and triggers
- Storage buckets

### Phase 2: Database Setup

#### 2.1 PostgreSQL + PGVector Installation

**Docker Compose Setup:**
```yaml
# docker-compose.pgvector.yml
version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: clara
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: claraverse
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-scripts:/docker-entrypoint-initdb.d
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U clara"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

**Initialization Script:**
```sql
-- /init-scripts/01-init.sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";

-- Create schemas
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS storage;
CREATE SCHEMA IF NOT EXISTS vectors;
```

#### 2.2 Schema Migration

**Core Tables:**
```sql
-- Users table (replacing Supabase Auth)
CREATE TABLE auth.users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    email_verified BOOLEAN DEFAULT FALSE,
    encrypted_password VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Sessions table
CREATE TABLE auth.sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Vector storage for RAG
CREATE TABLE vectors.embeddings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    content TEXT NOT NULL,
    embedding vector(1536), -- OpenAI embedding dimension
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_embeddings_vector ON vectors.embeddings 
USING ivfflat (embedding vector_cosine_ops);
```

### Phase 3: Code Migration

#### 3.1 Database Client Setup

**Create new database client:**
```typescript
// /src/db/pgClient.ts
import { Pool } from 'pg';
import pgvector from 'pgvector/pg';

export class DatabaseClient {
  private pool: Pool;

  constructor() {
    this.pool = new Pool({
      host: process.env.DB_HOST || 'localhost',
      port: parseInt(process.env.DB_PORT || '5432'),
      database: process.env.DB_NAME || 'claraverse',
      user: process.env.DB_USER || 'clara',
      password: process.env.DB_PASSWORD,
    });

    // Register pgvector type
    pgvector.registerType(this.pool);
  }

  async query(text: string, params?: any[]) {
    return this.pool.query(text, params);
  }

  async transaction(callback: (client: any) => Promise<void>) {
    const client = await this.pool.connect();
    try {
      await client.query('BEGIN');
      await callback(client);
      await client.query('COMMIT');
    } catch (e) {
      await client.query('ROLLBACK');
      throw e;
    } finally {
      client.release();
    }
  }
}
```

#### 3.2 Authentication Migration

**Replace Supabase Auth:**
```typescript
// /src/services/auth.ts
import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';
import { DatabaseClient } from '../db/pgClient';

export class AuthService {
  constructor(private db: DatabaseClient) {}

  async signUp(email: string, password: string) {
    const hashedPassword = await bcrypt.hash(password, 10);
    
    const result = await this.db.query(
      'INSERT INTO auth.users (email, encrypted_password) VALUES ($1, $2) RETURNING *',
      [email, hashedPassword]
    );
    
    return this.createSession(result.rows[0]);
  }

  async signIn(email: string, password: string) {
    const result = await this.db.query(
      'SELECT * FROM auth.users WHERE email = $1',
      [email]
    );
    
    if (!result.rows[0]) {
      throw new Error('Invalid credentials');
    }
    
    const validPassword = await bcrypt.compare(
      password, 
      result.rows[0].encrypted_password
    );
    
    if (!validPassword) {
      throw new Error('Invalid credentials');
    }
    
    return this.createSession(result.rows[0]);
  }

  private async createSession(user: any) {
    const token = jwt.sign(
      { userId: user.id, email: user.email },
      process.env.JWT_SECRET!,
      { expiresIn: '7d' }
    );
    
    await this.db.query(
      'INSERT INTO auth.sessions (user_id, token, expires_at) VALUES ($1, $2, $3)',
      [user.id, token, new Date(Date.now() + 7 * 24 * 60 * 60 * 1000)]
    );
    
    return { user, token };
  }
}
```

#### 3.3 Vector Storage Implementation

**RAG functionality with PGVector:**
```typescript
// /src/services/vectorStore.ts
import { DatabaseClient } from '../db/pgClient';
import { encode } from 'gpt-3-encoder';

export class VectorStore {
  constructor(
    private db: DatabaseClient,
    private embeddingService: EmbeddingService
  ) {}

  async addDocument(content: string, metadata: any = {}) {
    // Generate embedding
    const embedding = await this.embeddingService.createEmbedding(content);
    
    // Store in database
    const result = await this.db.query(
      `INSERT INTO vectors.embeddings (content, embedding, metadata) 
       VALUES ($1, $2, $3) RETURNING id`,
      [content, pgvector.toSql(embedding), metadata]
    );
    
    return result.rows[0].id;
  }

  async search(query: string, limit: number = 5) {
    // Generate query embedding
    const queryEmbedding = await this.embeddingService.createEmbedding(query);
    
    // Perform vector similarity search
    const result = await this.db.query(
      `SELECT id, content, metadata, 
              embedding <=> $1 as distance
       FROM vectors.embeddings
       ORDER BY embedding <=> $1
       LIMIT $2`,
      [pgvector.toSql(queryEmbedding), limit]
    );
    
    return result.rows;
  }

  async deleteDocument(id: string) {
    await this.db.query(
      'DELETE FROM vectors.embeddings WHERE id = $1',
      [id]
    );
  }
}
```

#### 3.4 Storage Migration

**File storage options:**

1. **Local Storage (Development):**
```typescript
// /src/services/localStorage.ts
import fs from 'fs/promises';
import path from 'path';
import crypto from 'crypto';

export class LocalStorage {
  private basePath: string;

  constructor(basePath: string = './storage') {
    this.basePath = basePath;
  }

  async upload(file: Buffer, filename: string): Promise<string> {
    const hash = crypto.createHash('sha256').update(file).digest('hex');
    const ext = path.extname(filename);
    const storedName = `${hash}${ext}`;
    const filePath = path.join(this.basePath, storedName);
    
    await fs.mkdir(path.dirname(filePath), { recursive: true });
    await fs.writeFile(filePath, file);
    
    return storedName;
  }

  async download(filename: string): Promise<Buffer> {
    return fs.readFile(path.join(this.basePath, filename));
  }

  async delete(filename: string): Promise<void> {
    await fs.unlink(path.join(this.basePath, filename));
  }
}
```

2. **S3-Compatible Storage (Production):**
```typescript
// /src/services/s3Storage.ts
import { S3Client, PutObjectCommand, GetObjectCommand } from '@aws-sdk/client-s3';

export class S3Storage {
  private client: S3Client;
  private bucket: string;

  constructor() {
    this.client = new S3Client({
      endpoint: process.env.S3_ENDPOINT,
      region: process.env.S3_REGION || 'us-east-1',
      credentials: {
        accessKeyId: process.env.S3_ACCESS_KEY!,
        secretAccessKey: process.env.S3_SECRET_KEY!,
      },
    });
    this.bucket = process.env.S3_BUCKET!;
  }

  async upload(file: Buffer, key: string): Promise<string> {
    await this.client.send(new PutObjectCommand({
      Bucket: this.bucket,
      Key: key,
      Body: file,
    }));
    return key;
  }
}
```

### Phase 4: Component Updates

#### 4.1 Update React Components

**Replace Supabase hooks:**
```typescript
// /src/hooks/useAuth.ts
import { useState, useEffect, createContext, useContext } from 'react';
import { authService } from '../services';

const AuthContext = createContext<any>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check for existing session
    const token = localStorage.getItem('auth_token');
    if (token) {
      authService.validateSession(token)
        .then(setUser)
        .catch(() => localStorage.removeItem('auth_token'))
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const signIn = async (email: string, password: string) => {
    const { user, token } = await authService.signIn(email, password);
    localStorage.setItem('auth_token', token);
    setUser(user);
    return user;
  };

  const signOut = async () => {
    await authService.signOut();
    localStorage.removeItem('auth_token');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, signIn, signOut, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
```

### Phase 5: Migration Scripts

#### 5.1 Data Migration Script
```typescript
// /scripts/migrate-supabase-data.ts
import { createClient } from '@supabase/supabase-js';
import { DatabaseClient } from '../src/db/pgClient';

async function migrateData() {
  // Connect to Supabase
  const supabase = createClient(
    process.env.OLD_SUPABASE_URL!,
    process.env.OLD_SUPABASE_KEY!
  );
  
  // Connect to new database
  const pgClient = new DatabaseClient();
  
  // Migrate users
  const { data: users } = await supabase.auth.admin.listUsers();
  for (const user of users) {
    await pgClient.query(
      `INSERT INTO auth.users (id, email, email_verified, metadata, created_at) 
       VALUES ($1, $2, $3, $4, $5)
       ON CONFLICT (id) DO NOTHING`,
      [user.id, user.email, user.email_confirmed_at != null, 
       user.user_metadata, user.created_at]
    );
  }
  
  // Migrate other tables...
  console.log('Migration completed');
}
```

### Phase 6: Testing

#### 6.1 Test Checklist
- [ ] Authentication flows (sign up, sign in, sign out)
- [ ] Session management
- [ ] Vector search functionality
- [ ] File upload/download
- [ ] Data integrity after migration
- [ ] Performance benchmarks
- [ ] Error handling
- [ ] Rollback procedures

#### 6.2 Integration Tests
```typescript
// /tests/integration/auth.test.ts
describe('Authentication', () => {
  test('user can sign up', async () => {
    const result = await authService.signUp('test@example.com', 'password');
    expect(result.user.email).toBe('test@example.com');
    expect(result.token).toBeDefined();
  });
  
  test('user can sign in', async () => {
    const result = await authService.signIn('test@example.com', 'password');
    expect(result.token).toBeDefined();
  });
});
```

### Phase 7: Deployment

#### 7.1 Environment Variables
```env
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=claraverse
DB_USER=clara
DB_PASSWORD=secure_password

# Auth
JWT_SECRET=your-secret-key
BCRYPT_ROUNDS=10

# Storage (choose one)
STORAGE_TYPE=local # or 's3'
STORAGE_PATH=./storage

# S3 (if using S3)
S3_ENDPOINT=https://s3.amazonaws.com
S3_BUCKET=claraverse
S3_ACCESS_KEY=your-key
S3_SECRET_KEY=your-secret

# OpenAI (for embeddings)
OPENAI_API_KEY=your-api-key
```

#### 7.2 Railway Deployment Update
```yaml
# docker-compose.railway.yml update
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: ${DB_NAME}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      
  backend:
    # ... existing config
    environment:
      - DB_HOST=postgres
      - DB_PORT=5432
      - DB_NAME=${DB_NAME}
      - DB_USER=${DB_USER}
      - DB_PASSWORD=${DB_PASSWORD}
    depends_on:
      - postgres
```

### Phase 8: Rollback Plan

#### 8.1 Backup Current State
- Export all Supabase data
- Document current configuration
- Create database snapshots

#### 8.2 Rollback Steps
1. Restore Supabase client configuration
2. Update environment variables
3. Revert code changes
4. Restore data if needed

## Post-Migration Tasks

- [ ] Update documentation
- [ ] Train team on new system
- [ ] Monitor performance
- [ ] Set up backups
- [ ] Configure monitoring/alerts
- [ ] Update CI/CD pipelines

## Benefits of Migration

1. **Full Control**: Complete control over database and authentication
2. **Cost Savings**: No Supabase subscription fees
3. **Custom Features**: Implement custom authentication flows
4. **Vector Search**: Native PGVector support for advanced RAG
5. **Performance**: Optimize queries for specific use cases
6. **Privacy**: All data stays in your infrastructure

## Potential Challenges

1. **Maintenance**: Need to manage database backups, updates
2. **Security**: Implement security best practices manually
3. **Real-time**: Need alternative for Supabase real-time features
4. **Development Time**: Initial migration effort
5. **Monitoring**: Set up own monitoring infrastructure

## Conclusion

This migration guide provides a comprehensive approach to replacing Supabase with PostgreSQL + PGVector. The process involves careful planning, systematic implementation, and thorough testing to ensure a smooth transition while maintaining all functionality.