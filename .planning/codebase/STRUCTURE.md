# Codebase Structure

**Analysis Date:** 2026-09-10

## Directory Layout

```
Auvyra/
├── backend/                        # Python / FastAPI backend service
│   ├── app/
│   │   ├── ai/                     # AI Gateway & LLM prompt engineering
│   │   ├── api/                    # FastAPI HTTP route controllers
│   │   ├── auth/                   # Authentication service, routes, and JWT guards
│   │   ├── models/                 # Pydantic domain models & schemas
│   │   ├── repositories/           # MongoDB data access layer (Motor)
│   │   ├── services/               # Core business logic orchestrators
│   │   ├── storage/                # Media storage abstractions (local filesystem)
│   │   ├── utils/                  # Serialization and helper utilities
│   │   ├── video/                  # Video engine subsystem (FFmpeg, TTS, composition)
│   │   ├── workers/                # Background async job workers & polling runner
│   │   ├── youtube/                # YouTube Data API v3 client & OAuth scopes
│   │   ├── config.py               # Pydantic BaseSettings & env validation
│   │   ├── database.py             # Motor MongoDB manager & index creation
│   │   └── main.py                 # FastAPI application factory & health routes
│   └── __init__.py
├── frontend/                       # React + Vite + TypeScript frontend application
│   ├── src/
│   │   ├── api/                    # Axios HTTP client & API route bindings
│   │   ├── auth/                   # React AuthContext & ProtectedRoute guard
│   │   ├── components/             # Reusable UI component library
│   │   ├── hooks/                  # Custom React hooks (usePolling)
│   │   ├── pages/                  # Route view components
│   │   ├── types/                  # TypeScript interface definitions
│   │   ├── App.tsx                 # Route declarations & toaster provider
│   │   ├── index.css               # Tailwind CSS declarations
│   │   └── main.tsx                # React DOM mount entry point
│   ├── package.json                # Frontend dependencies and scripts
│   ├── tsconfig.json               # TypeScript compiler configuration
│   └── vite.config.ts              # Vite bundler configuration
├── media/                          # Local directory for generated video/audio files
├── scripts/                        # Development, diagnostic, and automation scripts
├── tests/                          # Automated test suite
│   ├── fixtures/                   # Sample payloads and mock datasets
│   ├── integration/                # End-to-end and API integration tests
│   ├── unit/                       # Component-level unit tests
│   └── conftest.py                 # Pytest test fixtures and harnesses
├── docs/                           # Architecture and specification docs
├── .planning/                      # Planning logs and codebase reference maps
│   └── codebase/                   # Codebase architecture & structure documentation
├── pyproject.toml                  # Python dependencies and tool configs
├── README.md                       # High-level project overview
└── .env.example                    # Template environment variables
```

---

## Directory Purposes

### Backend (`backend/app/`)
- `ai/`: Encapsulates interactions with the local LLM (`Ollama`). Provides `AIGateway` (`backend/app/ai/gateway.py`) for structured JSON extraction with self-healing regex parsers, and `prompts.py` for structured prompts (scripts, hooks, research, analytics).
- `api/`: HTTP endpoints divided cleanly by business capability: `channels.py`, `content.py`, `jobs.py`, `publishing.py`, `research.py`, `videos.py`, `analytics.py`. Validates incoming payloads via Pydantic models.
- `auth/`: Houses JWT-based user authentication, password hashing with bcrypt, Google OAuth redirect handling, and the `require_auth` dependency.
- `models/`: Pydantic data schemas representing domain entities (`user.py`, `channel.py`, `content.py`, `video.py`, `job.py`, `analytics.py`, `auth.py`, `error.py`).
- `repositories/`: Encapsulates all direct database queries using Motor (`AsyncIOMotorDatabase`). Enforces tenant filtering on `user_id` in `backend/app/repositories/base.py`.
- `services/`: Coordinates transactions between repositories, the AI Gateway, YouTube client, and video pipeline.
- `storage/`: Handles media file persistence (`backend/app/storage/local.py`).
- `utils/`: Formatting and BSON/ObjectId document serialization (`backend/app/utils/serializers.py`).
- `video/`: Complete video production pipeline. Contains sub-modules for audio synthesis (`audio/`), subtitle generation (`subtitles/`), clip assembly (`composition/`), media retrieval (`media/`), and FFmpeg rendering (`rendering/`).
- `workers/`: Background job consumers running in an async loop. Extends `BaseWorker` (`backend/app/workers/base.py`) which atomically dequeues jobs from the MongoDB `jobs` collection.
- `youtube/`: YouTube Data API v3 wrapper (`backend/app/youtube/client.py`) supporting OAuth authentication, channel synchronization, and video uploads.

