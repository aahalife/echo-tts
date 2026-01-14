"""Echo-TTS API - TTS generation endpoint"""
import os
import json
import tempfile
import base64
from http.server import BaseHTTPRequestHandler
import cgi

try:
    from gradio_client import Client, handle_file
    GRADIO_AVAILABLE = True
except ImportError:
    GRADIO_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

BLOB_TOKEN = os.environ.get('BLOB_READ_WRITE_TOKEN', '')

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _utils import verify_api_key, error_response, cors_headers, DEFAULT_PARAMS, HF_SPACE


def blob_list(prefix=''):
    """List blobs with optional prefix."""
    url = 'https://blob.vercel-storage.com'
    headers = {'Authorization': f'Bearer {BLOB_TOKEN}'}
    params = {'prefix': prefix} if prefix else {}
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json().get('blobs', [])


def blob_get_json(url):
    """Get JSON blob content from URL."""
    response = requests.get(url)
    response.raise_for_status()
    return response.json()


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        cors_headers(self)
    
    def do_POST(self):
        """Generate speech from text."""
        if not verify_api_key(self.headers):
            return error_response(self, 401, 'Invalid or missing API key')
        
        if not GRADIO_AVAILABLE:
            return error_response(self, 503, 'Gradio client not available')
        
        try:
            content_type = self.headers.get('Content-Type', '')
            content_length = int(self.headers.get('Content-Length', 0))
            
            text = None
            voice_id = None
            audio_data = None
            audio_url = None
            params = DEFAULT_PARAMS.copy()
            
            if 'application/json' in content_type:
                body = self.rfile.read(content_length)
                data = json.loads(body)
                text = data.get('text')
                voice_id = data.get('voice_id')
                audio_b64 = data.get('audio')
                
                if audio_b64:
                    audio_data = base64.b64decode(audio_b64)
                
                # Override params if provided
                if 'num_steps' in data:
                    params['num_steps'] = int(data['num_steps'])
                if 'rng_seed' in data:
                    params['rng_seed'] = int(data['rng_seed'])
                if 'speaker_kv_enable' in data:
                    params['speaker_kv_enable'] = bool(data['speaker_kv_enable'])
                if 'speaker_kv_scale' in data:
                    params['speaker_kv_scale'] = float(data['speaker_kv_scale'])
                if 'preset_name' in data:
                    params['preset_name'] = data['preset_name']
                    
            elif 'multipart/form-data' in content_type:
                form = cgi.FieldStorage(
                    fp=self.rfile,
                    headers=self.headers,
                    environ={'REQUEST_METHOD': 'POST'}
                )
                text = form.getvalue('text')
                voice_id = form.getvalue('voice_id')
                
                if 'audio' in form:
                    audio_item = form['audio']
                    audio_data = audio_item.file.read()
                
                # Override params if provided
                if form.getvalue('num_steps'):
                    params['num_steps'] = int(form.getvalue('num_steps'))
                if form.getvalue('rng_seed'):
                    params['rng_seed'] = int(form.getvalue('rng_seed'))
                if form.getvalue('speaker_kv_enable'):
                    val = form.getvalue('speaker_kv_enable')
                    params['speaker_kv_enable'] = val.lower() in ('true', '1', 'yes')
                if form.getvalue('speaker_kv_scale'):
                    params['speaker_kv_scale'] = float(form.getvalue('speaker_kv_scale'))
                if form.getvalue('preset_name'):
                    params['preset_name'] = form.getvalue('preset_name')
            else:
                return error_response(self, 400, 'Content-Type must be application/json or multipart/form-data')
            
            if not text:
                return error_response(self, 400, 'Text is required')
            
            # Resolve audio source from voice_id
            if voice_id and BLOB_TOKEN:
                # Find metadata file for this voice
                blobs = blob_list(prefix=f'voices/{voice_id}.')
                metadata_blob = None
                for blob in blobs:
                    if blob.get('pathname', '').endswith('.json'):
                        metadata_blob = blob
                        break
                
                if not metadata_blob:
                    return error_response(self, 404, f'Voice not found: {voice_id}')
                
                metadata = blob_get_json(metadata_blob['url'])
                audio_url = metadata.get('audio_url')
                
                if not audio_url:
                    return error_response(self, 500, f'Voice has no audio URL: {voice_id}')
                    
            elif not audio_data and not audio_url:
                return error_response(self, 400, 'Either voice_id or audio must be provided')
            
            # Prepare text
            if not text.strip().startswith('[S'):
                text = f'[S1] {text}'
            
            # Create temp file for audio if we have raw data
            temp_file = None
            audio_path = audio_url
            
            if audio_data:
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
                temp_file.write(audio_data)
                temp_file.close()
                audio_path = temp_file.name
            
            try:
                # Call HuggingFace API
                client = Client(HF_SPACE)
                
                result = client.predict(
                    text_prompt=text,
                    speaker_audio_path=handle_file(audio_path),
                    preset_name=params['preset_name'],
                    rng_seed=params['rng_seed'],
                    num_steps=params['num_steps'],
                    speaker_kv_enable=params['speaker_kv_enable'],
                    speaker_kv_scale=params['speaker_kv_scale'],
                    api_name="/generate_audio_simple"
                )
                
                # Get audio path from result
                audio_result = result[0]
                if isinstance(audio_result, dict):
                    generated_audio_path = audio_result.get('value')
                else:
                    generated_audio_path = audio_result
                
                if not generated_audio_path:
                    return error_response(self, 500, 'No audio generated')
                
                # Read and return the audio file
                with open(generated_audio_path, 'rb') as f:
                    audio_output = f.read()
                
                self.send_response(200)
                self.send_header('Content-Type', 'audio/wav')
                self.send_header('Content-Disposition', 'attachment; filename="output.wav"')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Content-Length', str(len(audio_output)))
                self.end_headers()
                self.wfile.write(audio_output)
                
            finally:
                if temp_file:
                    try:
                        os.unlink(temp_file.name)
                    except:
                        pass
                        
        except Exception as e:
            return error_response(self, 500, f'TTS generation failed: {str(e)}')
