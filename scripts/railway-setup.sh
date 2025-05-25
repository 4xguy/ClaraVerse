#!/bin/bash

# Railway Multi-Service Setup Script
# This script helps set up Clara with separate frontend and backend services on Railway

echo "=== Railway Multi-Service Setup for Clara ==="
echo ""
echo "This script will guide you through setting up Clara on Railway with:"
echo "- Backend service (Python API)"
echo "- Frontend service (React + Nginx)"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Prerequisites:${NC}"
echo "1. Railway CLI installed (npm install -g @railway/cli)"
echo "2. Logged into Railway (railway login)"
echo "3. A Railway project created"
echo ""

read -p "Press Enter to continue or Ctrl+C to exit..."

echo ""
echo -e "${GREEN}Step 1: Creating Backend Service${NC}"
echo "Run these commands in your terminal:"
echo ""
echo "# Create backend service"
echo "railway service create backend"
echo ""
echo "# Link the backend service"
echo "railway link"
echo "railway service backend"
echo ""
echo "# Set backend environment variables"
echo "railway variables set PORT=5000"
echo "railway variables set HOST=0.0.0.0"
echo ""
echo "# Deploy backend"
echo "railway up --service backend --dockerfile py_backend/Dockerfile"
echo ""

read -p "Press Enter after completing Step 1..."

echo ""
echo -e "${GREEN}Step 2: Get Backend Internal URL${NC}"
echo "Run this command to get the backend's internal URL:"
echo ""
echo "railway variables get RAILWAY_PRIVATE_DOMAIN --service backend"
echo ""
echo "Note this URL (e.g., backend.railway.internal)"
echo ""

read -p "Enter the backend internal domain: " BACKEND_DOMAIN

echo ""
echo -e "${GREEN}Step 3: Creating Frontend Service${NC}"
echo "Run these commands:"
echo ""
echo "# Create frontend service"
echo "railway service create frontend"
echo ""
echo "# Link the frontend service"
echo "railway link"
echo "railway service frontend"
echo ""
echo "# Set frontend environment variables"
echo "railway variables set VITE_API_URL=http://${BACKEND_DOMAIN}:5000"
echo ""
echo "# Deploy frontend"
echo "railway up --service frontend"
echo ""

echo -e "${GREEN}Setup Complete!${NC}"
echo ""
echo "Your services should now be deploying on Railway."
echo "Check the Railway dashboard for deployment status."
echo ""
echo -e "${YELLOW}Important Notes:${NC}"
echo "- Backend runs on internal port 5000"
echo "- Frontend will use Railway's assigned PORT"
echo "- Services communicate via Railway's private network"
echo "- Only frontend needs a public domain"