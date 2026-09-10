# Auvyra

## What This Is

Auvyra is an autonomous YouTube content operating system ("Your YouTube Channel. On Autopilot."). It connects to a creator's real YouTube channel, researches high-opportunity niche content, generates structured scripts and visual storyboards, downloads and smart-crops real Pexels stock footage, synthesizes voiceovers and subtitles, renders 1080x1920 portrait videos (Shorts), publishes to YouTube, retrieves analytics, and updates a durable Channel Brain to improve performance autonomously across subsequent cycles.

## Core Value

An autonomous, closed-loop YouTube operating runtime where a user can connect a real YouTube channel, set their publishing strategy, and let Auvyra research, produce, publish, analyze, and learn from real video content on autopilot without manual intervention.

## Requirements

### Validated

- [x] FastAPI asynchronous backend architecture with Motor (MongoDB) multi-tenant repository boundaries.
- [x] Local LLM gateway (Ollama `llama3.1:8b`) with structured Pydantic validation and self-healing JSON retry.
- [x] Google OAuth 2.0 with canonical YouTube scopes (`youtube.readonly`, `youtube.upload`, `yt-analytics.readonly`) and Fernet AES-128 token encryption at rest.
- [x] Edge-TTS neural speech synthesis and faster-whisper subtitle generation.
- [x] Zero-mock policy: No fake channel IDs, mock video IDs, or fabricated analytics numbers.
- [x] HTTP 206 Partial Content video streaming endpoint for in-browser playback.

### Active Scope (Production Hardening & Completion)

- [ ] Real Pexels stock video pipeline downloading and smart-cropping actual footage covering 70%–90%+ of the visual timeline.
- [ ] Visual Storyboard Engine converting script narration into 2–5s timed scenes with concrete visual search queries.
- [ ] Persistent Channel Brain and interactive Channel Onboarding wizard.
- [ ] AI Opportunity Feed in Research with 1-click script generation handoff.
- [ ] Autopilot Engine (`AutopilotService` + background worker) executing the 21-step content cycle autonomously (`Off`, `Assisted`, `Full Autopilot`).
- [ ] Automated video inspection QA tool (`scripts/inspect_video.py`) and stock footage regression test (`tests/video/test_stock_footage_regression.py`).
- [ ] Real YouTube publishing calendar and scheduling in frontend (`Publishing.tsx`).
- [ ] Real YouTube Analytics dashboard displaying genuine metrics and AI-driven insights in `Analytics.tsx`.
- [ ] Dedicated AI Brain (`Brain.tsx`) and Autopilot (`Autopilot.tsx`) control pages.
- [ ] Full end-to-end browser user acceptance test via Antigravity Browser Agent.

### Out of Scope

- Direct in-browser non-linear video editing (Auvyra is an autonomous operating system, not a manual editor).
- TikTok / Instagram multi-platform auto-posting in Phase 1 (focus strictly on YouTube Shorts).
- Synthetic AI avatars/talking heads (focus on high-retention stock footage sequences + typography + voice).

## Context

- **Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, Motor, MongoDB, React 18, TypeScript, Vite, Tailwind CSS, FFmpeg 9.0+, Edge-TTS, faster-whisper, Ollama.
- **Stock Footage:** `PEXELS_API_KEY` configured in `.env`.
- **Google OAuth:** Configured for local development (`http://localhost:8000/api/auth/google/callback`).

## Key Constraints

- **Strict Zero-Mock Policy:** Never fake successful integrations, simulate analytics views, or generate placeholder video backgrounds.
- **Stock Footage Quality:** At least 70%–90% of the visual timeline must contain real, relevant stock footage when Pexels is available.
- **Multi-Tenant Isolation:** Channel A's memory, analytics, and assets must never be accessible or shared with Channel B.
- **Autopilot Safety:** Default to `approval_required: true` in Assisted mode; Full Autopilot must strictly follow configured policies.
