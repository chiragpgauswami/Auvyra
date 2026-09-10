# Auvyra — Required External Integrations & Setup Guide

This document outlines the external credentials and third-party setups required to enable live YouTube publishing, YouTube Analytics synchronization, and optional external stock media search.

---

## 1. Google Cloud Console & YouTube Integration (Required for Publishing)

Auvyra enforces a **Zero-Mock Policy**. In production mode, videos are only published to YouTube when valid Google OAuth credentials and YouTube channel permissions are configured.

### Step 1: Create a Google Cloud Project

1. Navigate to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project named `Auvyra-Production` (or select an existing project).

### Step 2: Enable Required Google APIs

In the Google Cloud Console, navigate to **APIs & Services > Library** and enable the following two APIs:

1. **YouTube Data API v3** (Required for uploading videos, setting thumbnails, creating playlists, and channel metadata).
2. **YouTube Analytics API** (Required for syncing real view counts, watch time, retention, and traffic metrics).

### Step 3: Configure the OAuth Consent Screen

1. Go to **APIs & Services > OAuth consent screen**.
2. Select **User Type**:
   - `External` (for public users or external testers)
   - `Internal` (if within a Google Workspace organization)
3. Fill in:
   - **App name**: `Auvyra`
   - **User support email**: Your admin email
   - **Developer contact information**: Your developer email
4. Add Scopes:
   - `openid`
   - `https://www.googleapis.com/auth/userinfo.email`
   - `https://www.googleapis.com/auth/userinfo.profile`
   - `https://www.googleapis.com/auth/youtube.upload`
   - `https://www.googleapis.com/auth/youtube.readonly`
   - `https://www.googleapis.com/auth/yt-analytics.readonly`
5. Under **Test Users**, add the Google accounts that will connect their YouTube channels during testing.

### Step 4: Create OAuth 2.0 Credentials

1. Go to **APIs & Services > Credentials**.
2. Click **Create Credentials > OAuth client ID**.
3. Select **Application type**: `Web application`.
4. Name: `Auvyra Backend Web Client`.
5. Under **Authorized redirect URIs**, add:
   - For local development: `http://localhost:8000/api/auth/google/callback`
   - For production: `https://api.yourdomain.com/api/auth/google/callback`
6. Click **Create**.
7. Copy the generated:
   - **Client ID**
   - **Client Secret**

### Step 5: Update `.env`

Add the credentials to your `.env` file:

```env
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/google/callback
```

---

## 2. Stock Media Integration (Pexels API - Optional)

Auvyra has built-in local fallback footage generation and canvas composition. To enable automatic stock video and image search from Pexels:

1. Sign up for a free developer account at [Pexels API](https://www.pexels.com/api/).
2. Generate an API Key under **Your API Key**.
3. Update `.env`:

```env
PEXELS_API_KEY=your-pexels-api-key-here
```

---

## 3. Ollama Local AI (Active & Verified)

Auvyra connects to local Ollama running on `http://localhost:11434` with `llama3.1:8b`.
Verify model installation:

```bash
ollama list
# If llama3.1:8b is not installed:
ollama pull llama3.1:8b
```

---

## 4. Environment Verification

Once you have updated your `.env` with Google credentials, run the Auvyra Doctor:

```bash
python3 scripts/doctor.py
```

When all items display `[PASS]`, run the single verification command:

```bash
./scripts/verify.sh
```
