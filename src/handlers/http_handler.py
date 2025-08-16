#!/usr/bin/env python3
"""
HTTP Request Handler
Handles HTTP requests and routes them to appropriate Redfish handlers.
"""

import logging
import time
from http.server import BaseHTTPRequestHandler

logger = logging.getLogger(__name__)


class RedfishRequestHandler(BaseHTTPRequestHandler):
    """Redfish HTTP request handler"""
    
    def setup(self):
        """Setup connection - detect SSL attempts on HTTP port"""
        try:
            super().setup()
        except Exception as e:
            # Log SSL attempts cleanly
            logger.warning(f"Connection setup failed from {self.client_address[0]} - likely SSL/TLS attempt on HTTP port")
            raise
    
    def log_message(self, format, *args):
        """Override to use our logger with smart filtering"""
        try:
            # Filter out problematic requests
            message = format % args
            
            # Check if message contains binary data or SSL errors
            if isinstance(message, str):
                # Check for SSL/TLS handshake patterns
                has_ssl_error = any(pattern in message for pattern in [
                    'Bad request version', 'Bad request syntax', 'Bad HTTP/0.9 request'
                ])
                
                # Count printable vs non-printable characters
                printable_chars = sum(c.isprintable() or c.isspace() for c in message)
                total_chars = len(message)
                
                # Check for binary content in quotes (like "üPÛ4ÐÕ9ñ^f")
                has_binary_quotes = '"' in message and any(ord(c) > 127 for c in message if c != '"')
                
                # Filter out problematic content
                if total_chars > 0 and ((printable_chars / total_chars) < 0.5 or has_ssl_error or has_binary_quotes):
                    # Only log warning once per IP for SSL errors
                    client_ip = self.address_string()
                    if not hasattr(self.server, '_ssl_warnings'):
                        self.server._ssl_warnings = set()
                    
                    if has_ssl_error and client_ip not in self.server._ssl_warnings:
                        logger.warning(f"{client_ip} - HTTP request to HTTPS port or malformed request")
                        self.server._ssl_warnings.add(client_ip)
                    
                    # Don't log the binary/malformed data
                    return
                
            # Log normal requests
            logger.info(f"{self.address_string()} - {message}")
        except Exception as e:
            # Fallback to minimal logging if there's an error
            logger.debug(f"{self.address_string()} - Log filtering error: {e}")
    
    def parse_request(self):
        """Override to catch SSL/TLS attempts early"""
        try:
            return super().parse_request()
        except Exception as e:
            # Check if this looks like an SSL/TLS attempt
            if hasattr(self, 'raw_requestline') and self.raw_requestline:
                # SSL/TLS handshake typically starts with 0x16 (22 in decimal)
                if len(self.raw_requestline) > 0 and self.raw_requestline[0] == 0x16:
                    logger.warning(f"{self.client_address[0]} - SSL/TLS handshake detected on HTTP port - client should connect via HTTP")
                    return False
            
            logger.debug(f"Request parsing failed from {self.client_address[0]}: {e}")
            return False
    
    def do_GET(self):
        """Handle GET requests"""
        try:
            logger.debug(f"🌐 GET Request received: {self.path}")
            logger.debug(f"🔍 Headers: {dict(self.headers)}")
            logger.debug(f"📡 Client: {self.client_address}")
            
            start_time = time.time()
            self.server.handler.handle_get_request(self)
            end_time = time.time()
            
            logger.debug(f"⏱️ GET request processed in {end_time - start_time:.3f}s")
        except Exception as e:
            logger.error(f"❌ Error handling GET request {self.path}: {e}")
            logger.error(f"🔧 Exception details: {type(e).__name__}: {str(e)}")
            self.send_error(500, "Internal Server Error")
    
    def do_POST(self):
        """Handle POST requests"""
        try:
            logger.debug(f"🌐 POST Request received: {self.path}")
            logger.debug(f"🔍 Headers: {dict(self.headers)}")
            logger.debug(f"📡 Client: {self.client_address}")
            
            # Read POST data for debugging
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 0:
                post_data = self.rfile.read(content_length)
                logger.debug(f"📝 POST Data: {post_data.decode('utf-8', errors='replace')}")
                # Reset for the handler to read again
                import io
                self.rfile = io.BytesIO(post_data)
            
            start_time = time.time()
            self.server.handler.handle_post_request(self)
            end_time = time.time()
            
            logger.debug(f"⏱️ POST request processed in {end_time - start_time:.3f}s")
        except Exception as e:
            logger.error(f"❌ Error handling POST request {self.path}: {e}")
            logger.error(f"🔧 Exception details: {type(e).__name__}: {str(e)}")
            self.send_error(500, "Internal Server Error")
    
    def do_PATCH(self):
        """Handle PATCH requests"""
        try:
            logger.debug(f"🌐 PATCH Request received: {self.path}")
            logger.debug(f"🔍 Headers: {dict(self.headers)}")
            logger.debug(f"📡 Client: {self.client_address}")
            
            # Read PATCH data for debugging
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 0:
                patch_data = self.rfile.read(content_length)
                logger.debug(f"📝 PATCH Data: {patch_data.decode('utf-8', errors='replace')}")
                # Reset for the handler to read again
                import io
                self.rfile = io.BytesIO(patch_data)
            
            start_time = time.time()
            self.server.handler.handle_patch_request(self)
            end_time = time.time()
            
            logger.debug(f"⏱️ PATCH request processed in {end_time - start_time:.3f}s")
        except Exception as e:
            logger.error(f"❌ Error handling PATCH request {self.path}: {e}")
            logger.error(f"🔧 Exception details: {type(e).__name__}: {str(e)}")
            self.send_error(500, "Internal Server Error")
    
    def do_DELETE(self):
        """Handle DELETE requests"""
        try:
            logger.debug(f"🌐 DELETE Request received: {self.path}")
            logger.debug(f"🔍 Headers: {dict(self.headers)}")
            logger.debug(f"📡 Client: {self.client_address}")
            
            start_time = time.time()
            self.server.handler.handle_delete_request(self)
            end_time = time.time()
            
            logger.debug(f"⏱️ DELETE request processed in {end_time - start_time:.3f}s")
        except Exception as e:
            logger.error(f"❌ Error handling DELETE request {self.path}: {e}")
            logger.error(f"🔧 Exception details: {type(e).__name__}: {str(e)}")
            self.send_error(500, "Internal Server Error")
