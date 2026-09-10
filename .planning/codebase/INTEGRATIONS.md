# External Integrations

**Analysis Date:** 2026-09-10

## Authentication & Identity

### Google OAuth 2.0
- **Purpose**: Authenticates YouTube creators, acquires delegated YouTube channel management authority, and allows resumable video publishing and channel analytics querying.
- **Protocol**: OAuth 2.0 Authorization Code Grant (`backend/app/auth/router.py`, `backend/app/auth/service.py`).
- **Authorization Endpoint**: `https://accounts.google.com/o/oauth2/v2/auth` with `access_type=offline`, `prompt=consent`, and `include_granted_scopes=true`.
- **Token Exchange Endpoint**: `https://oauth2.googleapis.com/token`.
- **User Profile Endpoint**: `https://www.googleapis.com/oauth2/v2/userinfo`.
- **Canonical Scopes (`backend/app/youtube/scopes.py`)**:
  - Identity Scopes: `openid`, `https://www.googleapis.com/auth/userinfo.email`, `https://www.googleapis.com/auth/userinfo.profile`.
  - Channel Management: `https://www.googleapis.com/auth/youtube.readonly` (reading channel details, subscribers, metadata).
  - Video Publishing: `https://www.googleapis.com/auth/youtube.upload` (initiating resumable video uploads and setting privacy).
  - Analytics: `https://www.googleapis.com/auth/yt-analytics.readonly` (fetching channel and video reporting data).
- **Scope Verification & Enforcement**:
  - `verify_granted_scopes()` audits scopes returned during token exchange.
  - Channels without `youtube.readonly` or `youtube.upload` are marked with `needs_reauthorization=True`.
  - Strict zero-mock enforcement: Publishing attempts without real valid tokens raise `GOOGLE_OAUTH_NOT_CONFIGURED` (`backend/app/services/publishing_service.py`).
- **Token Security & Storage**:
  - Google access tokens and refresh tokens are encrypted at rest using AES Fernet keys (`backend/app/auth/service.py`) before storage in MongoDB `oauth_accounts` collection.
  - Dedicated disconnect route: `DELETE /api/auth/google/disconnect` deletes OAuth records, enabling pristine re-authorization.

### Internal Authentication & Session Architecture
- **JWT Access Tokens**:
  - Signed with HMAC-SHA256 (`HS256`) via `python-jose` (`backend/app/auth/service.py`).
  - Default expiration: 30 minutes (`ACCESS_TOKEN_EXPIRE_MINUTES`).
  - Contains user ID in `sub` claim and token type verification (`type: access`).
- **Refresh Tokens & Session Rotation**:
  - Cryptographically secure 48-byte random token (`secrets.token_urlsafe(48)`).
  - Stored exclusively as a SHA-256 hash (`hashlib.sha256`) in MongoDB `sessions` collection.
  - Lifespan: 7 days (`REFRESH_TOKEN_EXPIRE_DAYS`).
  - Single-use token rotation: Refreshing revokes previous session and issues a fresh token pair.
  - Password resets immediately invalidate all active user sessions (`SessionRepository.revoke_all_user_sessions`).

---

## External APIs & Services

### 1. YouTube Data API v3
- **Base URL**: `https://www.googleapis.com/youtube/v3`
- **Upload URL**: `https://www.googleapis.com/upload/youtube/v3/videos`
- **Implementation**: `YouTubeClient` (`backend/app/youtube/client.py`).
- **Operations Supported**:
  - **Channel Auto-Discovery**: `GET /channels?part=snippet,statistics&mine=true` extracts authenticated channel ID, title, handle/custom URL, thumbnail URL, subscriber count, and video count. Automatically links or creates channel in `channels` collection.
  - **Resumable Video Uploads**:
    - Step 1: Initiates resumable upload session with `POST /upload/youtube/v3/videos?uploadType=resumable&part=snippet,status`, setting title, description, tags, category (`28` - Science & Technology), privacy status (`private`, `unlisted`, `public`), and `selfDeclaredMadeForKids: false`.
    - Step 2: Streams binary MP4 video to the returned upload location header via `PUT` with `X-Upload-Content-Type: video/mp4`.
- **Error Classification**:
  - Parses structured Google API errors into explicit typed exceptions (`YouTubeAPIError`):
    - `YOUTUBE_AUTH_EXPIRED` (HTTP 401)
    - `YOUTUBE_QUOTA_EXCEEDED` (HTTP 403)
    - `YOUTUBE_INSUFFICIENT_SCOPES` (HTTP 403)
    - `YOUTUBE_PERMISSION_DENIED` (HTTP 403)
    - `YOUTUBE_NOT_FOUND` (HTTP 404)
    - `YOUTUBE_SERVER_ERROR` (HTTP 500+) with automatic retry flag.

