# Testing Patterns

**Analysis Date:** 2026-09-10

## Test Framework & Runners (Pytest, Puppeteer/Browser QA, Vitest)

The Auvyra testing architecture utilizes a multi-tiered strategy spanning fast unit tests, ASGI integration tests, environment health checks, and a real headless browser QA suite.

### 1. Pytest (Python Backend Test Runner)
- **Framework**: `pytest` (v9.1.1) paired with `pytest-asyncio` for asynchronous coroutine execution.
- **In-Memory ASGI Execution**: Integration tests use `httpx.AsyncClient` with `ASGITransport(app=app)` to test FastAPI endpoints directly in-process without spinning up a live TCP socket.
- **Configuration & Markers**: Async tests are marked with `@pytest.mark.asyncio`. Test discovery covers `tests/unit/` and `tests/integration/`.

### 2. Puppeteer Real User Browser Acceptance (`scripts/real_user_acceptance_browser.js`)
- **Framework**: `puppeteer-core` driving an installed Google Chrome binary (`/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` on macOS).
- **Execution Target**: Live Vite frontend server (`http://localhost:5173`) interacting with the FastAPI backend.
- **Automated Workflow**:
  1. Initial App Load verification (Title check: `"Auvyra"`).
  2. Real user registration with dynamic timestamp credentials.
  3. Session logout and fresh login sequence.
  4. Channel creation and YouTube OAuth status audit.
  5. Content generation wizard (Ollama research and script drafting).
  6. Video creation queue and live polling progress monitoring (`0%` -> `100%`).
  7. Video playback verification: mounts HTML5 `<video>` element and asserts positive media duration.
  8. Videos library verification and analytics dashboard inspection.
  9. Network failure and browser console error interception (`page.on('console')`, `page.on('requestfailed')`).

### 3. Environment & Dependency Doctor (`scripts/doctor.py`)
- Automated pre-flight certification runner verifying:
  - Python version (Python >= 3.11).
  - Node.js & npm runtime availability in `PATH`.
  - FFmpeg & FFprobe binary installations.
  - Fernet encryption key validation (encrypt/decrypt round-trip).
  - MongoDB connectivity (`ping` command via Motor).
  - Ollama service availability and configured model presence (`OLLAMA_MODEL`).
  - Ollama live inference test (`gateway._chat`).
  - Edge-TTS speech synthesis test (`en-US-AriaNeural`).
  - Google OAuth credentials presence in `.env`.

### 4. Frontend Build & Type Validation
- Static analysis and compilation verified via `frontend/package.json`:
  - `npm run build`: Executes `tsc && vite build` to enforce TypeScript type safety across all components and API calls.
  - `npm run lint`: Executes `eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0`.
- *Note on Vitest*: Unit testing for frontend components is currently handled via TypeScript compilation and browser-driven Puppeteer E2E acceptance; Vitest can be layered on top of Vite if granular component unit tests are required in future phases.

---

## Test File Organization

The `tests/` directory is structured to separate pure isolated logic from database-backed integrations:

```
tests/
├── conftest.py                          # Root fixtures: test database lifecycle & async client
├── fixtures/
│   ├── __init__.py
│   └── sample_data.py                   # Centralized mock/sample entities
├── unit/
│   ├── test_ai_gateway.py               # JSON extraction, repair routines, unreachable Ollama error
│   ├── test_config.py                   # Settings validation, Fernet auto-generation, optional flags
│   ├── test_storage.py                  # Local storage directories & path traversal prevention
│   └── test_video_pipeline.py           # Aspect ratios, SRT parser, Edge-TTS cleaner, FFmpeg codec
└── integration/
    ├── test_api_auth.py                 # Registration, login, JWT token emission, /api/auth/me
    ├── test_auth_login_regression.py    # Form-encoded rejects, bad credentials, secret redaction
    ├── test_health_api.py               # /api/health, /api/health/live, /api/health/ready
    ├── test_mongodb_isolation.py        # Multi-tenant scoping and cross-tenant 404 security
    ├── test_api_workflow.py             # Full creator lifecycle & worker stale job recovery
    └── test_learning_loop.py            # Analytics snapshots & memory engine zero-mock validation
```

