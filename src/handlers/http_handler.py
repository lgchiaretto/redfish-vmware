#!/usr/bin/env python3
"""
Enhanced HTTP Request Handler
Handles HTTP requests with comprehensive logging, debugging, and performance monitoring.
Routes requests to appropriate Redfish handlers with detailed tracking.
"""

import json
import logging
import time
import threading
import uuid
from http.server import BaseHTTPRequestHandler
from utils.logging_config import create_debug_context, log_performance_metric

logger = logging.getLogger(__name__)


class RequestTracker:
    """Track request metrics and statistics"""
    
    def __init__(self):
        self.lock = threading.Lock()
        self.total_requests = 0
        self.requests_by_method = {}
        self.requests_by_path = {}
        self.average_response_time = 0
        self.start_time = time.time()
    
    def record_request(self, method, path, duration, status_code):
        with self.lock:
            self.total_requests += 1
            self.requests_by_method[method] = self.requests_by_method.get(method, 0) + 1
            self.requests_by_path[path] = self.requests_by_path.get(path, 0) + 1
            
            # Update average response time
            if self.average_response_time == 0:
                self.average_response_time = duration
            else:
                self.average_response_time = (self.average_response_time + duration) / 2
    
    def get_stats(self):
        with self.lock:
            uptime = time.time() - self.start_time
            return {
                'total_requests': self.total_requests,
                'uptime_seconds': uptime,
                'requests_per_minute': (self.total_requests / uptime) * 60 if uptime > 0 else 0,
                'average_response_time': self.average_response_time,
                'requests_by_method': self.requests_by_method.copy(),
                'top_paths': dict(sorted(self.requests_by_path.items(), key=lambda x: x[1], reverse=True)[:10])
            }


# Global request tracker
request_tracker = RequestTracker()


