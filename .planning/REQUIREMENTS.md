# Requirements Specification: Auvyra Phase 1

This document defines the functional and non-functional requirements for Auvyra Phase 1 — Production Ready Autonomous YouTube Operating System.

---

## 1. Authentication & Security
- **AUTH-01:** Email and password registration with bcrypt hashing (min 8 characters).
- **AUTH-02:** Access token (JWT, short-lived) and refresh token (random, SHA-256 hashed in DB) lifecycle.
- **AUTH-03:** OAuth credentials and tokens must be encrypted at rest using Fernet AES-128. Encryption key must be loaded deterministically from environment.
- **AUTH-04:** Strict multi-tenant isolation: all MongoDB queries for channels, videos, assets, jobs, and brains must be scoped by `user_id`.
- **AUTH-05:** Secrets (OAuth client secret, JWT secret, Fernet key, Pexels API key) must never be logged or returned to frontend clients.

---

## 2. YouTube OAuth & Real Channel Connection
- **YT-01:** Google OAuth 2.0 must request canonical scopes: `youtube.readonly`, `youtube.upload`, `yt-analytics.readonly`.
- **YT-02:** Granted scopes must be verified on callback. If any required scope is missing, channel status must be marked `reauthorization_required` and UI must display `Reconnect YouTube`.
- **YT-03:** YouTube Data API v3 `channels.list(mine=true)` must retrieve the real channel ID, title, handle, thumbnail, and subscriber count.
- **YT-04:** Automatic access token refresh using stored encrypted refresh token when calling Google APIs.
- **YT-05:** Frontend must cleanly distinguish between a local manual channel and a verified connected YouTube channel.

---

## 3. Channel Onboarding & Channel Brain
- **BRAIN-01:** Post-connection onboarding wizard collecting: niche, target audience, language, country, tone, content pillars, blocked topics, and reference channels.
- **BRAIN-02:** Ollama AI generates strategic channel positioning, content pillars, hook rules, and CTA strategy based on onboarding answers.
- **BRAIN-03:** Durable `ChannelBrain` MongoDB collection storing positioning, pillars, tone, winning/losing topics, winning/losing hooks, title patterns, best publish times, learned rules, and strategy version.
- **BRAIN-04:** Channel memory must be strictly isolated per channel (Channel A memory never affects Channel B).
- **BRAIN-05:** Dedicated AI Brain inspection and editing page (`/brain`) with strategy refresh capability.

---

## 4. Research & Opportunity Engine
- **RES-01:** Research engine analyzes real market signals and niche evidence without fabricating trends.
- **RES-02:** Structured opportunity scoring returning: topic, opportunity score, why now, evidence, sources, demand signal, competition signal, content gap, and recommended hook.
- **RES-03:** AI Opportunity Feed in frontend (`/research`) with 1-click "Create Script" transition.
- **RES-04:** Research queries must respect Channel Brain content pillars and avoid blocked topics.

---

## 5. Script & AI Gateway
- **SCR-01:** Ollama integration via AsyncOpenAI client with self-healing JSON extraction and Pydantic validation.
- **SCR-02:** Structured Shorts scripts containing: Hook (0–3s), Body, Transitions, Payoff, and CTA.
- **SCR-03:** Script versioning and editing actions (regenerate, shorten, change tone, rewrite).

---

## 6. Visual Storyboard Engine
- **SB-01:** VisualStoryboard model decomposing script narration into timed scenes of 2–5 seconds duration.
- **SB-02:** Each scene must define: `scene_id`, `start_time`, `end_time`, `duration`, `narration`, `visual_query`, `visual_type`, `caption`, `transition`, `text_overlay`.
- **SB-03:** Narration-to-visual query generator using Ollama to extract concrete visual stock search terms from narration sentences.
- **SB-04:** Visual storyboard must be generated and persisted before media search and video rendering.

---