Additional diagnostic and certification scripts reside in `scripts/`:
- `scripts/doctor.py`: System prerequisites doctor.
- `scripts/verify.sh`: Phase 1 verification orchestrator (Doctor + Pytest + Vite Build).
- `scripts/real_user_acceptance_browser.js`: Puppeteer end-to-end browser QA runner.
- `scripts/production_acceptance.py`: Zero-mock production journey certification.
- `scripts/test_e2e.py`: Complete creator journey verification.
- `scripts/test_youtube_oauth.py`: YouTube OAuth diagnostic and token audit.

---

## Test Structure & Patterns

### Standard Test Anatomy
Tests follow an explicit Arrange-Act-Assert pattern with strict type expectations:
```python
@pytest.mark.asyncio
async def test_complete_creator_workflow(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Arrange
        register_payload = {
            "email": "workflow_creator@example.com",
            "password": "Password123!Secure",
            "name": "Workflow Creator"
        }
        # Act
        resp = await client.post("/api/auth/register", json=register_payload)
        # Assert
        assert resp.status_code == 201
        assert "access_token" in resp.json()
```

### Multi-Tenant Isolation Testing Pattern
Demonstrated in `tests/integration/test_mongodb_isolation.py`:
1. Register two independent users (`SAMPLE_USER_A`, `SAMPLE_USER_B`).
2. User A creates a resource (e.g. Channel A).
3. User B lists channels; test asserts Channel A is not present.
4. User B attempts direct retrieval, update, or deletion of Channel A; test asserts `status_code == 404` and error envelope `HTTP_404`.
5. User A retrieves Channel A to prove it was not mutated by User B's unauthorized attempts.

### Security & Sanitization Regression Pattern
Demonstrated in `tests/integration/test_auth_login_regression.py`:
- Malformed payloads (such as URL-encoded forms where JSON is expected) must produce a clean `422 Unprocessable Entity` rather than an unhandled `500 Internal Server Error`.
- Validation errors containing sensitive fields (`password`, `token`) are checked against the response string to ensure plaintext passwords are never leaked back to the client.

### Stale Job Recovery Testing Pattern
Demonstrated in `tests/integration/test_api_workflow.py`:
- A job is injected into MongoDB with status `processing` and a backdated `updated_at` timestamp (e.g. 20 minutes in the past).
- `job_repo.recover_stale_jobs(timeout_minutes=15)` is executed.
- Test asserts that the stuck job is recovered back to `queued` status and its `attempts` counter is incremented.

---

## Mocking Guidelines (Strict Zero-Mock Policy for YouTube/Video/Ollama/Analytics)

Auvyra enforces a **Strict Zero-Mock Policy** for all core revenue and production subsystems:

### 1. YouTube & Google OAuth
- **Rule**: Never fabricate synthetic YouTube metrics, dummy video IDs, fake view counts, or mock upload responses in production or integration code.
- **Handling Missing Credentials**: When `.env` lacks valid `GOOGLE_CLIENT_ID` or `GOOGLE_CLIENT_SECRET`, the system must explicitly mark the integration as `[BLOCKED]` or return `400 NOT_CONNECTED` / `403 YOUTUBE_INSUFFICIENT_SCOPES` with actionable instructions (referencing `docs/SETUP_REQUIRED.md`).
- **Scope Verification**: `verify_granted_scopes` in `backend/app/youtube/scopes.py` audits actual granted scopes against canonical requirements (`youtube.readonly`, `youtube.upload`).

### 2. Video Rendering & Media Validation
- **Rule**: Videos must be compiled using real FFmpeg binaries rather than writing dummy `.mp4` text files.
- **Visual & Audio QA**: Real video verification via `backend/app/video/validation.py` (`validate_video_content`, `VisualQAReport`):
  - Probes container and stream formats with `ffprobe`.
  - Samples video frames across duration; calculates mean luminance and variance to fail black or freeze frames.
  - Validates audio stream presence, non-zero sample amplitudes, and audio-video duration sync within tolerance (0.5s).

### 3. Ollama & AI Generation
- **Rule**: LLM prompts must target the configured Ollama instance (`http://localhost:11434`).
- **Failure Assertions**: `tests/unit/test_ai_gateway.py` tests that pointing to an unreachable port raises `OllamaUnavailableError` with code `"OLLAMA_UNAVAILABLE"`.
- **Parsing Robustness**: LLM output clean-up routines (`repair_json_string`, `extract_json`) are tested against markdown-wrapped, malformed, or trailing-comma JSON outputs.

