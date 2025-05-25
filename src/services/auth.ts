// Authentication service that communicates with the backend API
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

// Types
interface User {
  id: string;
  email: string;
  email_verified: boolean;
  created_at: Date;
  updated_at: Date;
  metadata: any;
}

interface AuthResult {
  user: User;
  token: string;
  refreshToken: string;
}

export class AuthService {
  private static instance: AuthService;

  private constructor() {}

  public static getInstance(): AuthService {
    if (!AuthService.instance) {
      AuthService.instance = new AuthService();
    }
    return AuthService.instance;
  }

  // Make API request
  private async apiRequest(endpoint: string, options: RequestInit = {}): Promise<any> {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers
      }
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(error || `HTTP error ${response.status}`);
    }

    return response.json();
  }

  // Sign up a new user
  async signUp(email: string, password: string, metadata?: any): Promise<AuthResult> {
    try {
      const result = await this.apiRequest('/api/auth/signup', {
        method: 'POST',
        body: JSON.stringify({ email, password, metadata })
      });

      // Store token
      localStorage.setItem('auth_token', result.token);
      localStorage.setItem('refresh_token', result.refreshToken);

      // Update database client token
      const { db } = await import('../db/pgClient');
      db.setAuthToken(result.token);

      return result;
    } catch (error) {
      console.error('Sign up error:', error);
      throw error;
    }
  }

  // Sign in an existing user
  async signIn(email: string, password: string): Promise<AuthResult> {
    try {
      const result = await this.apiRequest('/api/auth/signin', {
        method: 'POST',
        body: JSON.stringify({ email, password })
      });

      // Store token
      localStorage.setItem('auth_token', result.token);
      localStorage.setItem('refresh_token', result.refreshToken);

      // Update database client token
      const { db } = await import('../db/pgClient');
      db.setAuthToken(result.token);

      return result;
    } catch (error) {
      console.error('Sign in error:', error);
      throw error;
    }
  }

  // Sign out a user
  async signOut(token: string): Promise<void> {
    try {
      await this.apiRequest('/api/auth/signout', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      // Clear tokens
      localStorage.removeItem('auth_token');
      localStorage.removeItem('refresh_token');

      // Clear database client token
      const { db } = await import('../db/pgClient');
      db.setAuthToken(null);
    } catch (error) {
      console.error('Sign out error:', error);
      // Clear tokens even if API call fails
      localStorage.removeItem('auth_token');
      localStorage.removeItem('refresh_token');
      throw error;
    }
  }

  // Validate a session token
  async validateSession(token: string): Promise<User | null> {
    try {
      const result = await this.apiRequest('/api/auth/validate', {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      return result.user;
    } catch (error) {
      console.error('Session validation error:', error);
      return null;
    }
  }

  // Refresh access token
  async refreshToken(refreshToken: string): Promise<AuthResult> {
    try {
      const result = await this.apiRequest('/api/auth/refresh', {
        method: 'POST',
        body: JSON.stringify({ refreshToken })
      });

      // Update tokens
      localStorage.setItem('auth_token', result.token);
      localStorage.setItem('refresh_token', result.refreshToken);

      // Update database client token
      const { db } = await import('../db/pgClient');
      db.setAuthToken(result.token);

      return result;
    } catch (error) {
      console.error('Token refresh error:', error);
      throw error;
    }
  }

  // Update user metadata
  async updateUserMetadata(userId: string, metadata: any): Promise<User | null> {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('Not authenticated');
      }

      const result = await this.apiRequest(`/api/auth/users/${userId}/metadata`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ metadata })
      });

      return result.user;
    } catch (error) {
      console.error('Update metadata error:', error);
      throw error;
    }
  }

  // Get current user
  async getCurrentUser(): Promise<User | null> {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        return null;
      }

      return await this.validateSession(token);
    } catch (error) {
      console.error('Get current user error:', error);
      return null;
    }
  }

  // Check if user is authenticated
  isAuthenticated(): boolean {
    return !!localStorage.getItem('auth_token');
  }
}

// Export singleton instance
export const authService = AuthService.getInstance();