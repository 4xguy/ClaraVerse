// Vector store service that communicates with the backend API
import { OpenAI } from 'openai';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

// Types
interface VectorDocument {
  id: string;
  content: string;
  embedding?: number[];
  metadata: any;
  created_at: Date;
  updated_at: Date;
}

interface SearchResult {
  id: string;
  content: string;
  metadata: any;
  distance: number;
  document_name?: string;
}

export class VectorStore {
  private static instance: VectorStore;
  private openai: OpenAI | null = null;

  private constructor() {
    const apiKey = import.meta.env.VITE_OPENAI_API_KEY;
    if (apiKey) {
      this.openai = new OpenAI({ 
        apiKey,
        dangerouslyAllowBrowser: true // Note: In production, embeddings should be created server-side
      });
    }
  }

  public static getInstance(): VectorStore {
    if (!VectorStore.instance) {
      VectorStore.instance = new VectorStore();
    }
    return VectorStore.instance;
  }

  // Make API request
  private async apiRequest(endpoint: string, options: RequestInit = {}): Promise<any> {
    const token = localStorage.getItem('auth_token');
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`API Error: ${response.status} - ${error}`);
    }

    return response.json();
  }

  // Create embedding using OpenAI (client-side for development, should be server-side in production)
  async createEmbedding(text: string): Promise<number[]> {
    // First try to use backend API
    try {
      const result = await this.apiRequest('/api/vectors/embed', {
        method: 'POST',
        body: JSON.stringify({ text })
      });
      return result.embedding;
    } catch (error) {
      // Fallback to client-side OpenAI if backend is not available
      if (this.openai) {
        try {
          const response = await this.openai.embeddings.create({
            model: 'text-embedding-ada-002',
            input: text,
          });
          return response.data[0].embedding;
        } catch (openaiError) {
          console.error('OpenAI embedding error:', openaiError);
          throw openaiError;
        }
      }
      throw new Error('No embedding service available');
    }
  }

  // Add a document to the vector store
  async addDocument(content: string, metadata: any = {}): Promise<string> {
    try {
      const result = await this.apiRequest('/api/vectors/documents', {
        method: 'POST',
        body: JSON.stringify({ content, metadata })
      });
      return result.id;
    } catch (error) {
      console.error('Add document error:', error);
      throw error;
    }
  }

  // Add a large document with chunking
  async addLargeDocument(
    name: string,
    content: string,
    type: string,
    metadata: any = {}
  ): Promise<string> {
    try {
      const result = await this.apiRequest('/api/vectors/documents/large', {
        method: 'POST',
        body: JSON.stringify({ name, content, type, metadata })
      });
      return result.id;
    } catch (error) {
      console.error('Add large document error:', error);
      throw error;
    }
  }

  // Search for similar documents
  async search(
    query: string,
    limit: number = 5,
    threshold: number = 0.8
  ): Promise<SearchResult[]> {
    try {
      const results = await this.apiRequest('/api/vectors/search', {
        method: 'POST',
        body: JSON.stringify({ query, limit, threshold })
      });
      return results;
    } catch (error) {
      console.error('Search error:', error);
      throw error;
    }
  }

  // Search in document chunks
  async searchDocumentChunks(
    query: string,
    limit: number = 5,
    threshold: number = 0.8
  ): Promise<SearchResult[]> {
    try {
      const results = await this.apiRequest('/api/vectors/search/chunks', {
        method: 'POST',
        body: JSON.stringify({ query, limit, threshold })
      });
      return results;
    } catch (error) {
      console.error('Search document chunks error:', error);
      throw error;
    }
  }

  // Delete a document
  async deleteDocument(id: string): Promise<void> {
    try {
      await this.apiRequest(`/api/vectors/documents/${id}`, {
        method: 'DELETE'
      });
    } catch (error) {
      console.error('Delete document error:', error);
      throw error;
    }
  }

  // Delete a large document and its chunks
  async deleteLargeDocument(id: string): Promise<void> {
    try {
      await this.apiRequest(`/api/vectors/documents/large/${id}`, {
        method: 'DELETE'
      });
    } catch (error) {
      console.error('Delete large document error:', error);
      throw error;
    }
  }

  // Get user's documents
  async getUserDocuments(): Promise<VectorDocument[]> {
    try {
      const documents = await this.apiRequest('/api/vectors/documents', {
        method: 'GET'
      });
      return documents;
    } catch (error) {
      console.error('Get user documents error:', error);
      throw error;
    }
  }

  // Upload file for vectorization
  async uploadFile(file: File): Promise<string> {
    try {
      const formData = new FormData();
      formData.append('file', file);

      const token = localStorage.getItem('auth_token');
      const headers: HeadersInit = {};
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const response = await fetch(`${API_BASE_URL}/api/vectors/upload`, {
        method: 'POST',
        headers,
        body: formData
      });

      if (!response.ok) {
        const error = await response.text();
        throw new Error(`Upload failed: ${error}`);
      }

      const result = await response.json();
      return result.id;
    } catch (error) {
      console.error('Upload file error:', error);
      throw error;
    }
  }

  // Get vector database statistics
  async getStats(): Promise<{
    total_documents: number;
    total_chunks: number;
    average_chunk_size: number;
  }> {
    try {
      const stats = await this.apiRequest('/api/vectors/stats', {
        method: 'GET'
      });
      return stats;
    } catch (error) {
      console.error('Get stats error:', error);
      throw error;
    }
  }
}

// Export singleton instance
export const vectorStore = VectorStore.getInstance();