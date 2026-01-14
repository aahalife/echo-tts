"""Echo-TTS API - Root endpoint"""
import json
from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        response = {
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
            'defaults': {
                'speaker_kv_enable': True,
                'speaker_kv_scale': 1.5,
                'num_steps': 40,
                'preset': 'Independent (High Speaker CFG)'
            }
        }
        self.wfile.write(json.dumps(response).encode())
