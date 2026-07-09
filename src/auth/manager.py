#!/usr/bin/env python3
"""
Authentication Module
Handles Redfish authentication and session management.
"""

import base64
import logging
import time
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class AuthenticationManager:
    """Manages authentication and sessions for Redfish server"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.sessions = {}
        self.session_timeout = 600  # 10 minutes
        logger.info("🔐 Authentication manager initialized")
    
    def authenticate_request(self, request_handler) -> Tuple[bool, Optional[str]]:
        """
        Authenticate incoming request
        
        Args:
            request_handler: HTTP request handler
            
        Returns:
            Tuple of (is_authenticated, username)
        """
        auth_header = request_handler.headers.get('Authorization')
        
        if not auth_header:
            logger.debug("🔒 No authorization header found")
            return False, None
        
        try:
            if auth_header.startswith('Basic '):
                # Basic Authentication
                encoded_credentials = auth_header[6:]
                decoded_credentials = base64.b64decode(encoded_credentials).decode('utf-8')
                username, password = decoded_credentials.split(':', 1)
                
                logger.debug(f"🔑 Basic auth attempt for user: {username}")
                
                if self._check_credentials(username, password):
                    logger.info(f"✅ Basic authentication successful for: {username}")
                    return True, username
                else:
                    logger.warning(f"❌ Basic authentication failed for: {username}")
                    return False, None
                    
            elif auth_header.startswith('Bearer '):
                # Session Token Authentication
                token = auth_header[7:]
                return self._validate_session_token(token)
                
        except Exception as e:
            logger.error(f"❌ Authentication error: {e}")
            return False, None
        
        logger.debug("🔒 Unsupported authentication method")
        return False, None

    def _check_credentials(self, username: str, password: str) -> bool:
        """
        Validate username/password against the configured VM credentials.

        Accepts a match on any (redfish_user, redfish_password) pair defined in
        the vm list, or the legacy default admin:password fallback.
        """
        # Legacy fallback always accepted (keeps backward compatibility)
        if username == 'admin' and password == 'password':
            return True

        # Check against every VM's individual Redfish credentials
        for vm in self.config.get('vms', []):
            if isinstance(vm, dict):
                vm_user = vm.get('redfish_user')
                vm_pass = vm.get('redfish_password')
                if vm_user and vm_user == username and vm_pass and vm_pass == password:
                    return True

        return False

    def create_session(self, username: str) -> Dict:
        """Create a new session for authenticated user"""
        import uuid
        
        session_id = str(uuid.uuid4())
        session_token = str(uuid.uuid4())
        
        session_data = {
            'Id': session_id,
            'Name': f'Session for {username}',
            'Description': f'Active session for user {username}',
            'UserName': username,
            'Token': session_token,
            'CreatedTime': time.time(),
            'LastAccessTime': time.time()
        }
        
        self.sessions[session_id] = session_data
        logger.info(f"🎫 Session created for user: {username} (ID: {session_id})")
        
        return {
            'Id': session_id,
            'SessionToken': session_token,
            'Uri': f'/redfish/v1/SessionService/Sessions/{session_id}'
        }
    
    def _validate_session_token(self, token: str) -> Tuple[bool, Optional[str]]:
        """Validate session token"""
        current_time = time.time()
        
        for session_id, session_data in self.sessions.items():
            if session_data.get('Token') == token:
                # Check if session expired
                if current_time - session_data['LastAccessTime'] > self.session_timeout:
                    logger.warning(f"🕐 Session expired for: {session_data['UserName']}")
                    del self.sessions[session_id]
                    return False, None
                
                # Update last access time
                session_data['LastAccessTime'] = current_time
                logger.debug(f"✅ Valid session token for: {session_data['UserName']}")
                return True, session_data['UserName']
        
        logger.warning("❌ Invalid session token")
        return False, None
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        if session_id in self.sessions:
            username = self.sessions[session_id]['UserName']
            del self.sessions[session_id]
            logger.info(f"🗑️ Session deleted for user: {username} (ID: {session_id})")
            return True
        return False
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session data"""
        return self.sessions.get(session_id)
    
    def list_sessions(self) -> Dict:
        """List all active sessions"""
        return {
            '@odata.type': '#SessionCollection.SessionCollection',
            '@odata.id': '/redfish/v1/SessionService/Sessions',
            'Name': 'Session Collection',
            'Description': 'Active Sessions',
            'Members@odata.count': len(self.sessions),
            'Members': [
                {
                    '@odata.id': f'/redfish/v1/SessionService/Sessions/{session_id}'
                }
                for session_id in self.sessions.keys()
            ]
        }
    
    def cleanup_expired_sessions(self):
        """Remove expired sessions"""
        current_time = time.time()
        expired_sessions = []
        
        for session_id, session_data in self.sessions.items():
            if current_time - session_data['LastAccessTime'] > self.session_timeout:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            username = self.sessions[session_id]['UserName']
            del self.sessions[session_id]
            logger.info(f"🧹 Expired session cleaned up for: {username} (ID: {session_id})")
