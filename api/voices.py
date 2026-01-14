"""Echo-TTS API - Voices endpoint (list and create)"""
import os
import json
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler
import cgi

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

BLOB_TOKEN = os.environ.get('BLOB_READ_WRITE_TOKEN', '')
BLOB_STORE_ID = os.environ.get('BLOB_STORE_ID', '')  # Optional, for custom store

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import verify_api_key, error_response, json_response, cors_headers


def blob_put(path, data, content_type='application/octet-stream'):
    """Upload data to Vercel Blob."""
    url = f'https://blob.vercel-storage.com/{path}'
    headers = {
        'Authorization': f'Bearer {BLOB_TOKEN}',
        'Content-Type': content_type,
        'x-api-version': '7',
    }
    response = requests.put(url, data=data, headers=headers)
    response.raise_for_status()
    return response.json()


def blob_list(prefix=''):
    """List blobs with optional prefix."""
    url = 'https://blob.vercel-storage.com'
    headers = {
        'Authorization': f'Bearer {BLOB_TOKEN}',
    }
    params = {'prefix': prefix} if prefix else {}
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json().get('blobs', [])


def blob_get(url):
    """Get blob content from URL."""
    response = requests.get(url)
    response.raise_for_status()
    return response.content


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        cors_headers(self)
    
    def do_GET(self):
        """List all registered voices."""
        if not verify_api_key(self.headers):
            return error_response(self, 401, 'Invalid or missing API key')
        
        if not BLOB_TOKEN:
            return json_response(self, {'voices': [], 'note': 'Storage not configured'})
        
        try:
            # List all metadata files
            blobs = blob_list(prefix='voices/')
            voices = []
            
            for blob in blobs:
                # Only process .json metadata files
                if blob.get('pathname', '').endswith('.json'):
                    try:
                        metadata_content = blob_get(blob['url'])
                        metadata = json.loads(metadata_content)
                        voices.append({
                            'id': metadata.get('id'),
                            'name': metadata.get('name'),
                            'created_at': metadata.get('created_at'),
                            'description': metadata.get('description', ''),
                        })
                    except:
                        pass  # Skip invalid metadata
            
            return json_response(self, {'voices': voices})
        except Exception as e:
            return error_response(self, 500, f'Failed to list voices: {str(e)}')
    
    def do_POST(self):
        """Register a new voice from reference audio."""
        if not verify_api_key(self.headers):
            return error_response(self, 401, 'Invalid or missing API key')
        
        if not BLOB_TOKEN:
            return error_response(self, 503, 'Storage not configured. Set BLOB_READ_WRITE_TOKEN.')
        
        try:
            content_type = self.headers.get('Content-Type', '')
            
            if 'multipart/form-data' in content_type:
                # Parse multipart form data
                form = cgi.FieldStorage(
                    fp=self.rfile,
                    headers=self.headers,
                    environ={'REQUEST_METHOD': 'POST'}
                )
                
                if 'audio' not in form:
                    return error_response(self, 400, 'No audio file provided')
                
                audio_item = form['audio']
                audio_data = audio_item.file.read()
                original_filename = audio_item.filename or 'audio.wav'
                
                voice_id = form.getvalue('id', str(uuid.uuid4())[:8])
                name = form.getvalue('name', voice_id)
                description = form.getvalue('description', '')
            else:
                return error_response(self, 400, 'Content-Type must be multipart/form-data')
            
            # Sanitize voice ID
            voice_id = ''.join(c for c in voice_id if c.isalnum() or c in '-_').lower()
            if not voice_id:
                return error_response(self, 400, 'Invalid voice ID')
            
            # Check if voice already exists
            try:
                existing_blobs = blob_list(prefix=f'voices/{voice_id}.')
                if any(b.get('pathname', '').endswith('.json') for b in existing_blobs):
                    return error_response(self, 409, f'Voice ID already exists: {voice_id}')
            except:
                pass  # If list fails, proceed anyway
            
            # Determine file extension
            ext = original_filename.rsplit('.', 1)[-1].lower() if '.' in original_filename else 'wav'
            if ext not in ['wav', 'mp3', 'ogg', 'flac', 'm4a', 'aac']:
                ext = 'wav'
            
            # Determine content type for audio
            audio_content_types = {
                'wav': 'audio/wav',
                'mp3': 'audio/mpeg',
                'ogg': 'audio/ogg',
                'flac': 'audio/flac',
                'm4a': 'audio/mp4',
                'aac': 'audio/aac',
            }
            audio_ct = audio_content_types.get(ext, 'audio/wav')
            
            # Upload audio to Vercel Blob
            audio_result = blob_put(f'voices/{voice_id}.{ext}', audio_data, audio_ct)
            audio_url = audio_result.get('url')
            
            # Create and upload metadata
            metadata = {
                'id': voice_id,
                'name': name,
                'description': description,
                'created_at': datetime.utcnow().isoformat() + 'Z',
                'audio_url': audio_url,
                'file_size': len(audio_data),
                'original_filename': original_filename,
            }
            blob_put(f'voices/{voice_id}.json', json.dumps(metadata).encode(), 'application/json')
            
            return json_response(self, {
                'id': voice_id,
                'name': name,
                'created_at': metadata['created_at'],
                'message': 'Voice registered successfully'
            }, 201)
            
        except Exception as e:
            return error_response(self, 500, f'Failed to create voice: {str(e)}')
