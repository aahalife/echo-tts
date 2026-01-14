"""Echo-TTS API - Flask application for Vercel"""
import os
import json
import uuid
import tempfile
import base64
from datetime import datetime
from flask import Flask, request, jsonify, Response

try:
    from gradio_client import Client, handle_file
    GRADIO_AVAILABLE = True
except ImportError:
    GRADIO_AVAILABLE = False

try:
    import requests as http_requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# Configuration
API_KEY = os.environ.get('API_KEY', '')
BLOB_TOKEN = os.environ.get('BLOB_READ_WRITE_TOKEN', '')
HF_SPACE = os.environ.get('HF_SPACE', 'jordand/echo-tts-preview')

# Default generation parameters
DEFAULT_PARAMS = {
    'preset_name': 'Independent (High Speaker CFG)',
    'num_steps': 40,
    'rng_seed': 0,
    'speaker_kv_enable': True,
    'speaker_kv_scale': 1.5,
}

app = Flask(__name__)

# ============== Auth Helpers ==============

def get_api_key():
    """Extract API key from request."""
    if request.headers.get('X-API-Key'):
        return request.headers.get('X-API-Key')
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header[7:]
    return request.args.get('api_key')

def require_auth():
    """Check if request is authenticated."""
    if not API_KEY:
        return None
    if get_api_key() != API_KEY:
        return jsonify({'error': 'Invalid or missing API key'}), 401
    return None

# ============== Blob Helpers ==============

def blob_put(path, data, content_type='application/octet-stream'):
    """Upload data to Vercel Blob."""
    url = f'https://blob.vercel-storage.com/{path}'
    headers = {
        'Authorization': f'Bearer {BLOB_TOKEN}',
        'Content-Type': content_type,
        'x-api-version': '7',
    }
    response = http_requests.put(url, data=data, headers=headers)
    response.raise_for_status()
    return response.json()

def blob_list(prefix=''):
    """List blobs with optional prefix."""
    url = 'https://blob.vercel-storage.com'
    headers = {'Authorization': f'Bearer {BLOB_TOKEN}'}
    params = {'prefix': prefix} if prefix else {}
    response = http_requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json().get('blobs', [])

def blob_get(url):
    """Get blob content from URL."""
    response = http_requests.get(url)
    response.raise_for_status()
    return response.content

def blob_delete(urls):
    """Delete blobs by URLs."""
    url = 'https://blob.vercel-storage.com/delete'
    headers = {
        'Authorization': f'Bearer {BLOB_TOKEN}',
        'Content-Type': 'application/json',
    }
    response = http_requests.post(url, json={'urls': urls}, headers=headers)
    response.raise_for_status()
    return response.json()

# ============== Routes ==============

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        'service': 'Echo-TTS REST API',
        'version': '1.0.0',
        'description': 'Voice cloning and text-to-speech API powered by Echo-TTS',
        'endpoints': {
            'GET /api/health': 'Health check',
            'GET /api/voices': 'List all registered voices',
            'GET /api/voices/<id>': 'Get voice details',
            'POST /api/voices': 'Register a new voice',
            'DELETE /api/voices/<id>': 'Delete a registered voice',
            'POST /api/tts': 'Generate speech from text',
        },
        'defaults': DEFAULT_PARAMS
    })

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'service': 'echo-tts-api',
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })

@app.route('/api/voices', methods=['GET', 'POST', 'OPTIONS'])
def voices():
    if request.method == 'OPTIONS':
        return '', 200
    
    auth_error = require_auth()
    if auth_error:
        return auth_error
    
    if request.method == 'GET':
        return list_voices()
    else:
        return create_voice()

def list_voices():
    if not BLOB_TOKEN:
        return jsonify({'voices': [], 'note': 'Storage not configured'})
    
    try:
        blobs = blob_list(prefix='voices/')
        voices = []
        
        for blob in blobs:
            if blob.get('pathname', '').endswith('.json'):
                try:
                    metadata = json.loads(blob_get(blob['url']))
                    voices.append({
                        'id': metadata.get('id'),
                        'name': metadata.get('name'),
                        'created_at': metadata.get('created_at'),
                        'description': metadata.get('description', ''),
                    })
                except:
                    pass
        
        return jsonify({'voices': voices})
    except Exception as e:
        return jsonify({'error': f'Failed to list voices: {str(e)}'}), 500

def create_voice():
    if not BLOB_TOKEN:
        return jsonify({'error': 'Storage not configured'}), 503
    
    try:
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400
        
        audio_file = request.files['audio']
        audio_data = audio_file.read()
        original_filename = audio_file.filename or 'audio.wav'
        
        voice_id = request.form.get('id', str(uuid.uuid4())[:8])
        name = request.form.get('name', voice_id)
        description = request.form.get('description', '')
        
        # Sanitize voice ID
        voice_id = ''.join(c for c in voice_id if c.isalnum() or c in '-_').lower()
        if not voice_id:
            return jsonify({'error': 'Invalid voice ID'}), 400
        
        # Check if exists
        try:
            existing = blob_list(prefix=f'voices/{voice_id}.')
            if any(b.get('pathname', '').endswith('.json') for b in existing):
                return jsonify({'error': f'Voice ID already exists: {voice_id}'}), 409
        except:
            pass
        
        # Get extension
        ext = original_filename.rsplit('.', 1)[-1].lower() if '.' in original_filename else 'wav'
        if ext not in ['wav', 'mp3', 'ogg', 'flac', 'm4a', 'aac']:
            ext = 'wav'
        
        content_types = {'wav': 'audio/wav', 'mp3': 'audio/mpeg', 'ogg': 'audio/ogg', 
                        'flac': 'audio/flac', 'm4a': 'audio/mp4', 'aac': 'audio/aac'}
        
        # Upload audio
        audio_result = blob_put(f'voices/{voice_id}.{ext}', audio_data, content_types.get(ext, 'audio/wav'))
        
        # Upload metadata
        metadata = {
            'id': voice_id,
            'name': name,
            'description': description,
            'created_at': datetime.utcnow().isoformat() + 'Z',
            'audio_url': audio_result.get('url'),
            'file_size': len(audio_data),
        }
        blob_put(f'voices/{voice_id}.json', json.dumps(metadata).encode(), 'application/json')
        
        return jsonify({
            'id': voice_id,
            'name': name,
            'created_at': metadata['created_at'],
            'message': 'Voice registered successfully'
        }), 201
        
    except Exception as e:
        return jsonify({'error': f'Failed to create voice: {str(e)}'}), 500

