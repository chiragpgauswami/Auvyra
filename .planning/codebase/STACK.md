# Technology Stack

**Analysis Date:** 2026-09-10

## Languages & Runtimes

- **Python**:
  - **Version**: Python `>=3.11` (specified in `pyproject.toml`, verified via `scripts/doctor.py`).
  - **Runtime**: CPython 3.11+ running with asynchronous event loop (`asyncio`).
- **JavaScript & TypeScript**:
  - **TypeScript**: `^5.2.2` (configured in `frontend/package.json`, `frontend/tsconfig.json`, `frontend/tsconfig.node.json`).
  - **Runtime & Package Management**: Node.js (`v18+` / `v20+`) and `npm` (`scripts/doctor.py`).
- **Shell Scripting**:
  - **Bash / POSIX Shell**: Orchestration and operational maintenance (`scripts/dev.sh`, `scripts/setup.sh`, `scripts/verify.sh`).

---

## Core Frameworks & Libraries

### Backend Framework
- **FastAPI** (`>=0.115.0` in `pyproject.toml`, implemented in `backend/app/main.py`):
  - Asynchronous RESTful API framework with automatic OpenAPI (`/docs`, `/redoc`) generation.
  - Custom lifespan context manager for database connection pooling and index verification.
  - Request ID injection, security headers (`nosniff`, `DENY` framing), CORS middleware, and sanitized error response handlers.
- **Uvicorn** (`uvicorn[standard]>=0.30.0`):
  - High-performance ASGI server for hosting FastAPI in development and production.
- **Pydantic** (`>=2.9.0`) & **Pydantic Settings** (`>=2.5.0` in `backend/app/config.py`, `backend/app/models/*.py`):
  - Strict type validation, serialization, and domain data models.
  - Environment variable ingestion via `BaseSettings` and `SettingsConfigDict` with custom field validators and production security guards.

### Frontend Framework
- **React 18** (`^18.2.0`, `react-dom^18.2.0` in `frontend/package.json`, `frontend/src/main.tsx`):
  - Component-based UI using React Hooks and Context (`frontend/src/auth/AuthContext.tsx`).
- **Vite** (`^5.2.0` with `@vitejs/plugin-react^4.2.1` in `frontend/vite.config.ts`):
  - Frontend development server with Hot Module Replacement (HMR) and production bundler.
  - Configured reverse proxy forwarding `/api` requests to backend on port 8000.
- **React Router DOM** (`^6.22.3` in `frontend/src/App.tsx`):
  - Client-side routing with authentication guards (`frontend/src/auth/ProtectedRoute.tsx`).
- **Tailwind CSS** (`^3.4.3`, `postcss^8.4.38`, `autoprefixer^10.4.19` in `frontend/tailwind.config.js`):
  - Utility-first CSS styling system with custom dark mode and responsive layout styling.
- **Headless UI** (`@headlessui/react^1.7.18`):
  - Accessible, unstyled UI primitives (dialogs, dropdowns, transitions).
- **Lucide React** (`^0.368.0`):
  - Iconography library used across sidebar, cards, buttons, and navigation.
- **Axios** (`^1.6.8` in `frontend/src/api/client.ts`):
  - HTTP client with automatic Bearer token injection and seamless refresh token rotation interceptors.
- **React Hot Toast** (`^2.4.1`):
  - User notification and alert banners.
- **Date-fns** (`^3.6.0`):
  - Lightweight date formatting and manipulation utilities.

---

## Key Dependencies

### Media Processing & Synthesis
- **FFmpeg & FFprobe** (System binary, wrapped in `backend/app/video/rendering/ffmpeg.py`):
  - Video composition, stream concatenation, audio/video multiplexing, and media probing.
  - Hardware encoder detection and dynamic fallback: `h264_videotoolbox` (macOS), `h264_nvenc` (NVIDIA), `h264_amf` (AMD), `h264_qsv` (Intel), falling back to `libx264`.
- **MoviePy** (`>=2.1.0` in `pyproject.toml`, `backend/app/video/composition/assembler.py`):
  - Programmatic video clip assembling, duration trimming, aspect ratio transforms, and subtitle overlaying.
