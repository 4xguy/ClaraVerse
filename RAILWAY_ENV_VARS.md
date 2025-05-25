# Railway Environment Variables Configuration

This document outlines the environment variables needed for deploying ClaraVerse on Railway.

## Required Environment Variables

### Frontend Variables

These environment variables should be set in your Railway frontend service:

```bash
# Supabase Configuration (Optional - app works without it)
VITE_SUPABASE_URL=your_supabase_project_url
VITE_SUPABASE_ANON_KEY=your_supabase_anon_key

# Backend API URL (Optional - only if deploying backend)
VITE_RAILWAY_BACKEND_URL=https://your-backend-service.railway.app
# or
VITE_API_URL=https://your-backend-service.railway.app
```

### Backend Variables (if deploying Python backend)

These environment variables should be set in your Railway backend service:

```bash
# Port configuration (Railway provides this automatically)
PORT=5000

# OpenAI API Key (if using OpenAI features)
OPENAI_API_KEY=your_openai_api_key

# Other API keys as needed
HUGGINGFACE_API_KEY=your_huggingface_api_key
```

## How to Set Environment Variables in Railway

1. Go to your Railway project dashboard
2. Select the service (frontend or backend)
3. Click on the "Variables" tab
4. Click "Add Variable"
5. Enter the variable name and value
6. Railway will automatically restart your service with the new variables

## Important Notes

- The app is designed to work without Supabase configuration. If `VITE_SUPABASE_ANON_KEY` is not provided, it will use a dummy client that prevents crashes.
- The frontend can run standalone without the backend. Features requiring the backend will be disabled.
- Never commit sensitive API keys to your repository. Always use environment variables.
- Railway automatically provides some environment variables like `PORT` and `RAILWAY_STATIC_URL`.

## Deployment without Backend

If you're only deploying the frontend:
- Don't set `VITE_RAILWAY_BACKEND_URL` or `VITE_API_URL`
- The app will detect there's no backend and disable features that require it

## Security Considerations

- Always use HTTPS URLs for production
- Keep your API keys secure and rotate them regularly
- Use Railway's private networking for internal service communication when possible