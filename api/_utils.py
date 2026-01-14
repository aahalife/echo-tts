"""Shared utilities for Echo-TTS API"""
import os
import json
from functools import wraps

# Environment variables
API_KEY = os.environ.get('API_KEY', '')
HF_SPACE = os.environ.get('HF_SPACE', 'jordand/echo-tts-preview')

# Default generation parameters
DEFAULT_PARAMS = {
    'preset_name': 'Independent (High Speaker CFG)',
    'num_steps': 40,
    'rng_seed': 0,
    'speaker_kv_enable': True,
    'speaker_kv_scale': 1.5,
}


def get_api_key_from_request(headers):
    """Extract API key from request headers."""
    # Check X-API-Key header
    if headers.get('X-API-Key'):
        return headers.get('X-API-Key')
    
    # Check Authorization: Bearer <token>
    auth_header = headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header[7:]
    
    return None


def verify_api_key(headers):
    """Verify the API key from request headers."""
    if not API_KEY:
        return True  # No API key configured, allow all
    
    provided_key = get_api_key_from_request(headers)
    return provided_key == API_KEY


def error_response(handler, status_code, message):
    """Send an error response."""
    handler.send_response(status_code)
    handler.send_header('Content-Type', 'application/json')
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.end_headers()
    handler.wfile.write(json.dumps({'error': message}).encode())


def json_response(handler, data, status_code=200):
    """Send a JSON response."""
    handler.send_response(status_code)
    handler.send_header('Content-Type', 'application/json')
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.end_headers()
    handler.wfile.write(json.dumps(data).encode())


def cors_headers(handler):
    """Send CORS headers for preflight requests."""
    handler.send_response(200)
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
    handler.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-API-Key')
    handler.send_header('Access-Control-Max-Age', '86400')
    handler.end_headers()
