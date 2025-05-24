"""
Simple HTTP server for handling Stripe webhooks alongside Telegram bot.
This runs on a separate port from the telegram webhook.
"""
import asyncio
from datetime import datetime
import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import threading
from typing import Optional
import pytz
from handlers.webhook_handlers import WebhookHandlers

logger = logging.getLogger(__name__)

class StripeWebhookHandler(BaseHTTPRequestHandler):
    webhook_handlers: Optional[WebhookHandlers] = None
    
    def do_POST(self):
        """Handle POST requests for Stripe webhooks."""
        try:
            # Parse URL path
            parsed_path = urlparse(self.path)
            
            if parsed_path.path == '/webhook/stripe':
                # Get request body
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length)
                
                # Get Stripe signature
                signature = self.headers.get('Stripe-Signature')
                
                # Create mock request object for webhook handler
                class MockRequest:
                    def __init__(self, body: bytes, headers: dict):
                        self.body = body
                        self.headers = headers
                
                mock_request = MockRequest(body, dict(self.headers))
                
                # Process webhook
                if self.webhook_handlers:
                    # Run async handler in event loop
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        result = loop.run_until_complete(
                            self.webhook_handlers.handle_stripe_webhook(mock_request)
                        )
                        
                        # Send response
                        self.send_response(result['status'])
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({
                            'message': result['message']
                        }).encode())
                        
                    finally:
                        loop.close()
                else:
                    self.send_response(500)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(b'{"error": "Webhook handlers not initialized"}')
                    
            elif parsed_path.path == '/health':
                # Health check endpoint
                if self.webhook_handlers:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        result = loop.run_until_complete(
                            self.webhook_handlers.health_check()
                        )
                        
                        self.send_response(result['status'])
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({
                            'message': result['message']
                        }).encode())
                        
                    finally:
                        loop.close()
                else:
                    self.send_response(503)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(b'{"error": "Service unavailable"}')
            else:
                # Unknown endpoint
                self.send_response(404)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"error": "Not found"}')
                
        except Exception as e:
            logger.error(f"Error handling webhook request: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'error': 'Internal server error'
            }).encode())
    
    def do_GET(self):
        """Handle GET requests (health checks)."""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/health':
            self.do_POST()  # Reuse POST logic for health check
        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Not found')
    
    def log_message(self, format, *args):
        """Override to use our logger instead of stderr."""
        logger.info(f"Webhook server: {format % args}")

class WebhookServer:
    def __init__(self, webhook_handlers: WebhookHandlers, port: int = 8080):
        self.webhook_handlers = webhook_handlers
        self.port = port
        self.server = None
        self.thread = None
    
    def start(self):
        """Start the webhook server in a separate thread."""
        try:
            # Set the webhook handlers class variable
            StripeWebhookHandler.webhook_handlers = self.webhook_handlers
            
            # Create server
            self.server = HTTPServer(('0.0.0.0', self.port), StripeWebhookHandler)
            
            # Start in separate thread
            self.thread = threading.Thread(target=self.server.serve_forever)
            self.thread.daemon = True
            self.thread.start()

            # Log the current time
            logger.info(f"Current time (UTC): {datetime.now(pytz.utc)}")
            
            logger.info(f"Webhook server started on port {self.port}")
            logger.info(f"Stripe webhook endpoint: http://localhost:{self.port}/webhook/stripe")
            logger.info(f"Health check endpoint: http://localhost:{self.port}/health")
            
        except Exception as e:
            logger.error(f"Failed to start webhook server: {e}")
            raise
    
    def stop(self):
        """Stop the webhook server."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            logger.info("Webhook server stopped")
        
        if self.thread:
            self.thread.join(timeout=5)

# Usage example:
# webhook_server = WebhookServer(webhook_handlers, port=8080)
# webhook_server.start() 