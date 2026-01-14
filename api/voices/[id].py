"""Echo-TTS API - Single voice endpoint (get/delete)"""
import os
import json
from http.server import BaseHTTPRequestHandler

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

BLOB_TOKEN = os.environ.get('BLOB_READ_WRITE_TOKEN', '')

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _utils import verify_api_key, error_response, json_response, cors_headers


def blob_list(prefix=''):
    """List blobs with optional prefix."""
    url = 'https://blob.vercel-storage.com'
    headers = {'Authorization': f'Bearer {BLOB_TOKEN}'}
    params = {'prefix': prefix} if prefix else {}
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json().get('blobs', [])


def blob_get(url):
    """Get blob content from URL."""
    response = requests.get(url)
    response.raise_for_status()
    return response.content


def blob_delete(urls):
    """Delete blobs by URLs."""
    url = 'https://blob.vercel-storage.com/delete'
    headers = {
        'Authorization': f'Bearer {BLOB_TOKEN}',
        'Content-Type': 'application/json',
    }
    response = requests.post(url, json={'urls': urls}, headers=headers)
    response.raise_for_status()
    return response.json()


def get_voice_id(path):
    """Extract voice ID from path like /api/voices/xyz"""
    parts = path.strip('/').split('/')
    if len(parts) >= 3:
        return parts[2]
    return None


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        cors_headers(self)
    
    def do_GET(self):
        """Get voice details."""
        if not verify_api_key(self.headers):
            return error_response(self, 401, 'Invalid or missing API key')
        
        if not BLOB_TOKEN:
            return error_response(self, 503, 'Storage not configured')
        
        voice_id = get_voice_id(self.path)
        if not voice_id:
            return error_response(self, 400, 'Voice ID required')
        
        try:
            # Find metadata file
            blobs = blob_list(prefix=f'voices/{voice_id}.')
            metadata_blob = None
            for blob in blobs:
                if blob.get('pathname', '').endswith('.json'):
                    metadata_blob = blob
                    break
            
            if not metadata_blob:
                return error_response(self, 404, f'Voice not found: {voice_id}')
            
            metadata_content = blob_get(metadata_blob['url'])
            metadata = json.loads(metadata_content)
            
            return json_response(self, metadata)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return error_response(self, 404, f'Voice not found: {voice_id}')
            return error_response(self, 500, f'Failed to get voice: {str(e)}')
        except Exception as e:
            return error_response(self, 500, f'Failed to get voice: {str(e)}')
    
    def do_DELETE(self):
        """Delete a voice."""
        if not verify_api_key(self.headers):
            return error_response(self, 401, 'Invalid or missing API key')
        
        if not BLOB_TOKEN:
            return error_response(self, 503, 'Storage not configured')
        
        voice_id = get_voice_id(self.path)
        if not voice_id:
            return error_response(self, 400, 'Voice ID required')
        
        try:
            # Find all blobs for this voice
            blobs = blob_list(prefix=f'voices/{voice_id}.')
            
            if not blobs:
                return error_response(self, 404, f'Voice not found: {voice_id}')
            
            # Delete all blobs (audio + metadata)
            urls_to_delete = [blob['url'] for blob in blobs]
            blob_delete(urls_to_delete)
            
            return json_response(self, {'message': f'Voice deleted: {voice_id}'})
        except Exception as e:
            return error_response(self, 500, f'Failed to delete voice: {str(e)}')
