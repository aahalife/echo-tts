"""Echo-TTS Modal App - Fast GPU inference with warm containers"""
import modal
import os
import io
import tempfile

app = modal.App("echo-tts")

# Pre-download models during image build
def download_models():
    from huggingface_hub import hf_hub_download
    import subprocess
    
    os.makedirs("/root/.cache/huggingface", exist_ok=True)
    os.environ["HF_HOME"] = "/root/.cache/huggingface"
    
    print("Downloading models...")
    hf_hub_download("jordand/echo-tts-base", "pytorch_model.safetensors")
    hf_hub_download("jordand/echo-tts-base", "pca_state.safetensors")
    hf_hub_download("jordand/fish-s1-dac-min", "pytorch_model.safetensors")
    
    print("Cloning echo-tts repo...")
    subprocess.run(["git", "clone", "--depth=1", "https://github.com/jordandare/echo-tts.git", "/root/echo-tts"], check=True)
    
    # Patch inference.py to use torchaudio instead of torchcodec
    inference_path = "/root/echo-tts/inference.py"
    with open(inference_path, "r") as f:
        content = f.read()
    
    # Remove torchcodec import
    content = content.replace("from torchcodec.decoders import AudioDecoder\n", "")
    
    # Replace load_audio function
    old_func = '''def load_audio(path: str, max_duration: int = 300) -> torch.Tensor:

    decoder = AudioDecoder(path)
    sr = decoder.metadata.sample_rate
    audio = decoder.get_samples_played_in_range(0, max_duration)
    audio = audio.data.mean(dim=0).unsqueeze(0)
    audio = torchaudio.functional.resample(audio, sr, 44_100)
    audio = audio / torch.maximum(audio.abs().max(), torch.tensor(1.))
    # is this better than clipping? should we target a specific energy level?
    return audio'''
    
    new_func = '''def load_audio(path: str, max_duration: int = 300) -> torch.Tensor:
    audio, sr = torchaudio.load(path)
    # Limit to max_duration seconds
    max_samples = int(max_duration * sr)
    if audio.shape[1] > max_samples:
        audio = audio[:, :max_samples]
    # Convert to mono
    audio = audio.mean(dim=0).unsqueeze(0)
    # Resample to 44100 Hz
    audio = torchaudio.functional.resample(audio, sr, 44_100)
    # Normalize
    audio = audio / torch.maximum(audio.abs().max(), torch.tensor(1.))
    return audio'''
    
    content = content.replace(old_func, new_func)
    
    with open(inference_path, "w") as f:
        f.write(content)
    
    print("Done!")

echo_tts_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "ffmpeg", "libsndfile1")
    .pip_install("numpy<2")
    .pip_install(
        "torch==2.5.1",
        "torchaudio==2.5.1",
        extra_index_url="https://download.pytorch.org/whl/cu124",
    )
    .pip_install(
        "transformers",
        "huggingface_hub",
        "safetensors",
        "einops",
    )
    .run_function(download_models)
)

web_image = modal.Image.debian_slim().pip_install("fastapi[standard]", "requests")


@app.cls(
    image=echo_tts_image,
    gpu="A10G",
    timeout=600,  # 10 min for cold start
    scaledown_window=900,  # Keep warm 15 min
)
class EchoTTS:
    @modal.enter()
    def load_models(self):
        import torch
        import sys
        import time
        
        sys.path.insert(0, "/root/echo-tts")
        os.environ["HF_HOME"] = "/root/.cache/huggingface"
        
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
        
        from inference import (
            load_model_from_hf,
            load_fish_ae_from_hf,
            load_pca_state_from_hf,
            load_audio,
            sample_pipeline,
            sample_euler_cfg_independent_guidances,
        )
        
        t0 = time.time()
        print("Loading main model...")
        self.model = load_model_from_hf(
            device="cuda",
            dtype=torch.bfloat16,
            delete_blockwise_modules=True
        )
        print(f"Main model loaded in {time.time()-t0:.1f}s")
        
        t1 = time.time()
        print("Loading fish_ae...")
        self.fish_ae = load_fish_ae_from_hf(device="cuda", dtype=torch.float32)
        print(f"fish_ae loaded in {time.time()-t1:.1f}s")
        
        t2 = time.time()
        print("Loading pca_state...")
        self.pca_state = load_pca_state_from_hf(device="cuda")
        print(f"pca_state loaded in {time.time()-t2:.1f}s")
        
        self.load_audio = load_audio
        self.sample_pipeline = sample_pipeline
        self.sample_fn_class = sample_euler_cfg_independent_guidances
        
        torch.cuda.synchronize()
        print(f"Total load time: {time.time()-t0:.1f}s - Ready!")
    


    @modal.method()
    def generate(
        self,
        text: str,
        speaker_audio_bytes: bytes,
        num_steps: int = 24,  # Good balance: 24-32 steps
        rng_seed: int = 0,
        cfg_scale_speaker: float = 8.0,
    ) -> bytes:
        import torch
        import torchaudio
        from functools import partial
        import time
        
        start = time.time()
        
        # Save audio to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(speaker_audio_bytes)
            audio_path = f.name
        
        try:
            # Prepare text
            if not text.strip().startswith("[S"):
                text = f"[S1] {text}"
            
            # Load speaker audio
            speaker_audio = self.load_audio(audio_path).cuda()
            
            # Configure sampler for speed
            sample_fn = partial(
                self.sample_fn_class,
                num_steps=num_steps,
                cfg_scale_text=3.0,
                cfg_scale_speaker=cfg_scale_speaker,
                cfg_min_t=0.5,
                cfg_max_t=1.0,
                truncation_factor=0.8,
                rescale_k=1.2,
                rescale_sigma=3.0,
                speaker_kv_scale=1.5,
                speaker_kv_max_layers=24,
                speaker_kv_min_t=0.9,
                sequence_length=640,
            )
            
            # Generate
            with torch.inference_mode():
                audio_out, _ = self.sample_pipeline(
                    model=self.model,
                    fish_ae=self.fish_ae,
                    pca_state=self.pca_state,
                    sample_fn=sample_fn,
                    text_prompt=text,
                    speaker_audio=speaker_audio,
                    rng_seed=rng_seed,
                )
            
            # Encode to WAV
            buf = io.BytesIO()
            torchaudio.save(buf, audio_out[0].cpu(), 44100, format="wav")
            buf.seek(0)
            
            print(f"Generated in {time.time()-start:.2f}s")
            return buf.read()
            
        finally:
            os.unlink(audio_path)