- **Pillow** (`>=10.0.0`):
  - Image handling, synthetic slide generation, text drawing, and thumbnail processing.
- **NumPy** (`>=1.26.0`):
  - Array transformations and pixel buffer operations used by MoviePy and Pillow.
- **Pydub** (`>=0.25.0`):
  - Audio segment manipulation, normalization, and duration calculations (`backend/app/video/audio/duration.py`).
- **Edge-TTS** (`>=7.0.0` in `backend/app/video/audio/edge_tts_provider.py`):
  - Python interface for Microsoft Edge's free neural text-to-speech engine.
  - Generates synchronized audio narration and word-boundary/sentence-boundary subtitle metadata via `SubMaker`.
- **Faster-Whisper** (`>=1.0.0` in `backend/app/video/subtitles/generator.py`):
  - CTranslate2-accelerated OpenAI Whisper implementation for audio transcription and timestamp alignment.

### AI & Machine Learning Interface
- **OpenAI Python SDK** (`>=1.50.0` in `backend/app/ai/gateway.py`):
  - `AsyncOpenAI` client utilized to interact with local Ollama instances via OpenAI-compatible endpoint `/v1`.
  - Powers script generation, hook scoring, competitive topic research, and strategy insights.

### Security, Cryptography & Authentication
- **Python-Jose** (`python-jose[cryptography]>=3.3.0` in `backend/app/auth/service.py`):
  - JSON Web Token (JWT) encoding, decoding, and cryptographic validation using HMAC-SHA256 (`HS256`).
- **Passlib & Bcrypt** (`passlib[bcrypt]>=1.7.4`, `bcrypt`):
  - Secure salted password hashing and credential verification.
- **Cryptography** (`>=43.0.0` in `backend/app/config.py`, `backend/app/auth/service.py`):
  - Fernet symmetric key encryption (`AES-128-CBC` with `HMAC-SHA256`) for securing third-party OAuth tokens (Google/YouTube access and refresh tokens) at rest in MongoDB.
- **Email-Validator** (`>=2.0.0`):
  - Strict email address syntax and domain validation.

### Async I/O, Networking & Storage
- **Motor** (`>=3.5.0` in `backend/app/database.py`):
  - Official asynchronous MongoDB driver wrapping PyMongo for async/await database operations.
- **HTTPX** (`>=0.27.0`):
  - Asynchronous HTTP client for outbound requests to Google OAuth, YouTube Data API, YouTube Analytics API, Pexels API, and Ollama.
- **Aiofiles** (`>=24.1.0` in `backend/app/storage/local.py`):
  - Non-blocking asynchronous filesystem reads and writes for media file storage.
- **Loguru** (`>=0.7.0`):
  - Structured, thread-safe application and worker logging with automatic formatting and stack trace isolation.

---

## Infrastructure & Database

- **Database**:
  - **MongoDB** (6.0+ / 7.0+, local instance or MongoDB Atlas), connected via `motor.motor_asyncio.AsyncIOMotorClient` (`backend/app/database.py`).
  - **Collections**:
    - `users`: User accounts and hashed credentials.
    - `oauth_accounts`: Third-party OAuth links with Fernet-encrypted tokens.
    - `sessions`: Active refresh token hashes and expiration timestamps.
    - `channels`: YouTube channels connected or managed by creators.
    - `channel_memory`: Persistent longitudinal strategy memory and channel heuristics.
    - `content_ideas`: Generated video topics, hooks, angles, and status.
    - `videos`: Master video records, rendering metadata, and YouTube publishing status.
    - `analytics_snapshots`: Performance metrics snapshots over time.
    - `strategy_insights`: AI-generated actionable advice and channel performance insights.
    - `jobs`: Asynchronous worker tasks and progress tracking.
    - `notifications`: User alert notifications.
  - **Index Strategy**: Automated startup index creation (`backend/app/database.py`) ensuring uniqueness (`users.email`, sparse `channels.youtube_channel_id`) and compound query performance (`jobs(status, created_at)`, `videos(channel_id, status)`, `videos(channel_id, published_at DESC)`).
