# Auvyra GSD Baseline & Codebase Audit

**Date:** 2026-09-10  
**Target:** Auvyra — Autonomous YouTube Channel Operating System  
**Product Motto:** _"Your YouTube Channel. On Autopilot."_

---

## 1. Executive Summary

This baseline establishes the exact state of the Auvyra codebase prior to GSD phase execution. Auvyra is not starting from scratch; it already has substantial foundations in FastAPI, Motor (MongoDB), React/Vite, and MoneyPrinterTurbo-derived video composition. However, critical runtime pipelines (Pexels per-scene footage, Visual Storyboard, Autopilot Engine, Channel Brain feedback loop, and integrated frontend workflows) are incomplete or absent.

| Category                  | Count | Status Overview                                                                                                                                                                                                                     |
| :------------------------ | :---: | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **IMPLEMENTED**           |  14   | Auth, DB, Repositories, Ollama Gateway, YouTube API Client, Edge-TTS, FFmpeg Codec Fallback, Stream Endpoints, Doctor Script                                                                                                        |
| **PARTIALLY IMPLEMENTED** |   8   | Pexels Provider, Video Pipeline, Channel Memory, Research Service, Publishing Service, Analytics Service, Learning Service, Video Page                                                                                              |
| **BROKEN**                |   3   | Video Visual Quality (static gradient fallback), Analytics Frontend (hardcoded 0s), Token Decryption Persistence across worker restarts                                                                                             |
| **MOCKED**                |   0   | Zero-mock policy strictly maintained in core paths; unconfigured OAuth/YouTube returns honest blocked/400/403 states                                                                                                                |
| **DEAD CODE**             |   2   | Empty placeholder `Publishing.tsx` card, unused `autopilot_enabled` boolean on channel schema                                                                                                                                       |
| **MISSING**               |   7   | Visual Storyboard Engine, Pexels Per-Scene Stock Service, Channel Onboarding Wizard, Channel Brain System, Autopilot Background Engine, Video QA Inspection Tool (`scripts/inspect_video.py`), Dedicated Autopilot & AI Brain Pages |

---

## 2. Detailed Subsystem Audit

### 2.1 Authentication & Security Layer

- **Status:** **IMPLEMENTED**
- **Files:**
  - `backend/app/auth/service.py`
  - `backend/app/auth/router.py`
  - `backend/app/auth/dependencies.py`
  - `backend/app/models/auth.py`
  - `backend/app/repositories/users.py`
- **Findings:**
  - User registration, bcrypt password hashing, login, logout, and refresh tokens are fully functional.
  - Session tokens stored with SHA256 hashes in MongoDB `sessions` collection.
  - OAuth tokens encrypted at rest using Fernet AES-128.
  - Multi-tenant scoping enforced on repository queries (`user_id`).
- **Required Action:** Ensure Fernet encryption key is strictly loaded from `.env` and never falls back to an ephemeral key that invalidates tokens on restart.

---

### 2.2 YouTube OAuth & Channel Integration

- **Status:** **IMPLEMENTED / PARTIALLY IMPLEMENTED**
- **Files:**
  - `backend/app/youtube/client.py`
  - `backend/app/youtube/scopes.py`
  - `backend/app/api/channels.py`
  - `frontend/src/pages/Channels.tsx`
- **Findings:**
  - Canonical scopes defined: `https://www.googleapis.com/auth/youtube.readonly`, `https://www.googleapis.com/auth/youtube.upload`, `https://www.googleapis.com/auth/yt-analytics.readonly`.
  - Google OAuth redirect constructed with `prompt=consent` and `include_granted_scopes=true`.
  - `YouTubeClient.get_my_channel()` successfully calls Google API and returns channel ID, title, handle, thumbnail, and subscriber count.
  - Granted scopes are audited on callback; missing scopes trigger `reauthorization_required` status.
- **Required Action:** Add automatic OAuth token refresh loop using Google's token endpoint when access tokens expire. Store subscriber, view, and video count history in channel document.

---

### 2.3 Channel Brain & Onboarding

