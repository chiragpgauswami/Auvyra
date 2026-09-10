# Auvyra Implementation Roadmap

This roadmap organizes the development of Auvyra Phase 1 into 17 sequential, verifiable phases. Each phase follows the GSD discipline: **DISCUSS → PLAN → EXECUTE → VERIFY → SHIP**.

---

## Milestone 1: Production Core & Autonomous Operating System

### Phase 1: Current-State Audit & Architecture Reconciliation
- **Goal:** Audit existing codebase, establish zero-mock baseline, create diagnostic scripts, and document technical debt.
- **Key Deliverables:** `docs/AUVYRA_IMPLEMENTATION_AUDIT.md`, `docs/AUVYRA_GSD_BASELINE.md`, `.planning/codebase/` map.
- **Verification:** All 7 codebase documents exist; `doctor.py` passes.

### Phase 2: YouTube OAuth & Real Channel Connection
- **Goal:** Ensure bulletproof Google OAuth flow, canonical scope validation, encrypted token refresh loop, and real channel retrieval.
- **Key Deliverables:** Scope verification, token refresh mechanism in `YouTubeClient`, channel statistics persistence, re-auth banners.
- **Verification:** `scripts/test_youtube_oauth.py` passes; channel verified via live Google token.

### Phase 3: Channel Onboarding & Channel Brain
- **Goal:** Build durable, isolated per-channel intelligence and an interactive onboarding flow.
- **Key Deliverables:** `ChannelBrain` schema, MongoDB repository, onboarding endpoint `POST /api/channels/{id}/onboard`, AI positioning generator.
- **Verification:** Channel A and Channel B brains tested for complete data boundary isolation.

### Phase 4: Research & Opportunity Engine
- **Goal:** Build genuine niche research analysis and an AI Opportunity Feed with 1-click script generation handoff.
- **Key Deliverables:** `ResearchOpportunity` generation linked to Channel Brain, AI Opportunity Feed in `Research.tsx`.
- **Verification:** Real research generation returns structured opportunities without trend fabrication.

### Phase 5: Script & Structured AI Generation
- **Goal:** Deliver high-retention Shorts script generation with hook, body, payoff, and CTA structure.
- **Key Deliverables:** Ollama script generation prompts integrating Channel Brain hook rules; script versioning and rewrite actions.
- **Verification:** Pydantic validation passes; script complies with requested duration and structure.

### Phase 6: Visual Storyboard Engine
- **Goal:** Build the scene-by-scene storyboard engine decomposing narration into 2–5s timed scenes with concrete visual queries.
- **Key Deliverables:** `VisualScene` and `VisualStoryboard` models, Ollama narration-to-visual query generator.
- **Verification:** Unit test parses script into timed scenes with distinct visual search terms.

### Phase 7: Pexels Stock Video Pipeline
- **Goal:** Connect live Pexels API, implement per-scene video search, candidate ranking, download caching, and 9:16 smart-cropping.
- **Key Deliverables:** `PexelsStockService`, `scripts/test_pexels.py`, local disk caching, landscape-to-portrait crop fallback.
- **Verification:** `scripts/test_pexels.py` successfully downloads and validates real stock clips.

### Phase 8: Video Composition & Multi-Clip QA
- **Goal:** Overhaul `VideoAssembler` to assemble multi-clip storyboard sequences with $\ge 70\%$ stock footage coverage and automated frame QA.
- **Key Deliverables:** Multi-clip timeline assembler, `scripts/inspect_video.py`, `tests/video/test_stock_footage_regression.py`.
- **Verification:** Rendered MP4 verified with $\ge 70\%$ real stock footage; regression test passes.

### Phase 9: Metadata & Thumbnail Pipeline
- **Goal:** Build AI-driven YouTube metadata and thumbnail generation assets.
- **Key Deliverables:** Metadata generator (titles, descriptions, tags, hashtags, CTA, pinned comment), thumbnail generation service.
- **Verification:** Generated metadata and thumbnail assets saved and linked to video records.

### Phase 10: Real YouTube Publishing & Content Calendar
- **Goal:** Implement full frontend content calendar and reliable resumable YouTube publishing.
- **Key Deliverables:** Real `Publishing.tsx` content calendar (Drafts, Ready, Scheduled, Published, Failed), 1-click publishing.
- **Verification:** Video published to YouTube as PRIVATE or UNLISTED; real video ID verified via API.

### Phase 11: Real Analytics Ingestion
- **Goal:** Connect live YouTube Analytics API v2 to historical snapshots and dashboard charts.
- **Key Deliverables:** `Analytics.tsx` hooked to `/api/analytics` endpoints, historical snapshot storage in MongoDB.
- **Verification:** Analytics endpoint returns real channel metrics or honest empty states (zero mocks).

### Phase 12: Learning Engine & Channel Brain Feedback Loop
- **Goal:** Close the autonomous feedback loop: YouTube analytics update Channel Brain rules and drive subsequent research.
- **Key Deliverables:** Analytics-to-learning evaluation service, Channel Brain rule updates, prompt injection of learned rules.
- **Verification:** Integration test proves updated brain alters subsequent research recommendations.

### Phase 13: Autopilot Engine & Background Worker
- **Goal:** Build `AutopilotService` and background worker running the 21-step content cycle autonomously (`Off`, `Assisted`, `Full Autopilot`).
- **Key Deliverables:** `AutopilotService`, `autopilot_worker.py`, schedule configuration schema, autonomous job queue.
- **Verification:** Autonomous cycle executes from research to publishing without manual human clicks.

### Phase 14: Frontend Workflow Integration
- **Goal:** Transform the frontend from disconnected pages into a unified autonomous operating center.
- **Key Deliverables:** Autonomous Dashboard Control Center, dedicated `Autopilot.tsx` page, dedicated `Brain.tsx` page, Create studio pipeline.
- **Verification:** All frontend navigation, state management, and API calls functional with zero console errors.

### Phase 15: Security & Production Hardening
- **Goal:** Audit authentication boundaries, subprocess execution safety, path traversal guards, and encryption at rest.
- **Key Deliverables:** Path traversal sanitization, stream endpoint token verification, subprocess security audit.
- **Verification:** Security test suite passes; no secrets exposed in client responses.

### Phase 16: Full Real Browser User Acceptance (E2E)
- **Goal:** Execute complete end-to-end user journey in Google Chrome via Puppeteer browser agent.
- **Key Deliverables:** `scripts/real_user_acceptance_browser.js` updated to test all 17 phases.
- **Verification:** 100% PASS on all local pipeline steps, honest BLOCKED on interactive human consent.

### Phase 17: Final Production Certification
- **Goal:** Execute authoritative verification suite (`./scripts/verify.sh`) and produce final certification document.
- **Key Deliverables:** `scripts/verify.sh`, `docs/AUVYRA_FINAL_CERTIFICATION.md`.
- **Verification:** Single-command `./scripts/verify.sh` completes successfully.
