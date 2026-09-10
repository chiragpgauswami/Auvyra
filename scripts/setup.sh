#!/usr/bin/env bash
# ==============================================================================
# Auvyra — Environment Setup Script
# Installs backend Python dependencies and frontend npm dependencies
# ==============================================================================
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== Auvyra Environment Setup ==="

# 1. Setup Python virtual environment
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment in .venv..."
    python3 -m venv .venv
fi
source .venv/bin/activate

echo "Upgrading pip and installing Python dependencies..."
pip install --upgrade pip
pip install -e .

# 2. Setup Node frontend
if [ -d "frontend" ]; then
    echo "Installing frontend dependencies..."
    cd frontend
    npm install
    cd "$PROJECT_ROOT"
fi

# 3. Create .env if missing
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    echo "Copying .env.example to .env..."
    cp .env.example .env
fi

# 4. Create media directory structure
mkdir -p media/videos media/audio media/images media/thumbnails media/temp /tmp/auvyra-video-qa

echo "Running environment doctor..."
python3 scripts/doctor.py

echo "=== Setup complete! Run './scripts/dev.sh' to start development ==="

