#!/usr/bin/env bash
# ==============================================================================
# Auvyra — One-Command Development Server Launcher
# Starts Backend (FastAPI), Video Worker, and Frontend (Vite)
# ==============================================================================
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Ensure Python Virtual Environment
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "Warning: No .venv found. Using system python."
fi

# Ensure media directory exists
mkdir -p media/videos media/audio media/images media/thumbnails media/temp

echo "=========================================================="
echo "  AUVYRA — STARTING LOCAL DEVELOPMENT SERVICES"
echo "=========================================================="
echo "Backend:  http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo "Frontend: http://localhost:5173"
echo "=========================================================="

cleanup() {
    echo -e "\nShutting down Auvyra development services..."
    kill $(jobs -p) 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# 1. Start Backend API
echo "→ Starting Backend API on http://0.0.0.0:8000..."
python3 -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# 2. Start Video Worker
echo "→ Starting Video Generation Worker..."
python3 -m backend.app.workers.video_worker &
WORKER_PID=$!

# 3. Start Frontend (Vite Dev Server)
if [ -d "frontend" ]; then
    echo "→ Starting Frontend Dev Server on http://localhost:5173..."
    cd frontend
    npm run dev -- --host 0.0.0.0 &
    FRONTEND_PID=$!
    cd "$PROJECT_ROOT"
fi

echo "All services running! Press Ctrl+C to stop."
wait

