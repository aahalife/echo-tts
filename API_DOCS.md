# Echo-TTS REST API Documentation

## Overview

This API provides voice cloning and text-to-speech capabilities powered by the [Echo-TTS model](https://github.com/jordandare/echo-tts). Voice references can be persisted by ID, allowing reuse without re-uploading audio files.

---

## Authentication

All endpoints require API key authentication. Provide your API key using one of these methods:

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
curl -H "Authorization: Bearer YOUR_API_KEY" https://your-app.vercel.app/api/voices
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

### Health Check

```http
GET /api/health
```

Returns service health status.

**Response:**
```json
{
  "status": "healthy",
  "service": "echo-tts-api",
  "timestamp": "2025-01-14T10:00:00Z"
}
```

---

### List All Voices

```http
GET /api/voices
```

Returns a list of all registered voice IDs with metadata.

**Response:**
```json
{
  "voices": [
    {
      "id": "john",
      "name": "John's Voice",
      "created_at": "2025-01-14T10:00:00Z",
      "description": "Male speaker sample"
    }
  ]
}
```

---

### Get Voice Details

```http
GET /api/voices/{voice_id}
```

Returns details about a specific registered voice.

**Response:**
```json
{
  "id": "john",
  "name": "John's Voice",
  "created_at": "2025-01-14T10:00:00Z",
  "description": "Male speaker sample",
  "file_size": 245760,
  "blob_url": "https://..."
}
```

---

### Register a New Voice

```http
POST /api/voices
Content-Type: multipart/form-data
```

**Form Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `audio` | file | Yes | Reference audio file (WAV, MP3, OGG, FLAC, M4A, AAC) |
| `id` | string | No | Custom voice ID (auto-generated if not provided) |
| `name` | string | No | Display name for the voice |
| `description` | string | No | Voice description |

**Example:**
```bash
curl -X POST https://your-app.vercel.app/api/voices \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "audio=@reference.wav" \
  -F "id=john" \
  -F "name=John's Voice"
```

**Response (201 Created):**
```json
{
  "id": "john",
  "name": "John's Voice",
  "created_at": "2025-01-14T10:00:00Z",
  "message": "Voice registered successfully"
}
```

---

### Delete a Voice

```http
DELETE /api/voices/{voice_id}
```

Deletes a registered voice and its audio file.

**Response:**
```json
{
  "message": "Voice deleted: john"
}
```

---

### Generate Speech (TTS)

```http
POST /api/tts
```

Generate speech from text using a registered voice or one-time audio upload.

#### Option A: JSON Body (with registered voice)

```http
Content-Type: application/json
```

**Body:**
```json
{
  "text": "Hello, this is a test of the voice cloning system.",
  "voice_id": "john",
  "num_steps": 40,
  "rng_seed": 0,
  "speaker_kv_enable": true,
  "speaker_kv_scale": 1.5
}
```

#### Option B: Multipart Form (with audio file)

```http
Content-Type: multipart/form-data
```

**Form Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `text` | string | Yes | Text to synthesize |
| `voice_id` | string | No* | ID of a registered voice |
| `audio` | file | No* | One-time reference audio file |
| `num_steps` | int | No | Diffusion steps (default: 40) |
| `rng_seed` | int | No | Random seed (default: 0) |
| `speaker_kv_enable` | bool | No | Enable speaker KV (default: true) |
| `speaker_kv_scale` | float | No | Speaker KV scale (default: 1.5) |

*Either `voice_id` OR `audio` must be provided.

**Example (with registered voice):**
```bash
curl -X POST https://your-app.vercel.app/api/tts \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world!", "voice_id": "john"}' \
  --output output.wav
```

**Example (with audio file):**
```bash
curl -X POST https://your-app.vercel.app/api/tts \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "text=Hello world!" \
  -F "audio=@reference.wav" \
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

- **Typical:** 10-30 seconds per request
- **Note:** Vercel function timeout is set to 60 seconds

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
| 201 | Created (voice registered) |
| 400 | Bad request (missing parameters) |
| 401 | Unauthorized (invalid or missing API key) |
| 404 | Voice not found |
| 409 | Conflict (voice ID already exists) |
| 500 | Server error (TTS generation failed) |
| 503 | Service unavailable (storage not configured) |

---

## SDK Examples

### Python

```python
import requests

BASE_URL = "https://your-app.vercel.app"
API_KEY = "YOUR_API_KEY"

headers = {"Authorization": f"Bearer {API_KEY}"}

# Register a voice
with open("reference.wav", "rb") as f:
    response = requests.post(
        f"{BASE_URL}/api/voices",
        headers=headers,
        files={"audio": f},
        data={"id": "myvoice", "name": "My Voice"}
    )
    print(response.json())

# Generate speech
response = requests.post(
    f"{BASE_URL}/api/tts",
    headers={**headers, "Content-Type": "application/json"},
    json={
        "text": "Hello from Python!",
        "voice_id": "myvoice"
    }
)

if response.status_code == 200:
    with open("output.wav", "wb") as f:
        f.write(response.content)
```

### JavaScript

```javascript
const BASE_URL = "https://your-app.vercel.app";
const API_KEY = "YOUR_API_KEY";

const headers = {
  "Authorization": `Bearer ${API_KEY}`
};

// Generate speech
async function generateSpeech(text, voiceId) {
  const response = await fetch(`${BASE_URL}/api/tts`, {
    method: "POST",
    headers: { 
      ...headers,
      "Content-Type": "application/json" 
    },
    body: JSON.stringify({ text, voice_id: voiceId })
  });
  
  if (response.ok) {
    return response.blob();
  }
  throw new Error(await response.text());
}
```

---

## Environment Variables

Set these in your Vercel project:

| Variable | Required | Description |
|----------|----------|-------------|
| `API_KEY` | Yes | Secret key for API authentication |
| `KV_REST_API_URL` | Yes | Vercel KV REST API URL |
| `KV_REST_API_TOKEN` | Yes | Vercel KV REST API token |
| `BLOB_READ_WRITE_TOKEN` | Yes | Vercel Blob read/write token |
| `HF_SPACE` | No | HuggingFace Space (default: jordand/echo-tts-preview) |

---

## Notes

- This service uses the [HuggingFace Echo-TTS Space](https://huggingface.co/spaces/jordand/echo-tts-preview) as backend
- Audio outputs are [CC-BY-NC-SA-4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) licensed
- Please use responsibly and do not impersonate real people without consent
