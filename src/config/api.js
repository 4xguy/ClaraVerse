// API configuration for different environments
export const getApiBaseUrl = () => {
  // Check if we're in Electron environment
  if (window.electron) {
    return null; // Let the API service auto-detect
  }
  
  // Check for environment variable first
  if (import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL;
  }
  
  // Default to Railway internal URL if available
  if (import.meta.env.VITE_RAILWAY_BACKEND_URL) {
    return import.meta.env.VITE_RAILWAY_BACKEND_URL;
  }
  
  // Fallback to localhost for development
  if (import.meta.env.DEV) {
    return 'http://localhost:5000';
  }
  
  // In production without backend URL, return null
  return null;
};

export const isBackendAvailable = () => {
  return window.electron || !!getApiBaseUrl();
};