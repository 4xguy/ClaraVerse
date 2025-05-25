# Railway Deployment Guide for Clara

This guide explains how to deploy Clara on Railway with separate frontend and backend services.

## Architecture

```
┌─────────────────────┐     ┌─────────────────────┐
│   Frontend Service  │────▶│   Backend Service   │
│   (React + Nginx)   │     │   (Python FastAPI)  │
│   Public Domain     │     │   Internal Only     │
└─────────────────────┘     └─────────────────────┘
         ▲                           ▲
         │                           │
         │                           │
    Public Traffic            Railway Internal
                                Network
```

## Method 1: Using Railway Dashboard (Recommended)

### Step 1: Deploy Backend Service

1. Create a new Railway project or use existing one
2. Click "New Service" → "GitHub Repo"
3. Select your repository
4. Configure the service:
   - **Service Name**: `backend`
   - **Root Directory**: `/py_backend`
   - **Start Command**: Leave empty (uses Dockerfile)
   
5. Add environment variables:
   ```
   PORT=5000
   HOST=0.0.0.0
   ```

6. Deploy and wait for it to be ready
7. Note the internal domain (e.g., `backend.railway.internal`)

### Step 2: Deploy Frontend Service

1. In the same project, click "New Service" → "GitHub Repo"
2. Select your repository again
3. Configure the service:
   - **Service Name**: `frontend`
   - **Root Directory**: `/` (project root)
   - **Start Command**: Leave empty (uses Dockerfile)

4. Add environment variables:
   ```
   VITE_API_URL=http://backend.railway.internal:5000
   ```
   Replace `backend` with your actual backend service name if different

5. Deploy and wait for it to be ready
6. Add a public domain to the frontend service

## Method 2: Using Railway CLI

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login to Railway
railway login

# Create a new project
railway init

# Deploy backend
railway service create backend
railway link
railway service backend
railway variables set PORT=5000 HOST=0.0.0.0
railway up --dockerfile py_backend/Dockerfile

# Get backend internal URL
railway variables get RAILWAY_PRIVATE_DOMAIN

# Deploy frontend
railway service create frontend
railway link  
railway service frontend
railway variables set VITE_API_URL=http://backend.railway.internal:5000
railway up

# Add public domain to frontend
railway domain
```

## Method 3: Using GitHub Actions

Create `.github/workflows/railway.yml`:

```yaml
name: Deploy to Railway

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Install Railway
        run: npm i -g @railway/cli

      - name: Deploy Backend
        env:
          RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}
        run: |
          railway link ${{ secrets.RAILWAY_PROJECT_ID }}
          railway service backend
          railway up --dockerfile py_backend/Dockerfile

      - name: Deploy Frontend  
        env:
          RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}
        run: |
          railway link ${{ secrets.RAILWAY_PROJECT_ID }}
          railway service frontend
          railway up
```

## Environment Variables

### Backend Service
- `PORT`: 5000 (or any port, Railway internal network allows any port)
- `HOST`: 0.0.0.0 (required for container networking)

### Frontend Service
- `PORT`: (Railway will set this automatically)
- `VITE_API_URL`: http://[backend-service-name].railway.internal:5000

## Troubleshooting

### Frontend can't connect to backend
1. Ensure both services are in the same Railway project
2. Check the backend service name matches in VITE_API_URL
3. Verify backend is running on the correct port

### Blank screen on frontend
1. Check browser console for errors
2. Verify VITE_API_URL is set correctly
3. Check if backend health endpoint responds

### Build failures
1. Ensure all files are committed to Git
2. Check Railway build logs
3. Verify Dockerfile paths are correct

## Local Development with Docker Compose

For local development, use the provided docker-compose.yml:

```bash
docker-compose up
```

This will start both services locally with proper networking.