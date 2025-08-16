#!/usr/bin/env python3
"""
Main Redfish Handler - AI-Generated

Note: This application is AI-generated.

Routes requests to appropriate handlers and manages the overall Redfish protocol.
"""

import json
import logging
import time
from typing import Dict, Optional
from urllib.parse import urlparse, parse_qs

from auth.manager import AuthenticationManager
from tasks.manager import TaskManager
from models.redfish_schemas import RedfishModels
from vmware_client import VMwareClient
from .systems_handler import SystemsHandler
from .managers_handler import ManagersHandler
from .chassis_handler import ChassisHandler
from .update_service_handler import UpdateServiceHandler

logger = logging.getLogger(__name__)


class RedfishHandler:
    """Main Redfish protocol handler"""
    
    def __init__(self, vm_configs, config=None):
        self.vm_configs = {vm['name']: vm for vm in vm_configs}
        self.config = config or {}
        self.vmware_clients = {}
        
        # Initialize components
        self.auth_manager = AuthenticationManager(config)
        self.task_manager = TaskManager()
        
        # Initialize handlers
        self.systems_handler = SystemsHandler(self.vm_configs, self.vmware_clients, self.task_manager)
        self.managers_handler = ManagersHandler(self.vm_configs, self.vmware_clients)
        self.chassis_handler = ChassisHandler(self.vm_configs, self.vmware_clients)
        self.update_service_handler = UpdateServiceHandler(self.vm_configs, self.vmware_clients, self.task_manager)
        
        # Initialize VMware clients for each VM
        for vm_name, vm_config in self.vm_configs.items():
            try:
                self.vmware_clients[vm_name] = VMwareClient(
                    vm_config['vcenter_host'],
                    vm_config['vcenter_user'],
                    vm_config['vcenter_password'],
                    disable_ssl=vm_config.get('disable_ssl', True)
                )
                logger.info(f"✅ VMware client initialized for VM: {vm_name}")
            except Exception as e:
                logger.error(f"❌ Failed to initialize VMware client for {vm_name}: {e}")
        
        logger.info(f"🚀 Redfish handler initialized for {len(self.vm_configs)} VMs")
    
    def handle_get_request(self, request_handler):
        """Handle GET requests with enhanced Metal3/Ironic logging"""
        path = request_handler.path
        client_ip = request_handler.client_address[0]
        user_agent = request_handler.headers.get('User-Agent', 'Unknown')
        
        # Enhanced logging for Metal3/Ironic debugging
        logger.info(f"🔍 GET {path} from {client_ip}")
        logger.debug(f"🤖 User-Agent: {user_agent}")
        logger.debug(f"🎯 Processing GET request for path: {path}")
        
        # Metal3/Ironic specific detection
        if 'ironic' in user_agent.lower() or 'metal3' in user_agent.lower():
            logger.warning(f"🔧 METAL3/IRONIC REQUEST DETECTED: {path}")
            logger.warning(f"🔧 This request is from Metal3/Ironic - ensure it succeeds!")
            
        # Check for common Metal3/Ironic inspection patterns
        if any(pattern in path for pattern in ['/UpdateService', '/TaskService', '/FirmwareInventory', '/SoftwareInventory', '/Storage', '/Bios']):
            logger.warning(f"🔄 CRITICAL METAL3 INSPECTION ENDPOINT: {path}")
            logger.warning(f"🔄 Metal3 is checking this endpoint - response must be valid!")
        
        try:
            # Route the request
            self._route_get_request(request_handler, path)
        except Exception as e:
            logger.error(f"❌ Error processing GET request {path}: {e}")
            self._send_error_response(request_handler, 500, "Internal Server Error")
    
    def handle_post_request(self, request_handler):
        """Handle POST requests"""
        path = request_handler.path
        logger.info(f"📝 POST {path}")
        
        try:
            self._route_post_request(request_handler, path)
        except Exception as e:
            logger.error(f"❌ Error processing POST request {path}: {e}")
            self._send_error_response(request_handler, 500, "Internal Server Error")
    
    def handle_patch_request(self, request_handler):
        """Handle PATCH requests"""
        path = request_handler.path
        logger.info(f"🔧 PATCH {path}")
        
        try:
            self._route_patch_request(request_handler, path)
        except Exception as e:
            logger.error(f"❌ Error processing PATCH request {path}: {e}")
            self._send_error_response(request_handler, 500, "Internal Server Error")
    
    def handle_delete_request(self, request_handler):
        """Handle DELETE requests"""
        path = request_handler.path
        logger.info(f"🗑️ DELETE {path}")
        
        try:
            self._route_delete_request(request_handler, path)
        except Exception as e:
            logger.error(f"❌ Error processing DELETE request {path}: {e}")
            self._send_error_response(request_handler, 500, "Internal Server Error")
    
    def _route_get_request(self, request_handler, path):
        """Route GET requests to appropriate handlers"""
        # Service root - always public
        if path == '/redfish/v1/' or path == '/redfish/v1':
            data = RedfishModels.get_service_root()
            self._send_json_response(request_handler, 200, data)
            return
        
        # Check authentication for all other endpoints
        authenticated, username = self.auth_manager.authenticate_request(request_handler)
        if not authenticated:
            self._send_auth_challenge(request_handler)
            return
        
        # Route to specific handlers
        if path.startswith('/redfish/v1/Systems'):
            self.systems_handler.handle_get(request_handler, path)
        elif path.startswith('/redfish/v1/Managers'):
            self.managers_handler.handle_get(request_handler, path)
        elif path.startswith('/redfish/v1/Chassis'):
            self.chassis_handler.handle_get(request_handler, path)
        elif path.startswith('/redfish/v1/UpdateService'):
            self.update_service_handler.handle_get(request_handler, path)
        elif path.startswith('/redfish/v1/TaskService'):
            self._handle_task_service(request_handler, path)
        elif path.startswith('/redfish/v1/SessionService'):
            self._handle_session_service(request_handler, path)
        else:
            self._send_error_response(request_handler, 404, "Not Found")
    
    def _route_post_request(self, request_handler, path):
        """Route POST requests to appropriate handlers"""
        # Most POST requests require authentication
        if not path.startswith('/redfish/v1/SessionService/Sessions'):
            authenticated, username = self.auth_manager.authenticate_request(request_handler)
            if not authenticated:
                self._send_auth_challenge(request_handler)
                return
        
        # Route to specific handlers
        if path.startswith('/redfish/v1/Systems'):
            self.systems_handler.handle_post(request_handler, path)
        elif path.startswith('/redfish/v1/SessionService/Sessions'):
            self._handle_session_creation(request_handler)
        else:
            self._send_error_response(request_handler, 404, "Not Found")
    
    def _route_patch_request(self, request_handler, path):
        """Route PATCH requests to appropriate handlers"""
        authenticated, username = self.auth_manager.authenticate_request(request_handler)
        if not authenticated:
            self._send_auth_challenge(request_handler)
            return
        
        # Route to specific handlers
        if path.startswith('/redfish/v1/Systems'):
            self.systems_handler.handle_patch(request_handler, path)
        else:
            self._send_error_response(request_handler, 404, "Not Found")
    
    def _route_delete_request(self, request_handler, path):
        """Route DELETE requests to appropriate handlers"""
        authenticated, username = self.auth_manager.authenticate_request(request_handler)
        if not authenticated:
            self._send_auth_challenge(request_handler)
            return
        
        # Route to specific handlers
        if path.startswith('/redfish/v1/SessionService/Sessions'):
            self._handle_session_deletion(request_handler, path)
        else:
            self._send_error_response(request_handler, 404, "Not Found")
    
    def _handle_task_service(self, request_handler, path):
        """Handle TaskService requests"""
        if path == '/redfish/v1/TaskService':
            data = self.task_manager.get_task_service()
            self._send_json_response(request_handler, 200, data)
        elif path == '/redfish/v1/TaskService/Tasks':
            data = self.task_manager.list_tasks()
            self._send_json_response(request_handler, 200, data)
        elif '/TaskService/Tasks/' in path:
            task_id = path.split('/')[-1]
            task = self.task_manager.get_task(task_id)
            if task:
                self._send_json_response(request_handler, 200, task)
            else:
                self._send_error_response(request_handler, 404, "Task not found")
        else:
            self._send_error_response(request_handler, 404, "Not Found")
    
    def _handle_session_service(self, request_handler, path):
        """Handle SessionService requests"""
        if path == '/redfish/v1/SessionService':
            data = RedfishModels.get_session_service()
            self._send_json_response(request_handler, 200, data)
        elif path == '/redfish/v1/SessionService/Sessions':
            data = self.auth_manager.list_sessions()
            self._send_json_response(request_handler, 200, data)
        elif '/SessionService/Sessions/' in path:
            session_id = path.split('/')[-1]
            session = self.auth_manager.get_session(session_id)
            if session:
                self._send_json_response(request_handler, 200, session)
            else:
                self._send_error_response(request_handler, 404, "Session not found")
        else:
            self._send_error_response(request_handler, 404, "Not Found")
    
    def _handle_session_creation(self, request_handler):
        """Handle session creation"""
        try:
            content_length = int(request_handler.headers.get('Content-Length', 0))
            if content_length > 0:
                post_data = request_handler.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                username = data.get('UserName', 'admin')
                password = data.get('Password', 'password')
                
                # Validate credentials
                if username == 'admin' and password == 'password':
                    session = self.auth_manager.create_session(username)
                    self._send_json_response(request_handler, 201, session)
                else:
                    self._send_error_response(request_handler, 401, "Invalid credentials")
            else:
                self._send_error_response(request_handler, 400, "Missing credentials")
        except Exception as e:
            logger.error(f"❌ Session creation error: {e}")
            self._send_error_response(request_handler, 500, "Internal Server Error")
    
    def _handle_session_deletion(self, request_handler, path):
        """Handle session deletion"""
        session_id = path.split('/')[-1]
        if self.auth_manager.delete_session(session_id):
            request_handler.send_response(204)
            request_handler.end_headers()
        else:
            self._send_error_response(request_handler, 404, "Session not found")
    
    def _send_json_response(self, request_handler, status_code, data):
        """Send JSON response with enhanced debugging"""
        try:
            logger.debug(f"📤 Preparing JSON response: status={status_code}")
            
            json_data = json.dumps(data, indent=2)
            json_size = len(json_data)
            
            logger.debug(f"📤 JSON payload size: {json_size} bytes")
            
            # Log critical responses at warning level for Metal3 debugging
            if status_code >= 400:
                logger.error(f"❌ ERROR RESPONSE: {status_code}")
                logger.error(f"❌ Response data: {json_data[:500]}...")  # First 500 chars
            elif any(keyword in request_handler.path for keyword in ['/UpdateService', '/FirmwareInventory', '/TaskService']):
                logger.warning(f"🔄 CRITICAL RESPONSE for Metal3: {status_code}")
                logger.debug(f"🔄 Critical response data: {json_data[:200]}...")  # First 200 chars
            else:
                logger.debug(f"📤 Standard response: {status_code}")
                logger.debug(f"📤 Response data: {json_data[:100]}...")  # First 100 chars
            
            request_handler.send_response(status_code)
            request_handler.send_header('Content-Type', 'application/json')
            request_handler.send_header('Content-Length', str(json_size))
            request_handler.send_header('Cache-Control', 'no-cache')
            request_handler.end_headers()
            request_handler.wfile.write(json_data.encode('utf-8'))
            
            logger.debug(f"✅ JSON response sent successfully: {status_code}")
            
        except Exception as e:
            logger.error(f"❌ CRITICAL: Failed to send JSON response: {e}")
            logger.error(f"❌ Status code: {status_code}")
            logger.error(f"❌ Data type: {type(data)}")
            raise
    
    def _send_error_response(self, request_handler, status_code, message):
        """Send error response"""
        error_data = {
            "error": {
                "code": f"Base.1.0.{status_code}",
                "message": message
            }
        }
        self._send_json_response(request_handler, status_code, error_data)
    
    def _send_auth_challenge(self, request_handler):
        """Send authentication challenge"""
        request_handler.send_response(401)
        request_handler.send_header('WWW-Authenticate', 'Basic realm="Redfish VMware Server"')
        request_handler.send_header('Content-Type', 'application/json')
        request_handler.end_headers()
        
        error_data = {
            "error": {
                "code": "Base.1.0.401",
                "message": "Authentication required"
            }
        }
        request_handler.wfile.write(json.dumps(error_data).encode('utf-8'))
    
    def shutdown(self):
        """Shutdown the handler"""
        logger.info("🛑 Shutting down Redfish handler")
        self.task_manager.shutdown()
        
        # Disconnect VMware clients
        for vm_name, client in self.vmware_clients.items():
            try:
                client.disconnect()
                logger.info(f"🔌 Disconnected VMware client for: {vm_name}")
            except Exception as e:
                logger.error(f"❌ Error disconnecting VMware client for {vm_name}: {e}")