### 4. Analytics & Learning Loop
- **Rule**: Channel memory and strategy insights must derive strictly from real snapshot data.
- **Zero-Mock Verification**: `tests/integration/test_learning_loop.py` tests that:
  - If no analytics snapshots exist, `generate_insights` returns an empty list `[]` (never returns placeholder data).
  - When real snapshots are ingested, calculated metrics (`total_views`, `avg_views`) match mathematical sums.
  - Channel memory assertions explicitly fail if hardcoded placeholder strings (such as `"Practical AI Tools"` or `"Stop doing X manually"`) are found in `best_topics` or `best_hooks`.

---

## Fixtures & Test Database

### Test Database Lifecycle (`tests/conftest.py`)
```python
TEST_DB_NAME = "auvyra_test"

@pytest.fixture(scope="session")
async def init_test_db():
    settings = get_settings()
    await db_manager.connect(settings.MONGODB_URI, TEST_DB_NAME)
    await db_manager.create_indexes()
    
    yield db_manager.get_database()
    
    # Teardown: drop test database and disconnect
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    await client.drop_database(TEST_DB_NAME)
    await db_manager.disconnect()

@pytest.fixture
async def test_db(init_test_db):
    db = init_test_db
    # Clean all non-system collections before each test run
    collections = await db.list_collection_names()
    for col in collections:
        if not col.startswith("system."):
            await db[col].delete_many({})
    return db
```
- **Database Name**: Dedicated `auvyra_test` database to protect production/development data.
- **Session Fixture (`init_test_db`)**: Connects Motor client, creates MongoDB indexes, drops the entire test database on session completion, and closes connections.
- **Function Fixture (`test_db`)**: Iterates all collections and performs `delete_many({})` before each test, providing clean state isolation.

### HTTP Client Fixture (`async_client`)
```python
@pytest.fixture
async def async_client(init_test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
```
Provides an asynchronous HTTP test client with ASGI transport bound to `backend.app.main.app`.

### Temporary Storage Fixture (`tests/unit/test_storage.py`)
```python
@pytest.fixture
def temp_storage():
    with tempfile.TemporaryDirectory() as td:
        yield LocalStorageProvider(root_dir=td)
```
Generates a sandboxed temporary directory to verify folder hierarchy creation (`videos/`, `audio/`, `images/`, `thumbnails/`, `temp/`) and path traversal security.

### Reusable Test Entities (`tests/fixtures/sample_data.py`)
- `SAMPLE_USER_A` / `SAMPLE_USER_B`: Email, password, and name payloads for tenant isolation tests.
- `SAMPLE_CHANNEL_A` / `SAMPLE_CHANNEL_B`: Channel names, descriptions, and handles.
- `SAMPLE_OPPORTUNITY`: AI research topic data with confidence scores and content gaps.
- `SAMPLE_SCRIPT`: Script text, topic, duration, and aspect ratio (`9:16`).
- `SAMPLE_ANALYTICS_SNAPSHOT`: Baseline engagement data (views, likes, comments, watch time, CTR).

---

## Common Test Commands

### 1. Comprehensive Phase 1 Verification
Runs Doctor check, full Pytest suite, and Frontend production build:
```bash
bash scripts/verify.sh
```

### 2. Pytest Execution
Run all unit and integration tests:
```bash
.venv/bin/pytest -v tests/
```

Run unit tests only:
```bash
.venv/bin/pytest -v tests/unit/
```

Run integration tests only:
```bash
.venv/bin/pytest -v tests/integration/
```

Run a specific test file:
```bash
.venv/bin/pytest -v tests/integration/test_mongodb_isolation.py
```

Run with test output and fail-fast:
```bash
.venv/bin/pytest -v -s -x tests/
```

### 3. Diagnostics and Pre-Flight Checks
Run environment and dependency doctor:
```bash
.venv/bin/python scripts/doctor.py
```

Run YouTube OAuth configuration diagnostic:
```bash
.venv/bin/python scripts/test_youtube_oauth.py
```

### 4. End-to-End & Production Acceptance
Run full backend creator journey verification:
```bash
.venv/bin/python scripts/test_e2e.py
```

Run final Phase 1 zero-mock certification runner:
```bash
.venv/bin/python scripts/production_acceptance.py
```

### 5. Browser QA Acceptance Runner
Requires live frontend (`npm run dev` at `http://localhost:5173`) and backend running:
```bash
node scripts/real_user_acceptance_browser.js
```

### 6. Frontend Verification
Typecheck and build production bundle:
```bash
cd frontend && npm run build
```

Run ESLint:
```bash
cd frontend && npm run lint
```

---
*Testing analysis: 2026-09-10*
