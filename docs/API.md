# Auvyra REST API Specification (Phase 1)

Base URL: `http://localhost:8000/api`  
All protected endpoints require the HTTP Authorization header: `Authorization: Bearer <access_token>`

---

## 1. Authentication (`/api/auth`)

### `POST /api/auth/register`

Creates a new creator user account and returns JWT credentials.

- **Request Body (JSON):**
  ```json
  {
    "email": "creator@example.com",
    "password": "MinLength8CharsPassword!",
    "name": "Alex Smith"
  }
  ```
- **Responses:**
  - `201 Created`: Returns `TokenPair` (`{ "access_token": "...", "refresh_token": "...", "token_type": "bearer" }`)
  - `400 Bad Request`: `{"error": {"code": "EMAIL_EXISTS", "message": "Email already registered"}}`
  - `422 Unprocessable Entity`: Validation failure with sanitized error array.

### `POST /api/auth/login`

Authenticates a user via email/username and password.

- **Request Body (JSON):**
  ```json
  {
    "email": "creator@example.com",
    "password": "MinLength8CharsPassword!"
  }
  ```
  _(Note: `"username"` is also accepted as an alias for `"email"`)_
- **Responses:**
  - `200 OK`: Returns `TokenPair`
  - `401 Unauthorized`: `{"error": {"code": "INVALID_CREDENTIALS", "message": "Invalid email or password"}}`

### `POST /api/auth/refresh`

Rotates and returns a fresh JWT access and refresh token pair.

- **Request Body (JSON):**
  ```json
  {
    "refresh_token": "..."
  }
  ```
- **Responses:**
  - `200 OK`: Returns new `TokenPair`
  - `401 Unauthorized`: Token invalid or revoked.

### `POST /api/auth/logout`

Revokes the current refresh session.

- **Request Body (JSON):** `{"refresh_token": "..."}`
- **Responses:** `200 OK`: `{"status": "success", "message": "Logged out"}`

### `GET /api/auth/me`

Retrieves the currently authenticated user's profile.

- **Headers:** `Authorization: Bearer <access_token>`
- **Responses:**
  - `200 OK`: `{"id": "...", "email": "...", "name": "...", "email_verified": true}`

---

## 2. Channels (`/api/channels`)

### `GET /api/channels/`

Lists all channels owned by the authenticated user.

- **Responses:** `200 OK`: Array of `ChannelResponse` objects.

### `POST /api/channels/`

Creates a new managed channel.

- **Request Body (JSON):**
  ```json
  {
    "name": "Tech Insights",
    "description": "Daily AI tools and software engineering shorts",
    "handle": "@techinsights"
  }
  ```
- **Responses:** `201 Created`: Returns created `ChannelResponse`.

### `GET /api/channels/{channel_id}/memory`

Retrieves cumulative learning memory for the channel (best topics, hooks, audience insights).

- **Responses:** `200 OK`: Returns `ChannelMemory` document.

---

## 3. AI Content Research (`/api/research`)

### `POST /api/research/`

Executes real Ollama research on a given topic within the channel niche.

- **Request Body (JSON):**
  ```json
  {
    "channel_id": "66da...",
    "topic": "3 Productive Habits of Software Engineers",
    "channel_context": {}
  }
  ```
- **Responses:**
  - `201 Created`: Returns `ResearchReport` with structured `findings`, `sources`, and `recommendations`.
  - `503 Service Unavailable`: If local Ollama is offline.

---

## 4. Content Ideas & Scripts (`/api/content`)

### `GET /api/content/ideas`

Retrieves content ideas. `channel_id` is optional; if omitted, returns all user ideas.

- **Query Parameters:** `channel_id` (optional), `status` (optional)
- **Responses:** `200 OK`: Array of `ContentIdea` objects.

### `POST /api/content/ideas/generate`

Prompts Ollama to generate 5 distinct video ideas based on channel context.

- **Request Body (JSON):** `{"channel_id": "...", "channel_context": {}}`
- **Responses:** `201 Created`: Array of generated ideas saved to database.

### `POST /api/content/scripts/generate`

Generates a structured video script optimized for video narration and visual rhythm.

- **Request Body (JSON):**
  ```json
  {
    "channel_id": "...",
    "topic": "Eliminate Distraction with Timeboxing",
    "duration": 45
  }
  ```
- **Responses:** `201 Created`: Returns `Script` object with word count and estimated duration.

---

## 5. Video Generation Subsystem (`/api/videos`)

### `POST /api/videos/generate`

Queues a background video generation job.

- **Request Body (JSON):**
  ```json
  {
    "channel_id": "...",
    "request_data": {
      "topic": "Focus Mastery in 30 Seconds",
      "script": "Script text...",
      "aspect_ratio": "9:16",
      "voice_name": "en-US-AriaNeural-Female"
    }
  }
  ```
- **Responses:** `201 Created`: `{"job_id": "...", "video_id": "...", "status": "queued"}`

### `GET /api/videos/`

Lists generated videos filtered by user and optionally channel.

- **Query Parameters:** `channel_id` (optional), `status` (optional)

### `GET /api/videos/{video_id}`

Retrieves video details, resolution, duration, file path, and publishing status.

---

## 6. Jobs & Progress (`/api/jobs`)

### `GET /api/jobs/{job_id}/progress`

Real-time polling endpoint for generation progress.

- **Responses:**
  ```json
  {
    "stage": "rendering",
    "percent": 90,
    "message": "Final video rendering complete",
    "status": "processing"
  }
  ```

---

## 7. Publishing Subsystem (`/api/publishing`)

### `POST /api/publishing/`

Creates a publishing job record for a generated video.

- **Request Body (JSON):**
  ```json
  {
    "video_id": "...",
    "platform": "youtube",
    "metadata": {
      "title": "My New Video",
      "description": "Video description...",
      "tags": ["ai", "coding"],
      "privacy": "private"
    }
  }
  ```
- **Responses:** `201 Created`: `{"job_id": "..."}`

### `POST /api/publishing/{job_id}/publish`

Triggers real YouTube upload via Google OAuth tokens.

- **Responses:**
  - `200 OK`: `{"youtube_video_id": "...", "status": "published", "url": "https://youtube.com/watch?v=..."}`
  - `400 Bad Request` (`GOOGLE_OAUTH_NOT_CONFIGURED`): Explicit rejection if Google OAuth is not configured. Zero mock success.

---

## 8. Analytics & Learning Engine (`/api/analytics`)

### `GET /api/analytics/channel/{channel_id}`

Retrieves real analytics snapshots for the channel.

- **Query Parameters:** `period` (daily, weekly, monthly)

### `POST /api/analytics/insights/{channel_id}/generate`

Computes strategic insights from real snapshots and Ollama analysis. Returns empty list if no snapshots exist (zero fake data).

---

## 9. System Health (`/api/health`)

### `GET /api/health`

Composite system health check.

- **Responses:**
  ```json
  {
    "status": "ok",
    "services": {
      "database": { "status": "ok" },
      "ai": { "status": "ok", "model": "llama3.1:8b" },
      "video": { "status": "ok", "ffmpeg": "/opt/homebrew/bin/ffmpeg" }
    }
  }
  ```
