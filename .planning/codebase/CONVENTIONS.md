# Coding Conventions

**Analysis Date:** 2026-09-10

## Naming Patterns (Files, Functions, Variables, Types, Models)

### Files and Directories
- **Python Backend**: All module files and directory names use standard lowercase `snake_case.py`:
  - Routers & Endpoints: `backend/app/api/channels.py`, `backend/app/api/videos.py`, `backend/app/auth/router.py`.
  - Services: `backend/app/services/channel_service.py`, `backend/app/services/learning_service.py`, `backend/app/services/analytics_service.py`.
  - Repositories: `backend/app/repositories/base.py`, `backend/app/repositories/jobs.py`, `backend/app/repositories/videos.py`.
  - Workers: `backend/app/workers/base.py`, `backend/app/workers/video_worker.py`, `backend/app/workers/learning_worker.py`.
  - Utilities & Subsystems: `backend/app/video/audio/edge_tts_provider.py`, `backend/app/video/rendering/ffmpeg.py`, `backend/app/video/subtitles/srt_parser.py`.
  - Diagnostic Scripts: `scripts/doctor.py`, `scripts/production_acceptance.py`, `scripts/test_e2e.py`.
- **TypeScript / React Frontend**:
  - React Components and Pages use `PascalCase.tsx`: `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/Channels.tsx`, `frontend/src/components/Card.tsx`, `frontend/src/components/Sidebar.tsx`, `frontend/src/auth/ProtectedRoute.tsx`.
  - API modules, hooks, and utilities use `camelCase.ts`: `frontend/src/api/client.ts`, `frontend/src/api/channels.ts`, `frontend/src/hooks/usePolling.ts`.
  - Core interfaces and types are concentrated in `frontend/src/types/index.ts`.

### Functions and Methods
- **Python**: Standard `snake_case` with verb-noun naming conventions:
  - CRUD operations: `find_by_id`, `find_many`, `insert_one`, `update_one`, `delete_one` in `backend/app/repositories/base.py`.
  - Helpers and Validators: `safe_object_id`, `sanitize_validation_errors`, `validate_video_content`, `verify_granted_scopes`.
  - Async operations are explicitly defined with `async def` and clear naming (`check_mongodb_health`, `get_my_channel`, `recover_stale_jobs`).
- **TypeScript**: Standard `camelCase` for functions and hooks; `PascalCase` for React functional components:
  - API functions: `listChannels`, `createChannel`, `getYoutubeStatus`, `syncYoutubeChannel` in `frontend/src/api/channels.ts`.
  - React components: `Card`, `EmptyState`, `Layout`, `ProgressBar` in `frontend/src/components/`.
  - Custom hooks: prefixed with `use` (e.g. `usePolling` in `frontend/src/hooks/usePolling.ts`, `useAuth` in `frontend/src/auth/AuthContext.tsx`).

### Variables and Constants
- **Python**:
  - Global constants and configuration defaults use `UPPER_SNAKE_CASE`: `TEST_DB_NAME` in `tests/conftest.py`, `REQUIRED_YOUTUBE_SCOPES` and `CANONICAL_OAUTH_SCOPES` in `backend/app/youtube/scopes.py`, ANSI escape codes `GREEN`, `RED`, `RESET` in `scripts/doctor.py`.
  - Local variables and attributes use `snake_case`: `user_id`, `channel_id`, `access_token_encrypted`, `video_job_data`.
- **TypeScript**:
  - Constants use `UPPER_SNAKE_CASE` for fixed configuration (e.g. `CHROME_PATH`, `BASE_URL` in `scripts/real_user_acceptance_browser.js`).
  - Variables and props use `camelCase`: `token`, `refreshToken`, `isPolling`, `channelId`.

### Types and Models
- **Python (Pydantic v2)**:
  - All schema models use `PascalCase` inheriting from `pydantic.BaseModel`: `UserCreate`, `UserResponse`, `UserInDB`, `OAuthAccount`, `TokenPair` in `backend/app/models/user.py`.
  - Domain request/response models: `VideoGenerationRequest`, `VideoAspect` in `backend/app/video/models.py`; `StructuredScript`, `ResearchOpportunity` in `backend/app/models/content.py`.
  - Custom exceptions: `PascalCase` with `Error` suffix: `OllamaUnavailableError` in `backend/app/ai/gateway.py`, `YouTubeAPIError` in `backend/app/youtube/client.py`.
- **TypeScript**:
  - Interfaces and type aliases use `PascalCase`: `User`, `Channel`, `Video`, `Job`, `ContentIdea`, `ResearchReport`, `TokenPair`, `PipelineProgress` in `frontend/src/types/index.ts`, `YouTubeStatus` in `frontend/src/api/channels.ts`.

