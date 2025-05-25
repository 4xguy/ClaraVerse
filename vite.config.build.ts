import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// Build-time configuration for Railway
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  define: {
    // Pass environment variables to the build
    'import.meta.env.VITE_API_URL': JSON.stringify(process.env.VITE_API_URL || ''),
    'import.meta.env.VITE_RAILWAY_BACKEND_URL': JSON.stringify(process.env.VITE_RAILWAY_BACKEND_URL || ''),
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'ui-vendor': ['@mui/material', '@emotion/react', '@emotion/styled'],
          'utils-vendor': ['axios', 'date-fns', 'lodash'],
        },
      },
    },
  },
});