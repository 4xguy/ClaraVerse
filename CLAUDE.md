# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ClaraVerse is a fully local AI superstack application combining multiple AI capabilities into a single desktop application. It features LLM chat, visual workflow automation, app building, image generation, and code interpretation - all running locally without cloud dependencies.

## Essential Commands

### Development
```bash
npm install          # Install dependencies
npm run dev          # Run web version locally
npm run electron:dev # Run desktop version in development
npm run electron:dev:hot # Run with hot reload
```

### Testing
```bash
npm test            # Run tests once
npm run test:watch  # Run tests in watch mode
npm run test:coverage # Run tests with coverage report
```

### Building
```bash
npm run build        # Build web version
npm run electron:build # Build desktop app for current platform
npm run electron:build-all # Build for all platforms
```

### Linting & Type Checking
```bash
npm run lint        # Run ESLint
npm run typecheck   # Run TypeScript type checking
```

## Architecture Overview

### Component Structure
The application follows a modular architecture with self-contained feature modules:

- **Assistant** (`/src/components/Assistant.tsx`) - Main chat interface with multi-model support, handles streaming responses, image uploads, and RAG integration
- **App Creator** (`/src/components/AppCreator.tsx`) - Visual node-based application builder with drag-and-drop flow creation
- **N8N Integration** (`/src/components/N8N.tsx`) - Embedded workflow automation with 1000+ templates
- **Image Generation** (`/src/components/ImageGen.tsx`) - ComfyUI/Stable Diffusion integration with gallery management
- **UI Builder** (`/src/components/UIBuilder.tsx`) - Visual UI component builder with live preview

### Execution Flow
1. **Node System**: Apps are built as node graphs where each node represents an operation (LLM call, API request, image processing)
2. **Execution Engine** (`/src/ExecutionEngine.tsx`) - Orchestrates node execution, manages data flow between nodes
3. **Node Executors** (`/src/nodeExecutors/`) - Individual executors for each node type handle the actual processing

### State Management
- Uses React Context for global state (Ollama settings, theme)
- IndexedDB for persistent storage of apps, chats, and images
- Local file system for large assets via Electron APIs

### Key Technologies
- **Frontend**: React 18.3 + TypeScript + Vite + Tailwind CSS
- **Desktop**: Electron 35 with context isolation
- **UI Components**: Material-UI, Headless UI, Lucide icons
- **Flow Visualization**: ReactFlow for node-based interfaces
- **Backend Services**: Python FastAPI backend in `/py_backend/`

## Development Guidelines

### Adding New Node Types
1. Create node component in `/src/components/appcreator_components/nodes/`
2. Create executor in `/src/nodeExecutors/`
3. Register in `NodeRegistry.tsx` and `NodeExecutorRegistry.tsx`

### Working with Electron
- Main process code in `/electron/main.ts`
- Preload scripts handle IPC communication
- Use context bridge for secure API exposure

### Python Backend
- FastAPI server in `/py_backend/main.py`
- Handles RAG, speech-to-text, and model APIs
- Runs on port 5000 by default

### Security Considerations
- All Electron windows use context isolation
- No remote module usage
- API keys stored in IndexedDB, never in code
- File system access restricted through preload APIs