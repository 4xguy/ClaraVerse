// This client communicates with the backend API instead of directly connecting to PostgreSQL
// Direct database connections from browser are not possible/secure

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

export class DatabaseClient {
  private static instance: DatabaseClient;
  private authToken: string | null = null;

  private constructor() {
    // Get auth token from localStorage
    this.authToken = localStorage.getItem('auth_token');
  }

  public static getInstance(): DatabaseClient {
    if (!DatabaseClient.instance) {
      DatabaseClient.instance = new DatabaseClient();
    }
    return DatabaseClient.instance;
  }

  // Set auth token
  setAuthToken(token: string | null) {
    this.authToken = token;
  }

  // Make API request
  private async apiRequest(endpoint: string, options: RequestInit = {}): Promise<any> {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers
    };

    if (this.authToken) {
      headers['Authorization'] = `Bearer ${this.authToken}`;
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

  // Execute a query through the backend API
  async query<T = any>(text: string, params?: any[]): Promise<T[]> {
    try {
      const result = await this.apiRequest('/api/db/query', {
        method: 'POST',
        body: JSON.stringify({ query: text, params })
      });
      return result.rows || [];
    } catch (error) {
      console.error('Database query error:', error);
      throw error;
    }
  }

  // Execute a query and return the first row
  async queryOne<T = any>(text: string, params?: any[]): Promise<T | null> {
    const rows = await this.query<T>(text, params);
    return rows[0] || null;
  }

  // Execute a transaction through the backend API
  async transaction<T>(queries: Array<{ query: string; params?: any[] }>): Promise<T> {
    try {
      const result = await this.apiRequest('/api/db/transaction', {
        method: 'POST',
        body: JSON.stringify({ queries })
      });
      return result;
    } catch (error) {
      console.error('Transaction error:', error);
      throw error;
    }
  }

  // Health check
  async healthCheck(): Promise<boolean> {
    try {
      const result = await this.apiRequest('/api/health');
      return result.status === 'ok';
    } catch (error) {
      return false;
    }
  }
}

// Export singleton instance
export const db = DatabaseClient.getInstance();