@app.function(
    image=web_image,
    timeout=600,
    secrets=[modal.Secret.from_name("echo-tts-secrets")],
)
@modal.asgi_app()
def web_app():
    from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form
    from fastapi.responses import Response
    from fastapi.middleware.cors import CORSMiddleware
    from datetime import datetime
    from typing import Optional
    import requests as http_requests
    import base64

    app = FastAPI(title="Echo-TTS API")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    API_KEY = os.environ.get("API_KEY", "")

    def check_auth(request: Request):
        if not API_KEY:
            return
        auth = request.headers.get("Authorization", "")
        key = auth[7:] if auth.startswith("Bearer ") else request.headers.get("X-API-Key", "")
        if key != API_KEY:
            raise HTTPException(401, "Invalid API key")

    @app.get("/")
    def index():
        return {"service": "Echo-TTS", "gpu": "A10G", "inference": "local"}

    @app.get("/health")
    def health():
        return {"status": "ok", "ts": datetime.utcnow().isoformat()}

    @app.post("/tts")
    async def tts(request: Request):
        check_auth(request)
        
        content_type = request.headers.get("content-type", "")
        
        # Handle multipart form data (file upload)
        if "multipart/form-data" in content_type:
            form = await request.form()
            text = form.get("text")
            audio_file = form.get("audio")
            audio_url = form.get("speaker_audio_url")
            num_steps = int(form.get("num_steps", 24))
            rng_seed = int(form.get("rng_seed", 0))
            cfg_scale_speaker = float(form.get("cfg_scale_speaker", 8.0))
            
            if not text:
                raise HTTPException(400, "text required")
            
            # Get audio bytes from file or URL
            if audio_file:
                audio_bytes = await audio_file.read()
            elif audio_url:
                resp = http_requests.get(audio_url, timeout=30)
                resp.raise_for_status()
                audio_bytes = resp.content
            else:
                raise HTTPException(400, "audio file or speaker_audio_url required")
        
        # Handle JSON body
        else:
            data = await request.json()
            text = data.get("text")
            audio_url = data.get("speaker_audio_url")
            audio_base64 = data.get("audio_base64")  # Base64 encoded audio
            num_steps = data.get("num_steps", 24)
            rng_seed = data.get("rng_seed", 0)
            cfg_scale_speaker = data.get("cfg_scale_speaker", 8.0)
            
            if not text:
                raise HTTPException(400, "text required")
            
            # Get audio bytes from base64 or URL
            if audio_base64:
                audio_bytes = base64.b64decode(audio_base64)
            elif audio_url:
                resp = http_requests.get(audio_url, timeout=30)
                resp.raise_for_status()
                audio_bytes = resp.content
            else:
                raise HTTPException(400, "audio_base64 or speaker_audio_url required")
        
        # Generate
        tts_model = EchoTTS()
        audio = tts_model.generate.remote(
            text=text,
            speaker_audio_bytes=audio_bytes,
            num_steps=num_steps,
            rng_seed=rng_seed,
            cfg_scale_speaker=cfg_scale_speaker,
        )
        
        return Response(content=audio, media_type="audio/wav")

    return app
