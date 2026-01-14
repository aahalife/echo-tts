"""Echo-TTS API - Health check endpoint"""
import json
from datetime import datetime
from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        response = {
            'status': 'healthy',
            'service': 'echo-tts-api',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        self.wfile.write(json.dumps(response).encode())