- **Status:** **MISSING**
- **Files:**
  - `backend/app/models/channel.py` (only basic `ChannelMemory` stub)
  - `backend/app/repositories/channels.py`
- **Findings:**
  - No onboarding wizard exists after YouTube channel connection.
  - No `ChannelBrain` model representing channel positioning, audience profile, content pillars, tone, hook styles, winning/losing patterns, and learned rules.
  - No dedicated AI Brain inspection and editing page in frontend.
- **Required Action:**
  - Build `ChannelBrain` schema in `backend/app/models/brain.py`.
  - Implement onboarding wizard endpoint `POST /api/channels/{id}/onboard` using Ollama to generate positioning, pillars, and strategy.
  - Create dedicated `Brain.tsx` frontend page.

---

### 2.4 Research & Opportunity Engine

- **Status:** **PARTIALLY IMPLEMENTED**
- **Files:**
  - `backend/app/services/research_service.py`
  - `backend/app/models/content.py`
  - `frontend/src/pages/Research.tsx`
- **Findings:**
  - Backend has structured Pydantic model `ResearchOpportunity` (why now, evidence, content gap, recommended angle, hooks).
  - Frontend `Research.tsx` only provides a single manual topic input box and renders basic findings.
  - No AI Opportunity Feed displaying ranked content opportunities with demand/competition signals.
  - No 1-click transition from opportunity to script generation.
- **Required Action:** Build AI Opportunity Feed in `Research.tsx` with direct 1-click "Create Script" handoff. Connect research prompts to `ChannelBrain` pillars and constraints.

---

### 2.5 Script & Structured AI Generation

- **Status:** **IMPLEMENTED**
- **Files:**
  - `backend/app/ai/gateway.py`
  - `backend/app/services/content_service.py`
  - `backend/app/models/content.py`
- **Findings:**
  - `AIGateway` interfaces with local Ollama (`llama3.1:8b`) via AsyncOpenAI.
  - Implements self-healing JSON parser (`extract_json()`) handling markdown code blocks and invalid syntax.
  - Generates structured scripts with hook, outline, final script, and CTA.
- **Required Action:** Integrate `ChannelBrain` context (tone, audience, hook patterns) into script generation prompts. Add script versioning and rewrite/shorten actions.

---

### 2.6 Visual Storyboard Engine

- **Status:** **MISSING (CRITICAL DEFECT ROOT CAUSE)**
- **Files:**
  - None (currently absent)
- **Findings:**
  - The application currently jumps directly from script to media search using 2–3 words extracted from the title.
  - It does NOT segment the script into timed scenes (2–5 seconds).
  - It does NOT derive specific visual search queries from the narration sentences.
- **Required Action:**
  - Create `backend/app/video/storyboard.py` with `VisualScene` and `VisualStoryboard` schemas.
  - Implement Ollama-powered storyboard generator creating timed scenes with narration-derived visual queries.

---

### 2.7 Pexels Stock Video Pipeline

- **Status:** **PARTIALLY IMPLEMENTED / BROKEN**
- **Files:**
  - `backend/app/video/media/pexels_provider.py`
  - `backend/app/video/pipeline.py`
- **Findings:**
  - `PexelsProvider` exists and can connect to Pexels API with `PEXELS_API_KEY`.
  - However, `pipeline.py` called a single search query on title words, failed to match portrait orientation, and silently fell back to `LocalMediaProvider` which generated static gradients!
  - No candidate ranking (resolution, duration, bitrate).
  - No smart 9:16 center-cropping for landscape footage.
  - No local disk caching by URL hash.
- **Required Action:**
  - Create `backend/app/video/media/pexels_stock_service.py` with per-scene search, candidate ranking, download caching, and landscape-to-portrait crop fallback.
  - Enforce 70%–90%+ stock footage coverage in final MP4.
  - Create `scripts/test_pexels.py` diagnostic script.

---

### 2.8 Video Composition & Quality Assurance

- **Status:** **PARTIALLY IMPLEMENTED**
- **Files:**
  - `backend/app/video/composition/assembler.py`
  - `backend/app/video/composition/overlay.py`
  - `backend/app/video/validation.py`
  - `backend/app/api/videos.py`
