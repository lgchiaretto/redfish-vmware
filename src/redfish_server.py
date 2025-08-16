#!/usr/bin/env python3
"""
VMware Redfish Server - First Version (AI-Generated)

Note: This application is AI-generated and represents the first version 
of a Redfish-to-VMware bridge solution.

Provides Redfish REST API interface for VMware VMs management.
Converts Redfish operations to VMware vSphere API calls.
"""

import json
import logging
import ssl
import socketserver
import sys
import threading
import time
from http.server import HTTPServer

from utils.logging_config import setup_logging
from handlers.http_handler import RedfishRequestHandler
from handlers.redfish_handler import RedfishHandler

# Setup logging first
logger = setup_logging()


class RedfishHTTPServer(HTTPServer):
    """Custom HTTP server with Redfish handler"""
    
    def __init__(self, server_address, RequestHandlerClass, handler):
        super().__init__(server_address, RequestHandlerClass)
        self.handler = handler
        self.allow_reuse_address = True
        
    def server_bind(self):
        """Override to ensure proper socket configuration"""
        super().server_bind()
        self.socket.setsockopt(socketserver.socket.SOL_SOCKET, socketserver.socket.SO_REUSEADDR, 1)


class RedfishServer:
    """Main VMware Redfish Server"""
    
    def __init__(self, config_path):
        self.config_path = config_path
        self.config = self._load_config()
        self.servers = []
        self.running = False
        
        logger.info("🚀 VMware Redfish Server initialized")
        logger.info(f"📋 Configuration loaded from: {config_path}")
        logger.info(f"💻 Managing {len(self.config.get('vms', []))} VMs")
    
    def _load_config(self):
        """Load configuration from file"""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            logger.info(f"✅ Configuration loaded successfully")
            
            # Validate config
            if 'vms' not in config or not config['vms']:
                raise ValueError("No VMs configured")
            
            # Log VM configurations (without passwords)
            for vm in config['vms']:
                logger.info(f"🖥️  VM: {vm['name']} - vCenter: {vm['vcenter_host']} - Port: {vm['redfish_port']}")
            
            return config
            
        except FileNotFoundError:
            logger.error(f"❌ Configuration file not found: {self.config_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON in configuration file: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Error loading configuration: {e}")
            raise
    
    def start(self):
        """Start all Redfish servers"""
        self.running = True
        
        logger.info("🔄 Starting VMware Redfish Server instances...")
        
        # Create a single Redfish handler for all VMs
        vm_configs = self.config.get('vms', [])
        redfish_handler = RedfishHandler(vm_configs, self.config)
        
        # Start a server for each VM
        for vm_config in vm_configs:
            vm_name = vm_config['name']
            port = vm_config.get('redfish_port', 8443)
            disable_ssl = vm_config.get('disable_ssl', False)
            
            try:
                logger.info(f"🚀 Starting Redfish server for {vm_name} on port {port}")
                
                # Create server
                server = RedfishHTTPServer(
                    ('0.0.0.0', port),
                    RedfishRequestHandler,
                    redfish_handler
                )
                
                # Setup SSL if not disabled and certificates exist
                if not disable_ssl:
                    ssl_cert_path = f'/home/lchiaret/git/ipmi-vmware/config/ssl/{vm_name}.crt'
                    ssl_key_path = f'/home/lchiaret/git/ipmi-vmware/config/ssl/{vm_name}.key'
                    
                    try:
                        import os
                        if os.path.exists(ssl_cert_path) and os.path.exists(ssl_key_path):
                            context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
                            context.load_cert_chain(ssl_cert_path, ssl_key_path)
                            server.socket = context.wrap_socket(server.socket, server_side=True)
                            logger.info(f"🔒 HTTPS enabled for {vm_name} with SSL certificates")
                        else:
                            logger.warning(f"⚠️  No SSL certificates found for {vm_name}, running HTTP only")
                            logger.warning(f"   Expected: {ssl_cert_path} and {ssl_key_path}")
                    except Exception as ssl_error:
                        logger.warning(f"⚠️  HTTPS setup failed for {vm_name}, falling back to HTTP: {ssl_error}")
                else:
                    logger.info(f"📄 HTTP mode enabled for {vm_name} (SSL disabled in config)")
                    logger.info(f"💡 Client should connect to: http://bastion.chiaret.to:{port}/redfish/v1/")
                    logger.warning(f"⚠️  HTTPS connections will FAIL - use HTTP only for {vm_name}")
                
                # Start server in thread
                server_thread = threading.Thread(
                    target=server.serve_forever,
                    daemon=True,
                    name=f"RedfishServer-{vm_name}-{port}"
                )
                server_thread.start()
                
                self.servers.append((server, server_thread))
                logger.info(f"✅ Redfish server started for {vm_name} on port {port}")
                
            except Exception as e:
                logger.error(f"❌ Failed to start Redfish server for {vm_name} on port {port}: {e}")
        
        if self.servers:
            logger.info(f"🎯 All Redfish servers started successfully ({len(self.servers)} servers)")
            logger.info("🔍 Enhanced Metal3/Ironic compatibility enabled")
            logger.info("🔄 UpdateService, TaskService, and FirmwareInventory endpoints active")
            
            # Keep main thread alive
            try:
                while self.running:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("🛑 Received shutdown signal")
                self.stop()
        else:
            logger.error("❌ No Redfish servers could be started")
            raise RuntimeError("Failed to start any Redfish servers")
    
    def stop(self):
        """Stop all Redfish servers"""
        self.running = False
        
        logger.info("🛑 Stopping all Redfish servers...")
        
        for server, thread in self.servers:
            try:
                server.shutdown()
                server.server_close()
                logger.info("🛑 Redfish server stopped")
            except Exception as e:
                logger.error(f"Error stopping server: {e}")
        
        self.servers.clear()


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='VMware Redfish Server - Modularized')
    parser.add_argument(
        '--config', 
        default='/home/lchiaret/git/ipmi-vmware/config/config.json',
        help='Configuration file path'
    )
    
    args = parser.parse_args()
    
    logger.info("🚀 Starting VMware Redfish Server (Modularized)")
    logger.info(f"📋 Using config: {args.config}")
    
    try:
        server = RedfishServer(args.config)
        server.start()
    except KeyboardInterrupt:
        logger.info("🛑 Received shutdown signal")
    except Exception as e:
        logger.error(f"❌ Server error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
