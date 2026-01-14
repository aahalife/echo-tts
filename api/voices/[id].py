"""Echo-TTS API - Single voice endpoint (get/delete)"""
import os
import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse

try:
    from vercel_blob import delete as blob_delete
    from vercel_kv import kv
    STORAGE_AVAILABLE = True
except ImportError:
    STORAGE_AVAILABLE = False

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _utils import verify_api_key, error_response, json_response, cors_headers


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
        
        if not STORAGE_AVAILABLE:
            return error_response(self, 503, 'Storage not configured')
        
        voice_id = get_voice_id(self.path)
        if not voice_id:
            return error_response(self, 400, 'Voice ID required')
        
        try:
            metadata = kv.get(f'voice:{voice_id}')
            if not metadata:
                return error_response(self, 404, f'Voice not found: {voice_id}')
            
            return json_response(self, metadata)
        except Exception as e:
            return error_response(self, 500, f'Failed to get voice: {str(e)}')
    
    def do_DELETE(self):
        """Delete a voice."""
        if not verify_api_key(self.headers):
            return error_response(self, 401, 'Invalid or missing API key')
        
        if not STORAGE_AVAILABLE:
            return error_response(self, 503, 'Storage not configured')
        
        voice_id = get_voice_id(self.path)
        if not voice_id:
            return error_response(self, 400, 'Voice ID required')
        
        try:
            metadata = kv.get(f'voice:{voice_id}')
            if not metadata:
                return error_response(self, 404, f'Voice not found: {voice_id}')
            
            # Delete blob
            if metadata.get('blob_url'):
                try:
                    blob_delete(metadata['blob_url'])
                except:
                    pass  # Blob might already be deleted
            
            # Delete metadata
            kv.delete(f'voice:{voice_id}')
            
            return json_response(self, {'message': f'Voice deleted: {voice_id}'})
        except Exception as e:
            return error_response(self, 500, f'Failed to delete voice: {str(e)}')
