#!/usr/bin/env python3
"""
Auvyra Environment Doctor
Checks all system and runtime dependencies for Phase 1 production readiness.
Outputs clear status for each dependency: [PASS], [FAIL], [WARNING], [BLOCKED].
"""

import sys
import os
import shutil
import asyncio
import subprocess
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.config import get_settings

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

results = []

def record(name: str, status: str, message: str, details: str = ""):
    results.append((name, status, message, details))
    color = GREEN if status == "PASS" else (RED if status == "FAIL" else YELLOW)
    print(f"[{color}{status:7s}{RESET}] {BOLD}{name}{RESET}: {message}")
    if details:
        print(f"          ↳ {CYAN}{details}{RESET}")

def check_python():
    v = sys.version_info
    v_str = f"{v.major}.{v.minor}.{v.micro}"
    if v.major == 3 and v.minor >= 11:
        record("Python Version", "PASS", f"Python {v_str} (>= 3.11 required)", sys.executable)
    else:
        record("Python Version", "FAIL", f"Python {v_str} (Python >= 3.11 required)", sys.executable)

def check_node():
    node = shutil.which("node")
    npm = shutil.which("npm")
    if node and npm:
        try:
            node_v = subprocess.check_output([node, "--version"]).decode().strip()
            npm_v = subprocess.check_output([npm, "--version"]).decode().strip()
            record("Node.js & npm", "PASS", f"Node {node_v}, npm {npm_v}", f"Node: {node}")
        except Exception as e:
            record("Node.js & npm", "WARNING", f"Error checking Node version: {e}")
    else:
        record("Node.js & npm", "FAIL", "Node.js or npm not found in PATH")

def check_ffmpeg():
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg and ffprobe:
        try:
            out = subprocess.check_output([ffmpeg, "-version"]).decode()
            first_line = out.split("\n")[0]
            record("FFmpeg & FFprobe", "PASS", first_line, f"Path: {ffmpeg}")
        except Exception as e:
            record("FFmpeg & FFprobe", "WARNING", f"Error executing ffmpeg: {e}")
    else:
        record("FFmpeg & FFprobe", "FAIL", "ffmpeg or ffprobe not installed in system PATH")

async def check_mongodb(settings):
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        client = AsyncIOMotorClient(settings.MONGODB_URI, serverSelectionTimeoutMS=3000)
        await client.admin.command("ping")
        record("MongoDB Connection", "PASS", f"Connected to {settings.MONGODB_DATABASE} successfully", settings.MONGODB_URI.split("@")[-1])
        client.close()
    except Exception as e:
        record("MongoDB Connection", "FAIL", f"Cannot connect to MongoDB: {e}", settings.MONGODB_URI)

async def check_ollama(settings):
    import httpx
    base_url = settings.OLLAMA_BASE_URL.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(f"{base_url}/api/tags")
            if resp.status_code == 200:
                tags = resp.json().get("models", [])
                model_names = [m.get("name") for m in tags]
                target_model = settings.OLLAMA_MODEL
                
                # Check if target model or prefix matches
                has_model = any(target_model in m or m.startswith(target_model.split(":")[0]) for m in model_names)
                if has_model:
                    record("Ollama Service", "PASS", f"Online at {base_url}", f"Configured model '{target_model}' is available")
                else:
                    record("Ollama Service", "WARNING", f"Online, but model '{target_model}' not found in tags", f"Installed: {', '.join(model_names) if model_names else 'none'}. Run: ollama pull {target_model}")
            else:
                record("Ollama Service", "FAIL", f"Returned status {resp.status_code}", base_url)
    except Exception as e:
        record("Ollama Service", "FAIL", f"Cannot connect to Ollama at {base_url}: {e}")

async def check_ollama_inference(settings):
    try:
        from backend.app.ai.gateway import AIGateway
        gateway = AIGateway(settings)
        test_resp = await gateway._chat("You are a test assistant.", "Respond with exactly one word: Ready.", temperature=0.1)
        record("Ollama Inference", "PASS", f"Live inference verified: '{test_resp.strip()}'", f"Model: {settings.OLLAMA_MODEL}")
    except Exception as e:
        record("Ollama Inference", "FAIL", f"Live inference test failed: {e}")

async def check_tts():
    try:
        import edge_tts
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
            temp_path = tf.name
        
        communicate = edge_tts.Communicate("Auvyra production doctor check.", "en-US-AriaNeural")
        await communicate.save(temp_path)
        
        if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
            record("Edge TTS Synthesis", "PASS", "Edge TTS synthesized test audio successfully", f"File size: {os.path.getsize(temp_path)} bytes")
            os.unlink(temp_path)
        else:
            record("Edge TTS Synthesis", "FAIL", "Synthesized audio file was empty or missing")
    except Exception as e:
        record("Edge TTS Synthesis", "FAIL", f"Edge TTS check failed: {e}")

def check_google_oauth(settings):
    cid = settings.GOOGLE_CLIENT_ID
    csec = settings.GOOGLE_CLIENT_SECRET
    
    if cid and csec and not cid.startswith("your-") and not csec.startswith("your-"):
        record("Google OAuth Config", "PASS", "Client ID & Secret configured", f"Redirect: {settings.GOOGLE_REDIRECT_URI}")
    else:
        record(
            "Google OAuth Config",
            "BLOCKED",
            "Google OAuth is not configured. YouTube publishing requires real OAuth credentials in .env",
            "See docs/SETUP_REQUIRED.md for Google Cloud Console setup guide."
        )

def check_fernet_key(settings):
    try:
        key = settings.ENCRYPTION_KEY
        f = settings.get_fernet()
        enc = f.encrypt(b"auvyra-test-payload")
        dec = f.decrypt(enc)
        assert dec == b"auvyra-test-payload"
        record("Fernet Token Encryption", "PASS", "Fernet key valid and encryption/decryption operational")
    except Exception as e:
        record("Fernet Token Encryption", "FAIL", f"Fernet key is invalid: {e}")

async def main():
    print(f"\n{BOLD}{CYAN}=== Auvyra Environment Doctor ==={RESET}\n")
    settings = get_settings()

    check_python()
    check_node()
    check_ffmpeg()
    check_fernet_key(settings)
    await check_mongodb(settings)
    await check_ollama(settings)
    await check_ollama_inference(settings)
    await check_tts()
    check_google_oauth(settings)

    print(f"\n{BOLD}{CYAN}=== Diagnostic Summary ==={RESET}")
    passes = sum(1 for _, s, _, _ in results if s == "PASS")
    fails = sum(1 for _, s, _, _ in results if s == "FAIL")
    warns = sum(1 for _, s, _, _ in results if s == "WARNING")
    blocked = sum(1 for _, s, _, _ in results if s == "BLOCKED")

    print(f"Total Checks: {len(results)} | {GREEN}PASS: {passes}{RESET} | {RED}FAIL: {fails}{RESET} | {YELLOW}WARN: {warns}{RESET} | {YELLOW}BLOCKED: {blocked}{RESET}")

    if fails > 0:
        print(f"\n{RED}{BOLD}[FAIL] Critical system dependencies are missing or failing.{RESET}")
        sys.exit(1)
    elif blocked > 0:
        print(f"\n{YELLOW}{BOLD}[READY WITH EXTERNAL BLOCKERS] Core engine is ready. YouTube integration is BLOCKED until real Google credentials are configured in .env.{RESET}")
        sys.exit(0)
    else:
        print(f"\n{GREEN}{BOLD}[PASS] All system and external dependencies are fully operational!{RESET}")
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())