- **File & Media Storage**:
  - `LocalStorageProvider` (`backend/app/storage/local.py` implementing `StorageProvider` in `backend/app/storage/base.py`).
  - Hierarchical storage directories (`media/videos/`, `media/audio/`, `media/images/`, `media/thumbnails/`, `media/temp/`).
  - Mounted via FastAPI static file handler (`backend/app/main.py`) at `/media`.
  - Built-in path traversal safeguards (`_validate_safe_path`).
- **Background Worker Engine**:
  - Independent async polling workers (`backend/app/workers/runner.py`) utilizing atomic MongoDB updates (`find_one_and_update`) on the `jobs` collection.
  - Includes automated stale-job recovery (`JobRepository.recover_stale_jobs`).

---

## Configuration & Environment

- **Configuration Engine**:
  - Centralized in `backend/app/config.py` using `pydantic_settings.BaseSettings`.
  - Loaded from `.env` file with environment variable fallback.
- **Categorized Variables**:
  - **Required Core Settings**:
    - `MONGODB_URI`: MongoDB connection string.
    - `MONGODB_DATABASE`: Primary database name (default: `auvyra`).
    - `JWT_SECRET`: Secret key for JWT signing (minimum 32 characters in production).
    - `JWT_REFRESH_SECRET`: Secret key for refresh tokens.
    - `ENCRYPTION_KEY`: Fernet base64 key for encrypted tokens (auto-generated in dev if unspecified).
  - **Feature-Specific Settings**:
    - `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`: Google OAuth credentials for YouTube publishing.
    - `OLLAMA_BASE_URL` (default: `http://localhost:11434`), `OLLAMA_MODEL` (default: `llama3.1:8b`), `OLLAMA_TIMEOUT_SECONDS`: AI gateway configuration.
  - **Optional Integration Settings**:
    - `PEXELS_API_KEY`: External stock media search and download.
    - `FFMPEG_PATH`, `FFPROBE_BINARY`: Explicit overrides for system binaries.
    - `EDGE_TTS_VOICE`: Default voice identifier (default: `en-US-AriaNeural`).
    - `MEDIA_ROOT`: Root path for local video asset storage (default: `media`).
- **Production Guardrails**:
  - Hard failure on default secrets (`auvyra-development-...`, `change-me`).
  - Automatic `APP_DEBUG=False` and `COOKIE_SECURE=True` enforcement in production environment.

---

## Build & Tooling

- **Backend Build & Packaging**:
  - `pyproject.toml` managed via Hatchling build backend (`[build-system] requires = ["hatchling"]`).
  - Execution within Python virtual environment (`.venv`).
- **Frontend Build & Bundling**:
  - `vite build` (`tsc && vite build`) producing static distribution assets in `frontend/dist/`.
  - ESLint `^8.57.0` configuration enforcing TypeScript and React best practices (`frontend/package.json`).
- **Testing Tools**:
  - `pytest` with `pytest-asyncio` (`asyncio_mode = "auto"`, session-scoped database fixtures in `tests/conftest.py`).
  - Unit tests (`tests/unit`), integration tests (`tests/integration`), end-to-end acceptance tests (`scripts/test_e2e.py`).
  - `puppeteer-core` (`^25.10.0` in `scripts/real_user_acceptance_browser.js`) for end-to-end browser verification.
- **Development & Operations Scripts**:
  - `scripts/dev.sh`: Starts FastAPI backend, video generation worker, and Vite frontend server concurrently.
  - `scripts/doctor.py`: Diagnostics tool verifying Python, Node, FFmpeg, MongoDB, Ollama, Edge TTS, Google OAuth, and Fernet encryption.
  - `scripts/setup.sh`: Automated dependency installation and directory setup.
  - `scripts/verify.sh`: Comprehensive test suite and build verification script.
  - `scripts/production_acceptance.py`: Automated multi-step acceptance test harness validating end-to-end user workflows.

---
*Stack analysis: 2026-09-10*
