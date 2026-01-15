# Echo-TTS REST API Documentation

## Overview

This API provides voice cloning and text-to-speech capabilities powered by the [Echo-TTS model](https://github.com/jordandare/echo-tts). The API runs on Modal with **local GPU inference** (NVIDIA A10G, 24GB VRAM) for fast, high-quality speech synthesis.

**Base URL:** `https://aahalife--echo-tts-web-app.modal.run`

**Dashboard:** [Modal App Dashboard](https://modal.com/apps/aahalife/main/deployed/echo-tts)

---

## Authentication

All endpoints (except health check and root) require API key authentication. Provide your API key using one of these methods:

### Option 1: Bearer Token (Recommended)
```http
Authorization: Bearer YOUR_API_KEY
```

### Option 2: X-API-Key Header
```http
X-API-Key: YOUR_API_KEY
```

**Error Response (401 Unauthorized):**
```json
{
  "detail": "Invalid API key"
}
```

---

## Endpoints

### Service Info

```http
GET /
```

Returns service information.

**Response:**
```json
{
  "service": "Echo-TTS",
  "gpu": "A10G",
  "inference": "local"
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
  "status": "ok",
  "ts": "2026-01-15T01:02:04.352309"
}
```

---

### Generate Speech (TTS)

```http
POST /tts
Content-Type: application/json
Authorization: Bearer YOUR_API_KEY
```

Generate speech from text using a speaker reference audio.

**Request Body:**
```json
{
  "text": "Hello, this is a test of the voice cloning system.",
  "speaker_audio_url": "https://example.com/speaker.wav",
  "num_steps": 24,
  "rng_seed": 0,
  "cfg_scale_speaker": 8.0
}
```

**Parameters:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `text` | string | Yes | - | Text to synthesize |
| `speaker_audio_url` | string | Yes | - | URL to speaker reference audio (WAV, MP3, OGG, etc.) |
| `num_steps` | int | No | 24 | Diffusion steps (more = higher quality, slower). Range: 16-48 recommended |
| `rng_seed` | int | No | 0 | Random seed for reproducibility |
| `cfg_scale_speaker` | float | No | 8.0 | Speaker guidance scale (higher = closer to reference voice) |

**Example Request:**
```bash
curl -X POST https://aahalife--echo-tts-web-app.modal.run/tts \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello world! This is Echo TTS speaking.",
    "speaker_audio_url": "https://example.com/speaker.wav"
  }' \
  --output output.wav
```

**Response:**

Returns WAV audio file directly (Content-Type: `audio/wav`).

---

## Generation Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `num_steps` | 24 | 16-48 | Number of diffusion steps. Higher = better quality but slower. 24 is a good balance. |
| `rng_seed` | 0 | any int | Random seed for reproducible output |
| `cfg_scale_speaker` | 8.0 | 1.0-15.0 | Speaker guidance scale. Higher = stronger voice adherence |

### Internal Parameters (hardcoded for optimal quality)

| Parameter | Value | Description |
|-----------|-------|-------------|
| `cfg_scale_text` | 3.0 | Text guidance scale |
| `speaker_kv_scale` | 1.5 | Speaker KV attention scale |
| `speaker_kv_max_layers` | 24 | Number of layers for speaker KV |
| `truncation_factor` | 0.8 | Truncation for sampling |

---

## Text Format

- The API automatically prepends `[S1] ` if the text doesn't start with a speaker tag
- **Commas** function as pauses
- **Periods** and **exclamation points** affect intonation
- Multi-speaker format: `[S1] First speaker says this. [S2] Second speaker says this.`

---

## Reference Audio Guidelines

- **Duration:** 10-30 seconds works well; up to 5 minutes supported
- **Quality:** Clear audio with minimal background noise is best
- **Format:** WAV, MP3, OGG, FLAC, M4A supported
- **Sample rate:** Any (automatically resampled to 44.1kHz)

---

## Response Times

| Scenario | Time |
|----------|------|
| **Cold start** | ~15-20 seconds (model loading) |
| **Warm inference** | ~2-5 seconds (depending on text length) |
| **Container keep-alive** | 15 minutes after last request |
| **Request timeout** | 10 minutes |

**Tip:** Make a health check request first to warm up the container before time-sensitive TTS requests.

---

## Error Handling

All errors return JSON with a `detail` field:

```json
{
  "detail": "Error description here"
}
```

**HTTP Status Codes:**

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad request (missing required parameters) |
| 401 | Unauthorized (invalid or missing API key) |
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
        "speaker_audio_url": "https://example.com/speaker.wav",
        "num_steps": 24
    }
)

if response.status_code == 200:
    with open("output.wav", "wb") as f:
        f.write(response.content)
    print("Audio saved to output.wav")
else:
    print(f"Error: {response.json()}")
```

### JavaScript / TypeScript

```javascript
const BASE_URL = "https://aahalife--echo-tts-web-app.modal.run";
const API_KEY = "YOUR_API_KEY";

async function generateSpeech(text, speakerAudioUrl) {
  const response = await fetch(`${BASE_URL}/tts`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${API_KEY}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ 
      text, 
      speaker_audio_url: speakerAudioUrl,
      num_steps: 24
    })
  });
  
  if (!response.ok) {
    throw new Error(await response.text());
  }
  
  return response.blob();
}

// Usage
generateSpeech("Hello world!", "https://example.com/speaker.wav")
  .then(blob => {
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.play();
  });
```

### cURL

```bash
# Health check (no auth required)
curl https://aahalife--echo-tts-web-app.modal.run/health

# Generate speech
curl -X POST https://aahalife--echo-tts-web-app.modal.run/tts \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello world!",
    "speaker_audio_url": "https://example.com/speaker.wav"
  }' \
  --output output.wav
```

---

## Infrastructure

- **Platform:** [Modal](https://modal.com)
- **GPU:** NVIDIA A10G (24GB VRAM)
- **Model:** Echo-TTS Base (2.4B parameters, bfloat16)
- **Inference:** Local GPU (no external API calls)
- **Scaling:** Serverless, scales to zero when idle

---

## Environment Variables (Modal Secrets)

Set in Modal secret `echo-tts-secrets`:

| Variable | Required | Description |
|----------|----------|-------------|
| `API_KEY` | Yes | Secret key for API authentication |

---

## Notes

- Audio outputs are [CC-BY-NC-SA-4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) licensed
- Please use responsibly and do not impersonate real people without consent
- The model runs locally on GPU - no data is sent to external services
- **Streaming not supported:** Echo-TTS is a diffusion model that generates complete audio in a single pass. The full audio must be generated before playback can begin.
