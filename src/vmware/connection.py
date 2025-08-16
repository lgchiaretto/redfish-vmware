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
                
                # Register disconnect function
                atexit.register(self.disconnect)
            else:
                raise Exception("Failed to connect to vSphere")
                
        except Exception as e:
            logger.error(f"Error connecting to VMware: {e}")
            raise
    
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
