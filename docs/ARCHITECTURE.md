# Auvyra System Architecture

Auvyra is an autonomous AI-powered YouTube channel management and video generation platform.

---

## 1. High-Level Architecture Overview

```mermaid
flowchart TD
    User([Creator / Browser]) <-->|Vite + React 18 UI| Frontend[Auvyra Frontend]
    Frontend <-->|REST API + JWT| Backend[FastAPI Backend Application]

    subgraph Core Backend Subsystems
        AuthService[Auth & Encryption Service]
        ChannelService[Channel & Memory Service]
        ContentService[Content & Script Engine]
        VideoService[Video Generation Service]
        PublishingService[Publishing Service]
        AnalyticsService[Analytics Engine]
        LearningService[Strategic Learning Engine]
    end

    Backend --> Core Backend Subsystems

    subgraph External Infrastructure
        Mongo[(MongoDB Database)]
        Ollama[(Local Ollama llama3.1:8b)]
        EdgeTTS[Microsoft Edge TTS Engine]
        FFmpeg[FFmpeg / MoviePy Video Pipeline]
        YouTubeAPI[Google YouTube Data API v3]
        YouTubeAnalytics[Google YouTube Analytics API v2]
    end

    AuthService <-->|Sessions & Users| Mongo
    ChannelService <-->|Channels & Memory| Mongo
    ContentService <-->|Prompt Completion| Ollama
    VideoService -->|Audio Narration| EdgeTTS
    VideoService -->|H.264 Composition| FFmpeg
    VideoService -->|Metadata & Jobs| Mongo
    PublishingService -->|OAuth Upload| YouTubeAPI
    AnalyticsService -->|Metrics Sync| YouTubeAnalytics
    LearningService <-->|Memory Evolution| Mongo
```

---

## 2. The 5-Stage Autonomous Lifecycle

Auvyra executes an autonomous feedback loop:

```
┌──────────────────────────────────────────────────────────┐
│                   THE AUVYRA LIFECYCLE                   │
│                                                          │
│   [ 1. RESEARCH ] ──> [ 2. CREATE ] ──> [ 3. PUBLISH ]   │
│          ▲                                     │         │
│          │                                     ▼         │
│     [ 5. LEARN ]  <────────────────────── [ 4. ANALYZE ]  │
└──────────────────────────────────────────────────────────┘
```

1. **Research:**
   - Input: Topic or niche prompt.
   - Execution: Ollama analyzes competitive angles, extracts high-intent keywords, and proposes 3-5 structured video ideas with target hooks.
2. **Create:**
   - Input: Selected idea or manual topic.
   - Script Engine: Generates timed narration script and visual stock footage queries.
   - Voice Engine: Edge-TTS generates neural speech audio and word-aligned SRT subtitles.
   - Composition Engine: Trims footage to duration, applies aspect ratio transforms (`9:16`, `16:9`, `1:1`), overlays subtitles with drop-shadows, and encodes final MP4 via FFmpeg with hardware codec fallback (`h264_videotoolbox`, `h264_nvenc`, `libx264`).
3. **Publish:**
   - Input: Video file + title, description, tags, privacy setting.
   - Execution: Uploads to YouTube Data API v3 with resumable multipart protocol using refreshed OAuth tokens. If OAuth is unconfigured, cleanly fails with `GOOGLE_OAUTH_NOT_CONFIGURED` (zero mock bypass).
4. **Analyze:**
   - Execution: Syncs real performance snapshots (views, CTR, watch time, retention, subscriber deltas) via YouTube Analytics API v2.
5. **Learn:**
   - Execution: Aggregates real snapshots; compares performance against past videos; derives top topics and winning hooks; persists strategic memory to MongoDB (`channel_memory`).

---

## 3. Security & Multi-Tenancy Architecture

1. **Multi-Tenant Isolation:**
   - Every collection (`channels`, `content_ideas`, `scripts`, `videos`, `analytics_snapshots`, `jobs`) requires `user_id`.
   - All repository queries filter by `user_id` extracted from authenticated JWT.
2. **Encryption at Rest:**
   - Sensitive OAuth refresh tokens are encrypted using AES Fernet keys (`ENCRYPTION_KEY`) before persistence.
3. **Input Sanitization & Error Handling:**
   - Validation exception handler recursively sanitizes error envelopes: redacts password fields and converts non-serializable binary payloads to safe string summaries, preventing data leaks or server crashes.