@app.route('/api/voices/<voice_id>', methods=['GET', 'DELETE', 'OPTIONS'])
def voice_detail(voice_id):
    if request.method == 'OPTIONS':
        return '', 200
    
    auth_error = require_auth()
    if auth_error:
        return auth_error
    
    if not BLOB_TOKEN:
        return jsonify({'error': 'Storage not configured'}), 503
    
    if request.method == 'GET':
        return get_voice(voice_id)
    else:
        return delete_voice(voice_id)

def get_voice(voice_id):
    try:
        blobs = blob_list(prefix=f'voices/{voice_id}.')
        for blob in blobs:
            if blob.get('pathname', '').endswith('.json'):
                metadata = json.loads(blob_get(blob['url']))
                return jsonify(metadata)
        return jsonify({'error': f'Voice not found: {voice_id}'}), 404
    except Exception as e:
        return jsonify({'error': f'Failed to get voice: {str(e)}'}), 500

def delete_voice(voice_id):
    try:
        blobs = blob_list(prefix=f'voices/{voice_id}.')
        if not blobs:
            return jsonify({'error': f'Voice not found: {voice_id}'}), 404
        
        urls = [blob['url'] for blob in blobs]
        blob_delete(urls)
        return jsonify({'message': f'Voice deleted: {voice_id}'})
    except Exception as e:
        return jsonify({'error': f'Failed to delete voice: {str(e)}'}), 500

@app.route('/api/tts', methods=['POST', 'OPTIONS'])
def tts():
    if request.method == 'OPTIONS':
        return '', 200
    
    auth_error = require_auth()
    if auth_error:
        return auth_error
    
    if not GRADIO_AVAILABLE:
        return jsonify({'error': 'Gradio client not available'}), 503
    
    try:
        # Parse request
        if request.is_json:
            data = request.json
            text = data.get('text')
            voice_id = data.get('voice_id')
            audio_b64 = data.get('audio')
            audio_data = base64.b64decode(audio_b64) if audio_b64 else None
        else:
            text = request.form.get('text')
            voice_id = request.form.get('voice_id')
            audio_data = request.files['audio'].read() if 'audio' in request.files else None
            data = request.form
        
        if not text:
            return jsonify({'error': 'Text is required'}), 400
        
        # Get params
        params = DEFAULT_PARAMS.copy()
        for key in ['num_steps', 'rng_seed', 'speaker_kv_scale', 'preset_name']:
            if key in data:
                if key in ['num_steps', 'rng_seed']:
                    params[key] = int(data[key])
                elif key == 'speaker_kv_scale':
                    params[key] = float(data[key])
                else:
                    params[key] = data[key]
        if 'speaker_kv_enable' in data:
            val = data['speaker_kv_enable']
            params['speaker_kv_enable'] = val if isinstance(val, bool) else str(val).lower() in ('true', '1', 'yes')
        
        # Get audio URL
        audio_url = None
        if voice_id and BLOB_TOKEN:
            blobs = blob_list(prefix=f'voices/{voice_id}.')
            for blob in blobs:
                if blob.get('pathname', '').endswith('.json'):
                    metadata = json.loads(blob_get(blob['url']))
                    audio_url = metadata.get('audio_url')
                    break
            if not audio_url:
                return jsonify({'error': f'Voice not found: {voice_id}'}), 404
        elif not audio_data:
            return jsonify({'error': 'Either voice_id or audio must be provided'}), 400
        
        # Prepare text
        if not text.strip().startswith('[S'):
            text = f'[S1] {text}'
        
        # Handle audio
        temp_file = None
        audio_path = audio_url
        
        if audio_data:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
            temp_file.write(audio_data)
            temp_file.close()
            audio_path = temp_file.name
        
        try:
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
            
            audio_result = result[0]
            generated_path = audio_result.get('value') if isinstance(audio_result, dict) else audio_result
            
            if not generated_path:
                return jsonify({'error': 'No audio generated'}), 500
            
            with open(generated_path, 'rb') as f:
                audio_output = f.read()
            
            return Response(
                audio_output,
                mimetype='audio/wav',
                headers={'Content-Disposition': 'attachment; filename=output.wav'}
            )
        finally:
            if temp_file:
                try:
                    os.unlink(temp_file.name)
                except:
                    pass
                    
    except Exception as e:
        return jsonify({'error': f'TTS generation failed: {str(e)}'}), 500

# Add CORS headers to all responses
@app.after_request
def add_cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-API-Key'
    return response