---

## Code Style & Formatting (Python, TypeScript)

### Python Standards
- **Python Version**: Python >= 3.11 enforced by `scripts/doctor.py` (`sys.version_info >= (3, 11)`).
- **Type Annotations**: Comprehensive typing throughout models, function arguments, and return types using modern Python 3.10+ union syntax (`str | None`, `list[dict]`) alongside standard library typing (`Optional`, `List`, `Dict`, `Any` from `typing`).
- **Pydantic V2 Usage**: Models leverage `Field(alias="_id")` for MongoDB ID mapping and validation constraints (e.g. `Field(min_length=8)` for passwords in `backend/app/models/user.py`).
- **Async First Architecture**: All I/O operations (Motor MongoDB client, HTTPX async clients for Ollama/YouTube, Edge-TTS audio generation) use `async`/`await`.
- **Clean Configuration**: Centralized environment validation using `pydantic_settings.BaseSettings` in `backend/app/config.py` with automatic key generation (e.g. Fernet 32-byte urlsafe base64 key auto-generation if missing).

### TypeScript & React Standards
- **Strict Mode**: TypeScript strict mode enabled (`"strict": true` in `frontend/tsconfig.json`).
- **ES Modules**: Modern ES module imports (`"type": "module"` in `frontend/package.json`, Vite bundler).
- **React Patterns**:
  - Function components with TypeScript interface props (e.g. `interface CardProps` in `frontend/src/components/Card.tsx`).
  - Context API for global state management (`AuthContext` in `frontend/src/auth/AuthContext.tsx`).
  - Client-side token storage in `localStorage` with automated Axios 401 refresh interceptors in `frontend/src/api/client.ts`.
- **Styling**: Tailwind CSS utility classes with dark theme palette (`bg-slate-900`, `border-slate-800`, `text-slate-100`).
- **Linting**: ESLint rule set (`eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0`) with React Hooks (`eslint-plugin-react-hooks`) and Fast Refresh (`eslint-plugin-react-refresh`).

---

## Import Organization

### Python Import Ordering
Imports strictly follow a three-tier grouping separated by single blank lines:
1. **Standard Library Imports**:
   ```python
   import os
   import sys
   import uuid
   from datetime import datetime, timezone
   from pathlib import Path
   ```
2. **Third-Party Frameworks & Dependencies**:
   ```python
   from fastapi import FastAPI, HTTPException, Request, status
   from fastapi.exceptions import RequestValidationError
   from pydantic import BaseModel, Field
   from motor.motor_asyncio import AsyncIOMotorDatabase
   from loguru import logger
   import httpx
   ```
3. **Internal Application Imports** (using absolute workspace package paths):
   ```python
   from backend.app.config import get_settings
   from backend.app.database import db_manager
   from backend.app.repositories.base import safe_object_id
   from backend.app.models.user import UserCreate, UserResponse
   ```

### TypeScript Import Ordering
1. External core libraries: React, React Router, Axios, Lucide icons:
   ```typescript
   import React, { useState, useEffect } from 'react';
   import { useNavigate, Link } from 'react-router-dom';
   import axios from 'axios';
   import { Video, Youtube, CheckCircle } from 'lucide-react';
   ```
2. Internal types, context, and custom hooks:
   ```typescript
   import { Channel, YouTubeStatus } from '../types';
   import { useAuth } from '../auth/AuthContext';
   import { usePolling } from '../hooks/usePolling';
   ```
3. Local UI components and API modules:
   ```typescript
   import Card from '../components/Card';
   import StatusBadge from '../components/StatusBadge';
   import { client } from './client';
   ```

---

## Error Handling & Exception Patterns

### Structured Error Standard
A central structured error standard is implemented in `backend/app/main.py`. All API errors conform to a unified JSON response envelope:
```json
{
  "error": {
    "code": "ERROR_CODE_STRING",
    "message": "Human-readable description",
    "details": null,
    "request_id": "uuid4-string"
  }
}
```

### Sensitive Data Redaction
In `backend/app/main.py`, the `sanitize_validation_errors` helper sanitizes all FastAPI/Pydantic validation errors before responding:
- Any field containing sensitive substrings (`password`, `token`, `secret`, `key`, `authorization`) has its input redacted to `"[REDACTED]"`.
- Non-serializable raw types (such as raw bytes or complex objects) are converted to safe string representations (`<bytes len=N>`, `<dict keys=[...]>`) to prevent JSON serialization crashes or secondary 500 errors.
- Verified in `tests/integration/test_auth_login_regression.py`.