### Frontend (`frontend/src/`)
- `api/`: Contains the global Axios instance with authorization header insertion and token refresh interceptor (`client.ts`), plus typed API calls for auth, channels, content, jobs, research, and videos.
- `auth/`: React context provider (`AuthContext.tsx`) maintaining authentication state, token storage, and route protection wrapper (`ProtectedRoute.tsx`).
- `components/`: UI design system components: `Sidebar.tsx`, `Layout.tsx`, `Card.tsx`, `Modal.tsx`, `ProgressBar.tsx`, `StatusBadge.tsx`, `EmptyState.tsx`.
- `hooks/`: Reusable hooks such as `usePolling.ts` for monitoring asynchronous video and publishing jobs.
- `pages/`: Complete views corresponding to app routes: `Dashboard.tsx`, `Channels.tsx`, `Research.tsx`, `Create.tsx`, `Videos.tsx`, `Publishing.tsx`, `Analytics.tsx`, `Settings.tsx`, `Login.tsx`, `Register.tsx`, `OAuthCallback.tsx`.
- `types/`: Shared TypeScript type declarations matching backend models (`index.ts`).

### Test Suite (`tests/`)
- `unit/`: Fast, isolated tests for components that do not require external services: `test_ai_gateway.py`, `test_config.py`, `test_storage.py`, `test_video_pipeline.py`.
- `integration/`: Workflow and contract tests interacting with Motor/MongoDB: `test_api_auth.py`, `test_api_workflow.py`, `test_health_api.py`, `test_learning_loop.py`, `test_mongodb_isolation.py`.
- `fixtures/`: Test datasets and mock generators (`sample_data.py`).
- `conftest.py`: Common fixtures providing async test clients (`httpx.AsyncClient`), in-memory MongoDB mocks, and authenticated headers.

### Operations & Scripts (`scripts/`)
- `dev.sh`: Helper script starting backend, worker runner, and frontend Vite server concurrently.
- `verify.sh`: Full test and build verification script running backend `pytest` and frontend `tsc`.
- `doctor.py`: System readiness check ensuring MongoDB, Ollama, and FFmpeg prerequisites are satisfied.
- `production_acceptance.py`: Acceptance verification suite for production configuration.

---

## Key File Locations

| Purpose | File Path | Description |
|---------|-----------|-------------|
| **Backend Entry Point** | `backend/app/main.py` | FastAPI application factory, lifespan, CORS, middleware, and route mounting. |
| **Worker Entry Point** | `backend/app/workers/runner.py` | CLI runner for all background workers. |
| **Frontend Entry Point** | `frontend/src/main.tsx` | React 18 root mounting file. |
| **Frontend Root Router** | `frontend/src/App.tsx` | Client-side routing, auth wrappers, and layout shell. |
| **Application Config** | `backend/app/config.py` | Pydantic BaseSettings, environment validation, Fernet encryption helper. |
| **Database Manager** | `backend/app/database.py` | Motor client connection pool and index setup. |
| **Auth Dependencies** | `backend/app/auth/dependencies.py` | JWT extraction and user verification (`require_auth`). |
| **Video Orchestrator** | `backend/app/video/pipeline.py` | Facade for video assembly, subtitles, voiceover, and FFmpeg composition. |
| **AI Gateway** | `backend/app/ai/gateway.py` | Ollama client with structured JSON repair and Pydantic validation. |
| **HTTP Client** | `frontend/src/api/client.ts` | Axios instance with JWT injection and auto-refresh interceptors. |
| **Pytest Configuration** | `tests/conftest.py` | Pytest fixtures and mock database setup. |
| **Shared Types** | `frontend/src/types/index.ts` | TypeScript interface definitions for API data. |

