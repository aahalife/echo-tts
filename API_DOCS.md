# Echo-TTS REST API Documentation

## Overview

This API provides voice cloning and text-to-speech capabilities powered by the [Echo-TTS model](https://github.com/jordandare/echo-tts). The API runs on Modal with GPU acceleration (NVIDIA A10G) for fast inference.

**Base URL:** `https://aahalife--echo-tts-web-app.modal.run`

**Dashboard:** [Modal App Dashboard](https://modal.com/apps/aahalife/main/deployed/echo-tts)

---

## Authentication

All endpoints (except health check) require API key authentication. Provide your API key using one of these methods:

### Option 1: Bearer Token (Recommended)
```http
Authorization: Bearer YOUR_API_KEY
```

### Option 2: X-API-Key Header
```http
X-API-Key: YOUR_API_KEY
```

**Example:**
```bash
curl -H "Authorization: Bearer YOUR_API_KEY" https://aahalife--echo-tts-web-app.modal.run/health
```

**Error Response (401 Unauthorized):**
```json
{
  "error": "Invalid or missing API key"
}
```

---

## Default Settings

The API is configured with optimal defaults:

| Setting | Value | Description |
|---------|-------|-------------|
| Speaker KV | **Enabled** | Forces the model to match the reference speaker |
| Speaker KV Scale | **1.5** | Scale factor for speaker conditioning |
| Diffusion Steps | 40 | Quality/speed tradeoff |
| Preset | Independent (High Speaker CFG) | Sampler configuration |

---

## Endpoints

### Service Info

```http
GET /
```

Returns service information and available endpoints.

**Response:**
```json
{
  "service": "Echo-TTS Modal API",
  "version": "1.0.0",
  "gpu": "A10G",
  "endpoints": {
    "GET /health": "Health check",
    "POST /tts": "Generate speech"
  }
}
```

---

### Health Check

```http
GET /health
```

Returns service health status.

**Response:**
```json
{
  "status": "healthy",
  "service": "echo-tts-modal",
  "timestamp": "2025-01-14T10:00:00Z"
}
```

---

### Generate Speech (TTS)

```http
POST /tts
Content-Type: application/json
```

Generate speech from text using a registered voice.

**Request Body:**
```json
{
  "text": "Hello, this is a test of the voice cloning system.",
  "voice_id": "john",
  "num_steps": 40,
  "rng_seed": 0,
  "speaker_kv_enable": true,
  "speaker_kv_scale": 1.5,
  "preset_name": "Independent (High Speaker CFG)"
}
```

**Parameters:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `text` | string | Yes | - | Text to synthesize |
| `voice_id` | string | Yes | - | ID of a registered voice |
| `num_steps` | int | No | 40 | Diffusion steps (1-80) |
| `rng_seed` | int | No | 0 | Random seed for reproducibility |
| `speaker_kv_enable` | bool | No | true | Enable speaker KV attention |
| `speaker_kv_scale` | float | No | 1.5 | Speaker KV scale (1.0-2.0) |
| `preset_name` | string | No | "Independent (High Speaker CFG)" | Sampler preset |

**Example:**
```bash
curl -X POST https://aahalife--echo-tts-web-app.modal.run/tts \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world!", "voice_id": "john"}' \
  --output output.wav
```

**Response:**

Returns WAV audio file directly (Content-Type: audio/wav).

---

## Generation Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `num_steps` | 40 | 1-80 | Number of diffusion steps. Higher = better quality, slower. |
| `rng_seed` | 0 | any int | Random seed for reproducible output. |
| `speaker_kv_enable` | true | true/false | Enable speaker KV attention scaling. |
| `speaker_kv_scale` | 1.5 | 1.0-2.0 | Scale factor for speaker KV. Higher = stronger voice adherence. |
| `preset_name` | "Independent (High Speaker CFG)" | see below | Sampler preset. |

**Available Presets:**
- `Independent (High Speaker CFG)` (recommended)
- `Independent (High Speaker CFG) Flat`
- `Independent (High CFG)`
- `Independent (High CFG) Flat`
- `Independent`
- `Independent Flat`

---

## Voice Management

Voices are stored in Vercel Blob storage and referenced by ID. Voice registration is managed separately from the TTS endpoint.

To register a voice, the audio file metadata must be stored in Vercel Blob at `voices/{voice_id}.meta.json` with the format:
```json
{
  "id": "john",
  "name": "John's Voice",
  "audio_url": "https://blob.vercel-storage.com/...",
  "created_at": "2025-01-14T10:00:00Z"
}
```

---

## Text Format

Text prompts follow the WhisperD transcription format:

- The API automatically prepends `[S1] ` if not present
- **Commas** function as pauses
- **Exclamation points** may increase expressiveness

---

## Reference Audio Guidelines

- **Duration:** 10-30 seconds works well; up to 5 minutes supported
- **Quality:** Clear audio with minimal background noise is best
- **Format:** WAV, MP3, OGG, FLAC, M4A, AAC

---

## Response Times

- **Cold start:** ~45-60 seconds (model loading + inference)
- **Warm inference:** 5-20 seconds per request (depending on text length)
- **Timeout:** 300 seconds (5 minutes)

The service scales down after 2 minutes of inactivity to save costs.

**Note on Streaming:** The response uses HTTP chunked transfer encoding, so clients receive audio data progressively. However, the underlying diffusion model generates complete audio in a single pass, so true real-time streaming (where audio plays before generation completes) is not supported.

---

## Error Handling

All errors return JSON with an `error` field:

```json
{
  "error": "Error description here"
}
```

**HTTP Status Codes:**

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad request (missing parameters) |
| 401 | Unauthorized (invalid or missing API key) |
| 404 | Voice not found |
| 500 | Server error (TTS generation failed) |

---

## SDK Examples

### Python

```python
import requests

BASE_URL = "https://aahalife--echo-tts-web-app.modal.run"
API_KEY = "YOUR_API_KEY"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# Generate speech
response = requests.post(
    f"{BASE_URL}/tts",
    headers=headers,
    json={
        "text": "Hello from Python!",
        "voice_id": "myvoice"
    }
)

if response.status_code == 200:
    with open("output.wav", "wb") as f:
        f.write(response.content)
    print("Audio saved to output.wav")
else:
    print(f"Error: {response.json()}")
```

### JavaScript

```javascript
const BASE_URL = "https://aahalife--echo-tts-web-app.modal.run";
const API_KEY = "YOUR_API_KEY";

async function generateSpeech(text, voiceId) {
  const response = await fetch(`${BASE_URL}/tts`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${API_KEY}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ text, voice_id: voiceId })
  });
  
  if (response.ok) {
    return response.blob();
  }
  throw new Error(await response.text());
}

// Usage
generateSpeech("Hello world!", "myvoice")
  .then(blob => {
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.play();
  });
```

### cURL

```bash
# Health check
curl https://aahalife--echo-tts-web-app.modal.run/health

# Generate speech
curl -X POST https://aahalife--echo-tts-web-app.modal.run/tts \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world!", "voice_id": "john"}' \
  --output output.wav
```

---

## Environment Variables

Set these in Modal Secrets:

| Variable | Required | Description |
|----------|----------|-------------|
| `API_KEY` | Yes | Secret key for API authentication |
| `BLOB_READ_WRITE_TOKEN` | Yes | Vercel Blob read/write token for voice storage |

---

## Infrastructure

- **Platform:** [Modal](https://modal.com)
- **Backend:** HuggingFace Space API ([jordand/echo-tts-preview](https://huggingface.co/spaces/jordand/echo-tts-preview))
- **Scaling:** Serverless, scales to zero when idle

---

## Notes

- Audio outputs are [CC-BY-NC-SA-4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) licensed
- Please use responsibly and do not impersonate real people without consent
- The service falls back to HuggingFace Space API if local model loading fails
