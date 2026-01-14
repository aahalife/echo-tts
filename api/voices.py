"""Echo-TTS API - Voices endpoint (list and create)"""
import os
import json
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import cgi
import tempfile

try:
    from vercel_blob import put, list as blob_list
    from vercel_kv import kv
    STORAGE_AVAILABLE = True
except ImportError:
    STORAGE_AVAILABLE = False

from _utils import verify_api_key, error_response, json_response, cors_headers


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        cors_headers(self)
    
    def do_GET(self):
        """List all registered voices."""
        if not verify_api_key(self.headers):
            return error_response(self, 401, 'Invalid or missing API key')
        
        if not STORAGE_AVAILABLE:
            return json_response(self, {'voices': [], 'note': 'Storage not configured'})
        
        try:
            # Get all voice metadata from KV
            voice_keys = kv.keys('voice:*')
            voices = []
            
            for key in voice_keys:
                voice_data = kv.get(key)
                if voice_data:
                    voices.append(voice_data)
            
            return json_response(self, {'voices': voices})
        except Exception as e:
            return error_response(self, 500, f'Failed to list voices: {str(e)}')
    
    def do_POST(self):
        """Register a new voice from reference audio."""
        if not verify_api_key(self.headers):
            return error_response(self, 401, 'Invalid or missing API key')
        
        if not STORAGE_AVAILABLE:
            return error_response(self, 503, 'Storage not configured')
        
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
            existing = kv.get(f'voice:{voice_id}')
            if existing:
                return error_response(self, 409, f'Voice ID already exists: {voice_id}')
            
            # Determine file extension
            ext = original_filename.rsplit('.', 1)[-1].lower() if '.' in original_filename else 'wav'
            if ext not in ['wav', 'mp3', 'ogg', 'flac', 'm4a', 'aac']:
                ext = 'wav'
            
            # Upload audio to Vercel Blob
            blob_path = f'voices/{voice_id}.{ext}'
            blob_result = put(blob_path, audio_data, {'access': 'public'})
            
            # Store metadata in KV
            metadata = {
                'id': voice_id,
                'name': name,
                'description': description,
                'created_at': datetime.utcnow().isoformat() + 'Z',
                'blob_url': blob_result['url'],
                'file_size': len(audio_data),
                'original_filename': original_filename,
            }
            kv.set(f'voice:{voice_id}', metadata)
            
            return json_response(self, {
                'id': voice_id,
                'name': name,
                'created_at': metadata['created_at'],
                'message': 'Voice registered successfully'
            }, 201)
            
        except Exception as e:
            return error_response(self, 500, f'Failed to create voice: {str(e)}')