### 2. YouTube Analytics API v2
- **Base URL**: `https://youtubeanalytics.googleapis.com/v2/reports`
- **Implementation**: `YouTubeClient.get_channel_reports()` (`backend/app/youtube/client.py`).
- **Query Metrics**:
  - Fetches daily granular performance: `views`, `estimatedMinutesWatched`, `averageViewDuration`, `subscribersGained`, `likes`, `comments`, `shares`.
  - Processed by `AnalyticsWorker` (`backend/app/workers/analytics_worker.py`) and stored in `analytics_snapshots` collection.
  - Consumed by `AnalyticsService` (`backend/app/services/analytics_service.py`) to derive engagement rates, retention patterns, and AI strategic recommendations.

### 3. Ollama Local AI Service
- **Base URL**: Configurable via `OLLAMA_BASE_URL` (default: `http://localhost:11434`), model `OLLAMA_MODEL` (default: `llama3.1:8b`).
- **Interface Protocol**: OpenAI-compatible REST API (`/v1/chat/completions`) wrapped by `openai.AsyncOpenAI` (`backend/app/ai/gateway.py`).
- **Functional Roles**:
  - **Scriptwriting & Hook Generation**: Generates multi-hook scripts (`generate_structured_script`) with hook scoring, structural outline, narration text, and call-to-action calibrated to target video duration.
  - **Opportunity Research**: Produces structured market intelligence (`ResearchOpportunity`) including why now, audience evidence, content gaps, recommended angles, and confidence ratings.
  - **Asset Tagging & Search Query Generation**: Extracts visual search terms from narration scripts (`generate_search_terms`).
  - **Strategic Analysis**: Evaluates channel memory and analytics snapshots to identify winning content patterns (`analyze_performance`, `generate_strategy_insights`).
- **Resilience & Self-Healing**:
  - Intercepts connection downtime with `OllamaUnavailableError` (`HTTP 503 SERVICE_UNAVAILABLE`).
  - JSON syntax repair (`extract_json`, `repair_json_string`) eliminating markdown backticks and trailing commas.
  - Multi-turn schema correction: Up to 3 attempts with iterative system repair notes when JSON parsing or Pydantic validation fails.

### 4. Microsoft Edge TTS (Text-to-Speech)
- **Protocol**: Direct WebSocket / HTTP streaming using `edge-tts` (`backend/app/video/audio/edge_tts_provider.py`).
- **Key Features**:
  - Free, zero-API-key neural voice synthesis.
  - Supported voices: `en-US-AriaNeural`, `en-US-GuyNeural`, `en-US-JennyNeural`, `en-GB-SoniaNeural`.
  - Configurable rate adjustments (`+10%`, `-15%`).
  - Generates synchronized word-boundary timing events using `edge_tts.SubMaker` to produce millisecond-accurate SRT subtitle files.
  - Calculates audio duration using `backend/app/video/audio/duration.py` with fallback to `pydub`.

### 5. Pexels Stock Media API
- **Base URL**: `https://api.pexels.com/v1/videos/search`
- **Implementation**: `PexelsProvider` (`backend/app/video/media/pexels_provider.py`).
- **Capabilities**:
  - Dynamic stock footage retrieval filtered by search terms, orientation (`portrait`, `landscape`, `square`), and minimum duration.
  - Multi-key rotation support: Ingests comma-separated list of keys from `PEXELS_API_KEY` and alternates round-robin to maximize quota throughput.
  - Streaming file download via `httpx` with local file hash deduplication.
- **Local Fallback**:
  - When `PEXELS_API_KEY` is not provided or API calls fail, system seamlessly falls back to `LocalMediaProvider` (`backend/app/video/media/local_provider.py`), allowing fully offline media generation.

---

## Data Storage

### MongoDB Database
- **Driver**: `motor.motor_asyncio.AsyncIOMotorClient` (`backend/app/database.py`).
- **Connection**: Configured via `MONGODB_URI` and `MONGODB_DATABASE` (test isolation via `MONGODB_TEST_DATABASE`).
- **Schema & Collections**:
  - `users`: User registration, profile details, and bcrypt password hash.
  - `oauth_accounts`: Third-party provider identity, encrypted tokens, granted scopes.
  - `sessions`: Active refresh token hashes, expiration dates, validity flags.
  - `channels`: YouTube channels, handle, subscriber count, avatar URL, automation settings (`autopilot_enabled`, `approval_required`).
  - `channel_memory`: Persistent longitudinal memory holding strategic channel context and top topic performance.
  - `content_ideas`: AI-generated and user-submitted content ideas with status pipeline (`idea`, `scripted`, `approved`, `rejected`).
  - `videos`: Master video records, rendering metadata, storage paths, and published YouTube video IDs.
  - `analytics_snapshots`: Timestamped snapshots of channel and video performance metrics.
  - `strategy_insights`: Actionable recommendations with confidence scoring and supporting metrics.
  - `jobs`: Asynchronous worker tasks (`video_generation`, `research`, `script_generation`, `publishing`, `analytics_sync`, `learning`).
  - `notifications`: User alerts and asynchronous job event notifications.