### Custom Exceptions
- Domain-specific exceptions inherit from Python `Exception` and include structured properties:
  - `OllamaUnavailableError(message, url)` in `backend/app/ai/gateway.py` with code `"OLLAMA_UNAVAILABLE"`.
  - `YouTubeAPIError(message, status_code, error_code, retryable)` in `backend/app/youtube/client.py`.
- Router endpoints raise `fastapi.HTTPException` with structured dictionaries:
  ```python
  raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail={"code": "NOT_CONNECTED", "message": "Google OAuth is not connected."}
  )
  ```
- Catch-all exception handler in `backend/app/main.py` intercepts any uncaught server exception, logs the traceback internally with `logger.exception`, and returns a generic `INTERNAL_SERVER_ERROR` without leaking internal stack traces.

### Frontend Error Handling
- Axios interceptor in `frontend/src/api/client.ts` intercepts HTTP `401 Unauthorized`.
- Automatically calls `/api/auth/refresh` using the stored refresh token.
- If the refresh token has expired or is invalid, tokens are cleared and the user is redirected to `/login`.
- Toast notifications via `react-hot-toast` present user-friendly error messages parsed from `error.response?.data?.error?.message`.

---

## Logging (Loguru, console)

### Loguru Logging Architecture
- Logging is standardized across all backend services, workers, repositories, and API entry points using `from loguru import logger`.
- Plain `print()` calls are prohibited in backend application code.
- **Log Levels and Conventions**:
  - `logger.info()`: Application lifecycle events, worker task lifecycles, database connection milestones (`backend/app/main.py`, `backend/app/workers/base.py`).
  - `logger.success()`: Successfully completed pipelines (e.g. video rendering completion in `backend/app/workers/video_worker.py`, publishing events in `backend/app/workers/publishing_worker.py`).
  - `logger.warning()`: Degraded states, retry triggers, AI fallback events (`backend/app/services/content_service.py`, `backend/app/services/learning_service.py`).
  - `logger.error()`: Recoverable task failures, failed external API calls, MongoDB connection failures (`backend/app/workers/base.py`, `backend/app/youtube/client.py`).
  - `logger.exception()`: Uncaught server exceptions inside HTTP request contexts with complete tracebacks recorded in system logs (`backend/app/main.py`).

### CLI & Script Console Output
- Diagnostics and CLI utilities (`scripts/doctor.py`, `scripts/production_acceptance.py`, `scripts/test_e2e.py`) use standardized ANSI colors for terminal readability:
  - `GREEN` for `[PASS]`
  - `RED` for `[FAIL]`
  - `YELLOW` for `[WARNING]` and `[BLOCKED]`
  - `CYAN` and `BOLD` for section headers and diagnostic metadata.
- Zero-leak credential rule: `scripts/test_youtube_oauth.py` provides a `mask_string` utility to mask client IDs and tokens, ensuring secrets never appear in logs or terminal outputs.

---

## Function & Module Design

### Repository Pattern with Multi-Tenant Isolation
- `backend/app/repositories/base.py` implements `BaseRepository`:
  - Enforces automatic timestamp handling (`created_at`, `updated_at` with UTC timezone).
  - Normalizes IDs via `safe_object_id` supporting string and BSON `ObjectId`.
  - Enforces multi-tenant data isolation: operations (`find_by_id`, `update_one`, `delete_one`) accept an optional `user_id` parameter to scope queries strictly to the owning tenant.
  - Integration verified in `tests/integration/test_mongodb_isolation.py`.

### Service Layer Pattern
- Business logic is isolated in dedicated service classes (`backend/app/services/`):
  - `ChannelService`: Manages channel lifecycle, autopilot toggles, and YouTube linking.
  - `ContentService`: Orchestrates content idea generation, script creation, and Ollama prompts.
  - `VideoService`: Handles video generation scheduling, asset validation, and job dispatching.
  - `AnalyticsService`: Ingests performance snapshots and calculates real engagement metrics.
  - `LearningService`: Aggregates channel memory and strategy recommendations based strictly on real snapshot data.

### Resilient Worker Pattern
- `backend/app/workers/base.py` provides an asynchronous `BaseWorker` background execution loop:
  - Stale job auto-recovery: `recover_stale_jobs` checks for jobs stuck in `processing` beyond a timeout window (e.g. 15 minutes) and requeues them up to `max_attempts`.
  - Exponential/linear retry policies with explicit failure state recording in MongoDB.
  - Safe shutdown hooks on cancellation signals.

---
*Convention analysis: 2026-09-10*