---

## Naming Conventions

### Python (Backend)
- **Directories**: lowercase snake_case (e.g., `repositories`, `composition`).
- **Files**: lowercase snake_case (e.g., `video_service.py`, `research_worker.py`).
- **Classes**: PascalCase (e.g., `VideoService`, `BaseRepository`, `AIGateway`).
- **Functions & Methods**: snake_case (e.g., `create_video_job`, `generate_structured_script`).
- **Constants & Settings**: UPPER_SNAKE_CASE (e.g., `MONGODB_URI`, `SCRIPT_SYSTEM_PROMPT`).
- **Models**: PascalCase matching entity name (e.g., `Video`, `ContentIdea`, `Job`).
- **Repositories**: Plural module names (e.g., `channels.py`, `videos.py`, `jobs.py`) with singular re-export shims (`channel.py`, `video.py`, `job.py`) for legacy import compatibility.

### TypeScript / React (Frontend)
- **Component Files**: PascalCase (e.g., `Card.tsx`, `Layout.tsx`, `Dashboard.tsx`).
- **Hook Files**: camelCase prefixed with `use` (e.g., `usePolling.ts`).
- **API Files**: camelCase (e.g., `client.ts`, `videos.ts`, `channels.ts`).
- **Interfaces / Types**: PascalCase (e.g., `Video`, `Channel`, `PipelineProgress`).
- **CSS Classes**: Tailwind utility classes (kebab-case).

---

## Where to Add New Code

### 1. Adding a New API Feature / Domain
1. **Schema**: Define Pydantic request/response models in `backend/app/models/<domain>.py`.
2. **Repository**: Create or extend a repository class in `backend/app/repositories/<domain>s.py`, subclassing `BaseRepository`.
3. **Service**: Implement business logic in `backend/app/services/<domain>_service.py`.
4. **Router**: Create endpoints in `backend/app/api/<domain>.py`, using `require_auth` for security.
5. **Mount Router**: Register router in `backend/app/main.py`.
6. **Frontend Types**: Add matching TypeScript interfaces in `frontend/src/types/index.ts`.
7. **Frontend API**: Add Axios methods in `frontend/src/api/<domain>.ts`.
8. **Frontend View**: Create a page in `frontend/src/pages/<Domain>.tsx` and add its route in `frontend/src/App.tsx`.
9. **Navigation**: Add menu item to `frontend/src/components/Sidebar.tsx`.

### 2. Adding a New Background Job / Worker
1. **Job Type**: Define unique job type string (e.g., `"thumbnail_generation"`).
2. **Worker Class**: Create `backend/app/workers/<name>_worker.py` subclassing `BaseWorker`. Implement `async def process(self, job: dict)`.
3. **Register Worker**: Add worker class to `backend/app/workers/runner.py` inside `all_worker_classes`.
4. **Enqueue Job**: Use `self.job_repo.enqueue(job_type, user_id, channel_id, payload)` in the appropriate service.

### 3. Adding a New AI Capability
1. **Prompt**: Define system prompt in `backend/app/ai/prompts.py`.
2. **Gateway Method**: Add structured generation method in `backend/app/ai/gateway.py` with Pydantic response model.
3. **Service Consumption**: Call the new gateway method from the relevant domain service in `backend/app/services/`.

### 4. Adding a New Video Engine Media / TTS Provider
1. **Media Provider**: Implement `MediaProvider` interface in `backend/app/video/media/<provider>_provider.py`.
2. **TTS Provider**: Implement `TTSProvider` interface in `backend/app/video/audio/<provider>_provider.py`.
3. **Wire Provider**: Expose option in `VideoGenerationRequest` in `backend/app/video/models.py` and resolve in `VideoGenerationService._resolve_media_provider` (`backend/app/video/pipeline.py`).

### 5. Adding Tests
- **Unit Test**: Place in `tests/unit/test_<module>.py`. Mock external services and network I/O.
- **Integration Test**: Place in `tests/integration/test_<flow>.py`. Use `async_client` fixture and verify database state changes.

---
*Structure analysis: 2026-09-10*
