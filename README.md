# Auvyra — Autonomous YouTube Automation Platform

Auvyra is an autonomous AI-powered YouTube channel automation engine designed for creators and media teams. It manages the complete content lifecycle through a closed feedback loop:

$$\text{Research} \longrightarrow \text{Create} \longrightarrow \text{Publish} \longrightarrow \text{Analyze} \longrightarrow \text{Learn}$$

---

## Architecture Overview

- **Backend:** FastAPI (Python 3.11+), Motor (Async MongoDB), Pydantic v2
- **Video Engine:** Modern MoviePy 2.x, Edge TTS (Word-level subtitle alignment), FFmpeg 7.x with hardware acceleration fallback (`h264_videotoolbox`, `nvenc`, `libx264`)
- **AI Gateway:** Ollama local LLM integration with structured JSON repair and graceful degradation (HTTP 503 on offline)
- **Background Workers:** Asynchronous distributed task workers with stale job crash recovery
- **Database:** MongoDB with multi-tenant user scoping and compound indexing
- **Frontend:** React 18, TypeScript, Tailwind CSS, Vite

---

## Prerequisites

- **Python:** 3.11 or higher
- **Node.js:** 18 or higher (Node 20+ recommended)
- **FFmpeg & FFprobe:** Installed and on system PATH (`brew install ffmpeg` on macOS)
- **MongoDB:** Running locally or accessible via MongoDB Atlas
- **Ollama (Optional):** Running locally on port 11434 (`ollama run llama3.1:8b`)

---

## Quickstart Setup

### 1. Clone & Configure Environment
```bash
cp .env.example .env
```
Edit `.env` as needed. If `ENCRYPTION_KEY` is not set or invalid, Auvyra automatically generates a secure Fernet encryption key on startup.

### 2. Python Backend Virtual Environment
```bash
# Using uv (recommended)
uv venv .venv
source .venv/bin/activate
uv pip install -e .

# Or standard pip
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 3. Start MongoDB
```bash
# macOS Homebrew
brew services start mongodb-community
```

### 4. Run Automated QA Tests
```bash
# Run the complete unit and integration test suite
pytest -v tests/

# Run the full end-to-end creator journey test
python scripts/test_e2e.py
```

### 5. Launch the FastAPI Backend
```bash
source .venv/bin/activate
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```
Interactive API documentation will be accessible at:
- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check:** [http://localhost:8000/api/health](http://localhost:8000/api/health)

### 6. Launch Background Workers
In a separate terminal:
```bash
source .venv/bin/activate
python -m backend.app.workers.runner
```
This starts the background job processing loop with automatic stale job recovery (recovering any tasks interrupted by worker crashes).

### 7. Launch Frontend Development Server
In a separate terminal:
```bash
cd frontend
npm install
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

To build the frontend for production:
```bash
cd frontend
npm run build
```

---

## Verification & QA Status

Auvyra has been audited and verified:
- **Automated Tests:** 17/17 passing (`tests/unit` and `tests/integration`)
- **End-to-End Pipeline:** 19/19 passing (`scripts/test_e2e.py`)
- **Frontend Compilation:** Clean build with 0 TypeScript errors
- Detailed test matrix: [`docs/TESTING.md`](docs/TESTING.md)
- Complete QA report: [`docs/TEST_REPORT.md`](docs/TEST_REPORT.md)

---

## License

MIT License. See third-party attributions in [`backend/app/video/ATTRIBUTION.md`](backend/app/video/ATTRIBUTION.md).
