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
    
    def log_message(self, format, *args):
        """Override to use our logger"""
        logger.info(f"{self.address_string()} - {format % args}")
    
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
