# Running ClaraVerse Locally

## Prerequisites

- Docker and Docker Compose installed
- Node.js 18+ and npm (for development without Docker)
- Git

## Quick Start with Docker Compose

1. **Clone the repository** (if you haven't already):
   ```bash
   git clone <your-repo-url>
   cd ClaraVerse
   ```

2. **Environment Setup**:
   - The `.env` file has been created with default values
   - Modify the `.env` file if you need different passwords or ports
   - Add your OpenAI API key if you want to use OpenAI models

3. **Start all services**:
   ```bash
   docker-compose up -d
   ```

   This will start:
   - PostgreSQL database with pgvector extension (port 5432)
   - Python backend API (port 5000)
   - Frontend web application (port 3000)

4. **Check services are running**:
   ```bash
   docker-compose ps
   ```

5. **Access the application**:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:5000
   - API Docs: http://localhost:5000/docs

## Development Setup (Without Docker)

If you prefer to run services individually for development:

### 1. Start PostgreSQL with Docker:
```bash
docker-compose up -d postgres
```

### 2. Run the Python backend:
```bash
cd py_backend
pip install -r requirements.txt
python main.py
```

### 3. Run the frontend:
```bash
npm install
npm run dev
```

The frontend will be available at http://localhost:5173 (Vite's default port)

## Stopping Services

To stop all services:
```bash
docker-compose down
```

To stop and remove all data (including database):
```bash
docker-compose down -v
```

## Troubleshooting

1. **Port conflicts**: If you get port binding errors, check the `.env` file and change the ports:
   - `DB_PORT` for PostgreSQL
   - `BACKEND_PORT` for the Python API
   - `PORT` for the frontend

2. **Database connection errors**: Ensure PostgreSQL is fully started before the backend:
   ```bash
   docker-compose logs postgres
   ```

3. **Frontend can't connect to backend**: Make sure the backend is running and accessible:
   ```bash
   curl http://localhost:5000/health
   ```

4. **View logs**:
   ```bash
   docker-compose logs -f [service_name]
   ```
   Where `[service_name]` can be `postgres`, `backend`, or `frontend`

## First Time Setup

On first run, the database will be automatically initialized with:
- Required extensions (pgvector, uuid-ossp)
- Auth tables for user management
- Application tables
- Vector storage tables
- Storage tables

No manual database setup is required!