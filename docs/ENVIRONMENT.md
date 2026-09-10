# Auvyra Environment Configuration Reference

This guide details all configuration variables parsed by `backend/app/config.py`.

---

## 1. Application & Server

| Variable       | Type    | Default                 | Description                                          |
| :------------- | :------ | :---------------------- | :--------------------------------------------------- |
| `APP_NAME`     | string  | `Auvyra`                | Application identifier                               |
| `APP_ENV`      | string  | `development`           | Environment (`development`, `staging`, `production`) |
| `APP_DEBUG`    | boolean | `false`                 | Enable verbose debugging (forbidden in production)   |
| `APP_HOST`     | string  | `0.0.0.0`               | Bind host address                                    |
| `APP_PORT`     | integer | `8000`                  | HTTP port for backend server                         |
| `APP_URL`      | string  | `http://localhost:8000` | Base URL for API callbacks                           |
| `FRONTEND_URL` | string  | `http://localhost:5173` | Allowed CORS origin                                  |

---

## 2. Authentication & Security

| Variable                      | Type    | Default        | Description                                               |
| :---------------------------- | :------ | :------------- | :-------------------------------------------------------- |
| `JWT_SECRET`                  | string  | `change-me...` | Secret key for signing access JWTs (min 32 chars in prod) |
| `JWT_REFRESH_SECRET`          | string  | `change-me...` | Secret key for signing refresh JWTs                       |
| `JWT_ALGORITHM`               | string  | `HS256`        | JWT signature algorithm                                   |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | integer | `30`           | Access token lifespan in minutes                          |
| `REFRESH_TOKEN_EXPIRE_DAYS`   | integer | `7`            | Refresh token lifespan in days                            |
| `ENCRYPTION_KEY`              | string  | `""`           | 32-byte URL-safe base64 Fernet encryption key             |

---

## 3. Database (MongoDB)

| Variable                  | Type    | Default                     | Description              |
| :------------------------ | :------ | :-------------------------- | :----------------------- |
| `MONGODB_URI`             | string  | `mongodb://localhost:27017` | MongoDB connection URI   |
| `MONGODB_DATABASE`        | string  | `auvyra`                    | Target database name     |
| `MONGODB_MAX_CONNECTIONS` | integer | `100`                       | Max connection pool size |
| `MONGODB_MIN_CONNECTIONS` | integer | `10`                        | Min connection pool size |

---

## 4. AI Gateway (Ollama)

| Variable                 | Type   | Default                  | Description                           |
| :----------------------- | :----- | :----------------------- | :------------------------------------ |
| `OLLAMA_BASE_URL`        | string | `http://localhost:11434` | Ollama HTTP endpoint                  |
| `OLLAMA_MODEL`           | string | `llama3.1:8b`            | Model name for generation             |
| `OLLAMA_REQUEST_TIMEOUT` | float  | `120.0`                  | Max timeout per completion in seconds |

---

## 5. Google OAuth & YouTube API

| Variable               | Type   | Default                        | Description                                       |
| :--------------------- | :----- | :----------------------------- | :------------------------------------------------ |
| `GOOGLE_CLIENT_ID`     | string | `""`                           | OAuth 2.0 Web Client ID from Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | string | `""`                           | OAuth 2.0 Client Secret from Google Cloud Console |
| `GOOGLE_REDIRECT_URI`  | string | `.../api/auth/google/callback` | Authorized redirect URI                           |
| `YOUTUBE_API_KEY`      | string | `""`                           | Optional public YouTube Data API key              |

---

## 6. Media & Video Subsystem

| Variable         | Type   | Default                   | Description                                       |
| :--------------- | :----- | :------------------------ | :------------------------------------------------ |
| `MEDIA_ROOT`     | string | `media`                   | Directory for local video storage                 |
| `PEXELS_API_KEY` | string | `""`                      | Optional Pexels stock video API key               |
| `FFMPEG_PATH`    | string | `""`                      | Explicit path to ffmpeg (auto-detected if empty)  |
| `FFPROBE_BINARY` | string | `""`                      | Explicit path to ffprobe (auto-detected if empty) |
| `EDGE_TTS_VOICE` | string | `en-US-AriaNeural-Female` | Default narration voice                           |
