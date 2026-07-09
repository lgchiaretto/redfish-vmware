#!/usr/bin/env python3
"""
VMware Connection Manager
Handles connection and authentication to VMware vSphere.
"""

import ssl
import logging
import atexit
from pyVim.connect import SmartConnect, Disconnect

logger = logging.getLogger(__name__)


class VMwareConnection:
    """Manages VMware vSphere connections"""
    
    def __init__(self, host, user, password, port=443, disable_ssl=True):
        """
        Initialize VMware connection
        
        Args:
            host: vCenter/ESXi host
            user: Username
            password: Password
            port: Connection port
            disable_ssl: Disable SSL verification
        """
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.disable_ssl_verification = disable_ssl
        self.service_instance = None
        self.content = None
        
        self.connect()
    
    def connect(self):
        """Connect to VMware vSphere"""
        try:
            # Disable SSL verification if requested
            if self.disable_ssl_verification:
                context = ssl._create_unverified_context()
            else:
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
            
            # Connect to vSphere
            self.service_instance = SmartConnect(
                host=self.host,
                user=self.user,
                pwd=self.password,
                port=self.port,
                sslContext=context
            )
            
            if self.service_instance:
                self.content = self.service_instance.RetrieveContent()
                logger.info(f"Successfully connected to {self.host}")
                
                # Register disconnect function (only on first connect)
                if not getattr(self, '_atexit_registered', False):
                    atexit.register(self.disconnect)
                    self._atexit_registered = True
            else:
                raise Exception("Failed to connect to vSphere")
                
        except Exception as e:
            logger.error(f"Error connecting to VMware: {e}")
            raise

    def reconnect(self):
        """Reconnect to VMware vSphere after session expiry"""
        logger.info(f"🔄 Reconnecting to {self.host}...")
        try:
            # Try to cleanly disconnect first
            try:
                if self.service_instance:
                    Disconnect(self.service_instance)
            except Exception:
                pass
            self.service_instance = None
            self.content = None
            
            self.connect()
            logger.info(f"✅ Reconnected successfully to {self.host}")
        except Exception as e:
            logger.error(f"❌ Reconnect failed for {self.host}: {e}")
            raise

    def ensure_authenticated(self):
        """Check session is alive; reconnect if not authenticated."""
        try:
            # A lightweight call to verify the session is still valid
            if self.service_instance:
                self.service_instance.CurrentTime()
        except Exception as e:
            err_str = str(e)
            if 'NotAuthenticated' in err_str or 'not authenticated' in err_str.lower():
                logger.warning(f"⚠️ Session expired for {self.host}, reconnecting...")
                self.reconnect()
            else:
                raise

    def is_connection_alive(self):
        """Check if the connection is alive and responsive."""
        try:
            if not self.service_instance:
                return False
            self.service_instance.CurrentTime()
            return True
        except Exception as e:
            logger.debug(f"Connection check failed for {self.host}: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from VMware vSphere"""
        try:
            if self.service_instance:
                Disconnect(self.service_instance)
                logger.info("Disconnected from VMware")
        except Exception as e:
            logger.error(f"Error disconnecting: {e}")
    
    def is_connected(self):
        """Check if connection is active"""
        return self.service_instance is not None
    
    def get_service_instance(self):
        """Get the service instance"""
        return self.service_instance
    
    def get_content(self):
        """Get the content object"""
        return self.content