## 7. Pexels Stock Video Pipeline
- **PEX-01:** `PexelsStockService` integrating with live Pexels API using `PEXELS_API_KEY`.
- **PEX-02:** Per-scene search: executes targeted search for each storyboard scene query.
- **PEX-03:** Orientation handling: prefers native portrait 9:16; falls back to landscape footage with intelligent center-cropping to 1080x1920 without aspect distortion.
- **PEX-04:** Candidate ranking prioritizing resolution ($\ge 720\text{p}$), duration ($\ge \text{scene duration}$), and relevance.
- **PEX-05:** Media caching on local disk by URL hash to avoid redundant downloads.
- **PEX-06:** Semantic fallback query if primary search returns zero results; explicit failure reporting if footage is unavailable (never pretend stock footage was used).
- **PEX-07:** Real pixels must reach the final MP4; final video must achieve 70%–90%+ stock footage timeline coverage.

---

## 8. Video Composition, Audio, Subtitles & QA
- **VID-01:** Multi-clip timeline assembly with FFmpeg, trimming and cropping clips to exact scene boundaries.
- **VID-02:** Edge-TTS neural voice synthesis with configurable voice names and speech rates.
- **VID-03:** Faster-whisper subtitle generation synchronized to spoken narration with high-contrast text styling and dark backdrops.
- **VID-04:** Top branded header overlay (`AUVYRA | {TOPIC}`).
- **VID-05:** Automated video inspection tool (`scripts/inspect_video.py`) sampling 10 frames (0% to 90%) to calculate frame similarity, stock coverage %, and blank frames.
- **VID-06:** Regression test (`tests/video/test_stock_footage_regression.py`) ensuring videos do not regress to static gradient backgrounds with word-by-word text changes.
- **VID-07:** In-browser HTTP 206 Partial Content video streaming and playback.

---

## 9. Metadata & Thumbnail Pipeline
- **META-01:** Generates YouTube title, description, hashtags, tags, CTA, category, and pinned comment using Ollama and Channel Brain.
- **THUMB-01:** Generates branded thumbnail asset based on topic, hook, and video frame.

---

## 10. Real YouTube Publishing & Scheduling
- **PUB-01:** Authenticated resumable video upload via YouTube Data API v3 with privacy setting (`private`, `unlisted`, `public`).
- **PUB-02:** Returns real `youtube_video_id` and verifies video existence via API.
- **PUB-03:** Frontend Content Calendar (`Publishing.tsx`) showing drafts, ready, scheduled, published, and failed videos with 1-click publishing.

---

## 11. Real YouTube Analytics & Self-Learning Loop
- **ANA-01:** Ingests real performance metrics from YouTube Analytics API v2 (views, watch time, average view duration, likes, comments, shares, subscribers).
- **ANA-02:** Real Analytics frontend dashboard (`Analytics.tsx`) with historical trends and AI performance analysis.
- **LRN-01:** Learning engine analyzes video metrics to produce observations, insights, confidence, and recommended actions.
- **LRN-02:** Channel Brain updates winning/losing hooks, topics, and learned rules based on real data; subsequent research runs use the updated brain.

---

## 12. Autonomous Autopilot Engine
- **AUTO-01:** `AutopilotService` orchestrating the 21-step autonomous cycle via persistent background jobs.
- **AUTO-02:** Three operating modes: `OFF`, `ASSISTED` (pauses for approval at gates), `FULL_AUTOPILOT` (runs end-to-end automatically).
- **AUTO-03:** Configurable settings: `videos_per_week`, `content_pillars`, `blocked_topics`, `publish_time`, `timezone`, `min_quality_score`, `approval_required`.
- **AUTO-04:** Dedicated Autopilot control page (`Autopilot.tsx`) displaying cycle state, upcoming schedule, and decision logs.

---

## 13. Verification & Acceptance
- **VER-01:** `scripts/doctor.py` validates all environment services (Python, Node, MongoDB, Ollama, Pexels, FFmpeg, TTS, Google OAuth).
- **VER-02:** `scripts/test_pexels.py` verifies live Pexels search, download, and ffprobe inspection.
- **VER-03:** `scripts/verify.sh` runs linting, unit tests, integration tests, video regression tests, frontend build, and production checks.
- **VER-04:** Real Chrome browser user acceptance test verifying the complete user journey end-to-end.
- **VER-05:** Final certification document (`docs/AUVYRA_FINAL_CERTIFICATION.md`) with zero-mock verification.