- **Findings:**
  - FFmpeg multi-codec fallback (`h264_videotoolbox`, `nvenc`, `libx264`) works reliably.
  - HTTP 206 Partial Content video streaming works in browser.
  - VideoAssembler only assembled a single looped clip.
  - Subtitle styling and top header branding exist.
  - `scripts/inspect_video.py` is missing.
  - `tests/video/test_stock_footage_regression.py` is missing.
- **Required Action:**
  - Update `VideoAssembler` to assemble multi-clip storyboard sequences with smart center-cropping.
  - Build `scripts/inspect_video.py` for automated 10-frame sampling, stock coverage calculation, and blank frame detection.
  - Build `tests/video/test_stock_footage_regression.py`.

---

### 2.9 YouTube Publishing & Content Calendar

- **Status:** **PARTIALLY IMPLEMENTED**
- **Files:**
  - `backend/app/youtube/client.py` (resumable upload implemented)
  - `backend/app/services/publishing_service.py`
  - `frontend/src/pages/Publishing.tsx`
- **Findings:**
  - Backend can upload MP4s to YouTube via Google resumable upload API.
  - Frontend `Publishing.tsx` is completely empty—contains only an empty placeholder card!
  - No content calendar or scheduled queue.
- **Required Action:**
  - Replace `Publishing.tsx` with a real content calendar and status columns (`Drafts`, `Ready`, `Scheduled`, `Published`, `Failed`).
  - Add thumbnail generation and metadata generation pipelines.

---

### 2.10 YouTube Analytics & Learning Loop

- **Status:** **PARTIALLY IMPLEMENTED / BROKEN**
- **Files:**
  - `backend/app/youtube/client.py` (`get_channel_reports()` implemented)
  - `backend/app/services/analytics_service.py`
  - `backend/app/services/learning_service.py`
  - `frontend/src/pages/Analytics.tsx`
- **Findings:**
  - Backend can query YouTube Analytics API v2.
  - Frontend `Analytics.tsx` displays hardcoded zeroes and a disabled chart box.
  - Learning service extracts insights, but the feedback loop is open—insights do not update `ChannelBrain` or alter subsequent research prompts.
- **Required Action:**
  - Connect `Analytics.tsx` to `/api/analytics` endpoints.
  - Close the loop: Analytics sync $\to$ Learning evaluation $\to$ `ChannelBrain` rule updates $\to$ Next research cycle.

---

### 2.11 Autopilot Engine & Runtime Automation

- **Status:** **MISSING (CRITICAL PRODUCT GAP)**
- **Files:**
  - `backend/app/models/channel.py` (contains dead `autopilot_enabled` boolean)
- **Findings:**
  - No background scheduler or execution loop.
  - No modes (`OFF`, `ASSISTED`, `FULL_AUTOPILOT`).
  - No autopilot settings schema (`videos_per_week`, `publish_time`, `content_pillars`, `approval_required`).
  - No `Autopilot.tsx` frontend page.
- **Required Action:**
  - Create `AutopilotService` orchestrating the 21-step autonomous cycle.
  - Build `backend/app/workers/autopilot_worker.py` polling active channels.
  - Create `Autopilot.tsx` control panel in frontend.

---

### 2.12 Frontend Operating System Integration

- **Status:** **PARTIALLY IMPLEMENTED**
- **Files:**
  - `frontend/src/pages/`
- **Findings:**
  - Dashboard is a static counter summary rather than an autonomous control center.
  - Navigation lacks links to Autopilot and AI Brain.
  - Create page does not display the visual pipeline stages.
- **Required Action:**
  - Transform Dashboard into the Autonomous Operating Center.
  - Add navigation routes and components for `/autopilot` and `/brain`.
  - Upgrade `/create` to display live storyboard, stock asset search, voice, and rendering stages.

---

## 3. Immediate Implementation Roadmap

Following GSD's phase-based discipline, the implementation will proceed through the 17 verifiable phases outlined in the project plan.