- **Indexes**:
  - `users.email` (unique)
  - `channels.youtube_channel_id` (unique, sparse)
  - `channels.user_id`, `oauth_accounts.user_id`, `strategy_insights.channel_id`
  - Compound indexes: `content_ideas(channel_id, status)`, `videos(channel_id, status)`, `videos(channel_id, published_at DESC)`, `analytics_snapshots(channel_id, video_id)`, `jobs(status, created_at)`.

### Local Filesystem Media Storage
- **Implementation**: `LocalStorageProvider` (`backend/app/storage/local.py`).
- **Root Directory**: `MEDIA_ROOT` (default `media/` relative to project root).
- **Subdirectory Layout**:
  - `media/videos/`: Final assembled and rendered MP4 files.
  - `media/audio/`: Synthesized speech narration (`narration.mp3`) and background music.
  - `media/images/`: Stock stills and generated visual slides.
  - `media/thumbnails/`: Video cover images and thumbnails.
  - `media/temp/`: Ephemeral render directories (`auvyra_video_*`), SRT subtitle files, and intermediate FFmpeg clip concatenations.
- **Path Security**: All operations validate target paths against the root directory using `_validate_safe_path` to prevent path traversal (`../`) attacks.
- **API Access**: Mounted as static files on the FastAPI backend at `/media` (`backend/app/main.py`).

---

## Webhooks & Event Streams

- **Inbound Webhooks**:
  - No inbound webhooks are currently implemented or required.
  - YouTube OAuth operates strictly via browser redirection and authorization code callbacks (`GET /api/auth/google/callback`).
  - Media asset ingestion (Pexels, YouTube) is strictly pull-based.
- **Real-Time Client Updates**:
  - The system utilizes client-side short-polling rather than WebSockets or Server-Sent Events (SSE).
  - Frontend uses a reusable React hook `usePolling` (`frontend/src/hooks/usePolling.ts`) querying `GET /api/jobs/{job_id}/progress` every 2,000 milliseconds.
  - Responses return standardized progress payloads: `stage`, `percent` (0-100), `status` (`queued`, `processing`, `completed`, `failed`), and user-facing status messages.
- **Internal Worker Task Distribution**:
  - Background workers (`backend/app/workers/runner.py`) poll the MongoDB `jobs` collection using atomic `find_one_and_update` with status transitions (`queued` -> `processing` -> `completed` / `failed`).
  - Worker polling interval defaults to 2.0s - 3.0s (`WORKER_POLL_INTERVAL`).

---

## Rate Limits & Quotas

### YouTube Data API v3
- **Quota Allocation**: Default 10,000 units per day per Google Cloud project.
- **Operation Costs**:
  - Resumable video upload (`videos.insert`): 1,600 units (~6 uploads per project per day on free tier).
  - Channel metadata read (`channels.list`): 1 unit.
  - Video status read (`videos.list`): 1 unit.
- **Quota Handling**: `YouTubeClient` parses Google error responses for quota exhaustion messages and converts them to `YOUTUBE_QUOTA_EXCEEDED` (HTTP 403), alerting creators that quotas reset daily at midnight Pacific Time (PT).

### YouTube Analytics API v2
- **Quota Pool**: Tracked independently from the YouTube Data API.
- **Limits**: Standard Google Cloud per-minute and per-day user/project quotas.
- **Throttling Strategy**: Periodic scheduled syncs (`AnalyticsWorker`) rather than per-request calls prevent rate spikes.

### Pexels API
- **Limits**: 200 requests per hour; 20,000 requests per month on the standard free tier.
- **Throttling & Load Distribution**:
  - Multi-key rotation support: `PexelsProvider` splits comma-separated keys and rotates on each request.
  - Local caching: Reuses previously downloaded videos based on URL hashes (`pexels_{hash}.mp4`) to avoid duplicate downloads.
  - Automatic fallback: Defaults to `LocalMediaProvider` when quota is exhausted or key is omitted.

### Ollama Local Inference
- **Limits**: Uncapped by external rate limits (constrained only by local GPU/CPU compute capability).
- **Concurrency & Timeouts**:
  - Inference timeouts governed by `OLLAMA_TIMEOUT_SECONDS` (default: 60.0s).
  - Background worker concurrency prevents overlapping heavy generation requests from saturating hardware resources.

### Microsoft Edge TTS
- **Limits**: Public Microsoft endpoint without formal developer token quotas.
- **Best Practices**: Requests are executed sequentially per video job, preventing abrupt connection throttling.

---
*Integration analysis: 2026-09-10*