class RedfishRequestHandler(BaseHTTPRequestHandler):
    """Enhanced Redfish HTTP request handler with comprehensive logging"""
    
    def setup(self):
        """Setup connection with enhanced SSL/TLS detection"""
        self.request_id = str(uuid.uuid4())[:8]  # Short unique ID for this request
        try:
            super().setup()
            logger.debug(f"🔗 [{self.request_id}] Connection established from {self.client_address[0]}")
        except Exception as e:
            error_str = str(e).lower()
            client_ip = getattr(self, 'client_address', ['unknown'])[0] if hasattr(self, 'client_address') else 'unknown'
            
            if any(ssl_term in error_str for ssl_term in ['ssl', 'tls', 'handshake', 'wrong version']):
                logger.warning(f"🔒 [{self.request_id}] SSL/TLS connection attempt from {client_ip} on HTTP port")
                logger.info(f"💡 [{self.request_id}] Hint: Client should use HTTP (not HTTPS) for this endpoint")
            else:
                logger.warning(f"⚠️ [{self.request_id}] Connection setup failed from {client_ip}: {e}")
            raise
    
    def log_message(self, format, *args):
        """Enhanced logging with intelligent filtering and request tracking"""
        try:
            message = format % args
            client_ip = self.address_string()
            
            # Check for problematic content (binary data, SSL errors)
            if isinstance(message, str):
                has_ssl_error = any(pattern in message for pattern in [
                    'Bad request version', 'Bad request syntax', 'Bad HTTP/0.9 request'
                ])
                
                # Check for binary content
                printable_chars = sum(c.isprintable() or c.isspace() for c in message)
                total_chars = len(message)
                has_binary_quotes = '"' in message and any(ord(c) > 127 for c in message if c != '"')
                
                # Filter problematic content
                if total_chars > 0 and ((printable_chars / total_chars) < 0.5 or has_ssl_error or has_binary_quotes):
                    if not hasattr(self.server, '_ssl_warnings'):
                        self.server._ssl_warnings = set()
                    
                    if has_ssl_error and client_ip not in self.server._ssl_warnings:
                        logger.warning(f"🚫 [{self.request_id}] {client_ip} - Malformed HTTP request or HTTPS on HTTP port")
                        logger.info(f"💡 [{self.request_id}] Use HTTP protocol for this endpoint")
                        self.server._ssl_warnings.add(client_ip)
                    return
                
            # Log normal requests with enhanced information
            logger.info(f"🌐 [{self.request_id}] {client_ip} - {message}")
            
        except Exception as e:
            logger.debug(f"🔧 [{self.request_id}] Log filtering error: {e}")
    
    def parse_request(self):
        """Enhanced request parsing with better SSL/TLS detection"""
        try:
            return super().parse_request()
        except Exception as e:
            client_ip = getattr(self, 'client_address', ['unknown'])[0] if hasattr(self, 'client_address') else 'unknown'
            
            # Detect SSL/TLS handshake
            if hasattr(self, 'raw_requestline') and self.raw_requestline:
                if len(self.raw_requestline) > 0 and self.raw_requestline[0] == 0x16:
                    logger.warning(f"🔐 [{self.request_id}] {client_ip} - SSL/TLS handshake detected on HTTP port")
                    logger.info(f"💡 [{self.request_id}] Configure client to use HTTP (not HTTPS)")
                    
                    # Send helpful HTTP response
                    try:
                        self.wfile.write(b"HTTP/1.1 400 Bad Request\r\n")
                        self.wfile.write(b"Content-Type: text/plain\r\n")
                        self.wfile.write(b"Connection: close\r\n\r\n")
                        self.wfile.write(b"Error: SSL/TLS attempted on HTTP port. Use HTTP protocol.\r\n")
                        self.wfile.flush()
                    except:
                        pass
                    return False
            
            logger.debug(f"🔧 [{self.request_id}] Request parsing failed from {client_ip}: {e}")
            return False
    
    def _log_request_start(self, method, additional_info=None):
        """Log the start of a request with enhanced information"""
        client_info = {
            'ip': self.client_address[0],
            'port': self.client_address[1],
            'user_agent': self.headers.get('User-Agent', 'Unknown'),
            'content_type': self.headers.get('Content-Type', 'None'),
            'content_length': self.headers.get('Content-Length', '0')
        }
        
        logger.info(f"🚀 [{self.request_id}] {method} {self.path} - Client: {client_info['ip']}:{client_info['port']}")
        logger.debug(f"🔍 [{self.request_id}] User-Agent: {client_info['user_agent']}")
        logger.debug(f"📋 [{self.request_id}] Content-Type: {client_info['content_type']}, Length: {client_info['content_length']}")
        
        if additional_info:
            for key, value in additional_info.items():
                logger.debug(f"📝 [{self.request_id}] {key}: {value}")
        
        return client_info
    
    def _log_request_end(self, method, start_time, status_code=200, additional_info=None):
        """Log the end of a request with performance metrics"""
        duration = time.time() - start_time
        
        # Record in tracker
        request_tracker.record_request(method, self.path, duration, status_code)
        
        # Log completion
        status_emoji = "✅" if 200 <= status_code < 300 else "⚠️" if 300 <= status_code < 400 else "❌"
        logger.info(f"{status_emoji} [{self.request_id}] {method} {self.path} - {status_code} in {duration:.3f}s")
        
        if additional_info:
            for key, value in additional_info.items():
                logger.debug(f"📊 [{self.request_id}] {key}: {value}")
        
        # Log performance metrics if enabled
        log_performance_metric(logger, f"{method} {self.path}", duration, 200 <= status_code < 300,
                              status_code=status_code, request_id=self.request_id)
    
    def do_GET(self):
        """Handle GET requests with enhanced logging and error handling"""
        start_time = time.time()
        
        try:
            client_info = self._log_request_start('GET')
            
            with create_debug_context()('GET Request Processing'):
                self.server.handler.handle_get_request(self)
            
            self._log_request_end('GET', start_time)
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"❌ [{self.request_id}] GET {self.path} failed: {e}")
            logger.error(f"🔧 [{self.request_id}] Exception: {type(e).__name__}: {str(e)}")
            logger.debug(f"📍 [{self.request_id}] Stack trace:", exc_info=True)
            
            self._log_request_end('GET', start_time, 500)
            self.send_error(500, "Internal Server Error")
    
    def do_POST(self):
        """Handle POST requests with enhanced logging and body analysis"""
        start_time = time.time()
        
        try:
            # Read and log POST data
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = None
            
            if content_length > 0:
                post_data = self.rfile.read(content_length)
                logger.debug(f"� [{self.request_id}] POST body ({content_length} bytes): {post_data.decode('utf-8', errors='replace')}")
                
                # Parse JSON if possible
                try:
                    if self.headers.get('Content-Type', '').startswith('application/json'):
                        json_data = json.loads(post_data.decode('utf-8'))
                        logger.debug(f"📋 [{self.request_id}] Parsed JSON: {json.dumps(json_data, indent=2)}")
                except json.JSONDecodeError as je:
                    logger.warning(f"⚠️ [{self.request_id}] Invalid JSON in POST body: {je}")
                
                # Reset stream for handler
                import io
                self.rfile = io.BytesIO(post_data)
            
            client_info = self._log_request_start('POST', {'body_size': content_length})
            
            with create_debug_context()('POST Request Processing'):
                self.server.handler.handle_post_request(self)
            
            self._log_request_end('POST', start_time)
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"❌ [{self.request_id}] POST {self.path} failed: {e}")
            logger.error(f"🔧 [{self.request_id}] Exception: {type(e).__name__}: {str(e)}")
            logger.debug(f"📍 [{self.request_id}] Stack trace:", exc_info=True)
            
            self._log_request_end('POST', start_time, 500)
            self.send_error(500, "Internal Server Error")
    
    def do_PATCH(self):
        """Handle PATCH requests with enhanced logging and body analysis"""
        start_time = time.time()
        
        try:
            # Read and log PATCH data
            content_length = int(self.headers.get('Content-Length', 0))
            patch_data = None
            
            if content_length > 0:
                patch_data = self.rfile.read(content_length)
                logger.debug(f"� [{self.request_id}] PATCH body ({content_length} bytes): {patch_data.decode('utf-8', errors='replace')}")
                
                # Parse JSON if possible
                try:
                    if self.headers.get('Content-Type', '').startswith('application/json'):
                        json_data = json.loads(patch_data.decode('utf-8'))
                        logger.debug(f"📋 [{self.request_id}] Parsed JSON: {json.dumps(json_data, indent=2)}")
                except json.JSONDecodeError as je:
                    logger.warning(f"⚠️ [{self.request_id}] Invalid JSON in PATCH body: {je}")
                
                # Reset stream for handler
                import io
                self.rfile = io.BytesIO(patch_data)
            
            client_info = self._log_request_start('PATCH', {'body_size': content_length})
            
            with create_debug_context()('PATCH Request Processing'):
                self.server.handler.handle_patch_request(self)
            
            self._log_request_end('PATCH', start_time)
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"❌ [{self.request_id}] PATCH {self.path} failed: {e}")
            logger.error(f"🔧 [{self.request_id}] Exception: {type(e).__name__}: {str(e)}")
            logger.debug(f"📍 [{self.request_id}] Stack trace:", exc_info=True)
            
            self._log_request_end('PATCH', start_time, 500)
            self.send_error(500, "Internal Server Error")
    
    def do_DELETE(self):
        """Handle DELETE requests with enhanced logging"""
        start_time = time.time()
        
        try:
            client_info = self._log_request_start('DELETE')
            
            with create_debug_context()('DELETE Request Processing'):
                self.server.handler.handle_delete_request(self)
            
            self._log_request_end('DELETE', start_time)
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"❌ [{self.request_id}] DELETE {self.path} failed: {e}")
            logger.error(f"🔧 [{self.request_id}] Exception: {type(e).__name__}: {str(e)}")
            logger.debug(f"📍 [{self.request_id}] Stack trace:", exc_info=True)
            
            self._log_request_end('DELETE', start_time, 500)
            self.send_error(500, "Internal Server Error")
    
    def get_request_stats(self):
        """Get current request statistics"""
        return request_tracker.get_stats()


def get_request_statistics():
    """Get global request statistics"""
    return request_tracker.get_stats()
