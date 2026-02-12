#!/usr/bin/env python3
"""
Enhanced VMware Redfish Server with Comprehensive Debugging

This application provides a Redfish REST API interface for VMware VMs management
with enhanced debugging, performance monitoring, and comprehensive logging.
Converts Redfish operations to VMware vSphere API calls with detailed tracking.
"""

import json
import logging
import ssl
import socketserver
import sys
import threading
import time
from http.server import HTTPServer

from utils.logging_config import setup_logging, log_performance_metric, create_debug_context
from handlers.http_handler import RedfishRequestHandler, get_request_statistics
from handlers.redfish_handler import RedfishHandler

# Setup enhanced logging first
logger = setup_logging()


class ServerHealthMonitor:
    """Monitor server health and performance metrics"""
    
    def __init__(self):
        self.start_time = time.time()
        self.vm_stats = {}
        self.error_count = 0
        self.lock = threading.Lock()
    
    def record_vm_operation(self, vm_name, operation, success=True, duration=0):
        """Record VM operation statistics"""
        with self.lock:
            if vm_name not in self.vm_stats:
                self.vm_stats[vm_name] = {
                    'total_operations': 0,
                    'successful_operations': 0,
                    'failed_operations': 0,
                    'average_response_time': 0,
                    'last_operation': None,
                    'last_operation_time': None
                }
            
            stats = self.vm_stats[vm_name]
            stats['total_operations'] += 1
            stats['last_operation'] = operation
            stats['last_operation_time'] = time.time()
            
            if success:
                stats['successful_operations'] += 1
            else:
                stats['failed_operations'] += 1
                self.error_count += 1
            
            # Update average response time
            if stats['average_response_time'] == 0:
                stats['average_response_time'] = duration
            else:
                stats['average_response_time'] = (stats['average_response_time'] + duration) / 2
    
    def get_health_stats(self):
        """Get comprehensive health statistics"""
        with self.lock:
            uptime = time.time() - self.start_time
            total_operations = sum(vm['total_operations'] for vm in self.vm_stats.values())
            total_successful = sum(vm['successful_operations'] for vm in self.vm_stats.values())
            
            return {
                'uptime_seconds': uptime,
                'uptime_human': self._format_uptime(uptime),
                'total_operations': total_operations,
                'successful_operations': total_successful,
                'failed_operations': self.error_count,
                'success_rate': (total_successful / total_operations * 100) if total_operations > 0 else 0,
                'operations_per_minute': (total_operations / uptime) * 60 if uptime > 0 else 0,
                'vm_statistics': self.vm_stats.copy(),
                'request_statistics': get_request_statistics()
            }
    
    def _format_uptime(self, seconds):
        """Format uptime in human readable format"""
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"


# Global health monitor
health_monitor = ServerHealthMonitor()


class RedfishHTTPServer(HTTPServer):
    """Enhanced HTTP server with Redfish handler and health monitoring"""
    
    def __init__(self, server_address, RequestHandlerClass, handler):
        super().__init__(server_address, RequestHandlerClass)
        self.handler = handler
        self.allow_reuse_address = True
        self.health_monitor = health_monitor
        
    def server_bind(self):
        """Override to ensure proper socket configuration"""
        super().server_bind()
        self.socket.setsockopt(socketserver.socket.SOL_SOCKET, socketserver.socket.SO_REUSEADDR, 1)
        logger.debug(f"🔧 Server socket configured for {self.server_address}")


class RedfishServer:
    """Enhanced VMware Redfish Server with comprehensive monitoring"""
    
    def __init__(self, config_path):
        self.config_path = config_path
        self.config = self._load_config()
        self.servers = []
        self.running = False
        self.health_monitor = health_monitor
        
        logger.info("🚀 Enhanced VMware Redfish Server initialized")
        logger.info(f"📋 Configuration loaded from: {config_path}")
        logger.info(f"💻 Managing {len(self.config.get('vms', []))} VMs")
        logger.info(f"📊 Health monitoring enabled")
        
        # Log VM configurations (without sensitive data)
        for vm in self.config.get('vms', []):
            logger.info(f"🖥️  VM: {vm['name']} - vCenter: {vm['vcenter_host']} - Port: {vm['redfish_port']}")
    
    def _load_config(self):
        """Load and validate configuration with enhanced error reporting"""
        try:
            with create_debug_context()('Configuration Loading'):
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                
                logger.info(f"✅ Configuration file loaded successfully")
                
                # Enhanced validation
                self._validate_config(config)
                
                return config
                
        except FileNotFoundError:
            logger.error(f"❌ Configuration file not found: {self.config_path}")
            logger.error(f"💡 Ensure the config file exists and is readable")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON in configuration file: {e}")
            logger.error(f"💡 Check JSON syntax in {self.config_path}")
            raise
        except Exception as e:
            logger.error(f"❌ Error loading configuration: {e}")
            logger.debug(f"📍 Configuration loading error:", exc_info=True)
            raise
    
    def _validate_config(self, config):
        """Enhanced configuration validation"""
        if 'vms' not in config or not config['vms']:
            raise ValueError("No VMs configured - 'vms' section is required")
        
        required_vm_fields = ['name', 'vcenter_host', 'vcenter_user', 'vcenter_password', 'redfish_port']
        
        for i, vm in enumerate(config['vms']):
            for field in required_vm_fields:
                if field not in vm:
                    raise ValueError(f"VM {i+1}: Missing required field '{field}'")
            
            # Validate port ranges
            port = vm.get('redfish_port')
            if not isinstance(port, int) or port < 1024 or port > 65535:
                raise ValueError(f"VM {vm['name']}: Invalid port {port} (must be 1024-65535)")
        
        logger.info(f"✅ Configuration validation passed for {len(config['vms'])} VMs")
    
    def start(self):
        """Start all Redfish servers with enhanced monitoring"""
        self.running = True
        
        logger.info("🔄 Starting Enhanced VMware Redfish Server instances...")
        logger.info(f"📊 Performance monitoring and health tracking enabled")
        
        try:
            with create_debug_context()('Server Startup'):
                # Create a single Redfish handler for all VMs
                vm_configs = self.config.get('vms', [])
                redfish_handler = RedfishHandler(vm_configs, self.config)
                
                # Start a server for each VM
                for vm_config in vm_configs:
                    self._start_vm_server(vm_config, redfish_handler)
                
                if self.servers:
                    logger.info(f"🎯 All Redfish servers started successfully ({len(self.servers)} servers)")
                    logger.info("🔍 Enhanced Metal3/Ironic compatibility enabled")
                    logger.info("🔄 UpdateService, TaskService, and FirmwareInventory endpoints active")
                    logger.info("📊 Health monitoring available at /redfish/v1/health")
                    
                    # Start health reporting thread
                    self._start_health_reporter()
                    
                    # Keep main thread alive
                    self._main_loop()
                else:
                    logger.error("❌ No Redfish servers could be started")
                    raise RuntimeError("Failed to start any Redfish servers")
                    
        except Exception as e:
            logger.error(f"❌ Failed to start servers: {e}")
            logger.debug(f"📍 Startup error details:", exc_info=True)
            self.stop()
            raise
    
    def _start_vm_server(self, vm_config, redfish_handler):
        """Start a server for a specific VM with enhanced error handling"""
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
            
            # Setup SSL if not disabled
            if not disable_ssl:
                self._setup_ssl(server, vm_name, port)
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
            
            self.servers.append((server, server_thread, vm_name, port))
            logger.info(f"✅ Redfish server started for {vm_name} on port {port}")
            
        except Exception as e:
            logger.error(f"❌ Failed to start Redfish server for {vm_name} on port {port}: {e}")
            logger.debug(f"📍 Server startup error for {vm_name}:", exc_info=True)
    
    def _setup_ssl(self, server, vm_name, port):
        """Setup SSL configuration for a server"""
        ssl_config = self.config.get('ssl', {})
        ssl_cert_path = ssl_config.get('cert_path', '/etc/letsencrypt/live/bastion.chiaret.to/fullchain.pem')
        ssl_key_path = ssl_config.get('key_path', '/etc/letsencrypt/live/bastion.chiaret.to/privkey.pem')
        
        try:
            import os
            if os.path.exists(ssl_cert_path) and os.path.exists(ssl_key_path):
                context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
                context.load_cert_chain(ssl_cert_path, ssl_key_path)
                server.socket = context.wrap_socket(server.socket, server_side=True)
                logger.info(f"🔒 HTTPS enabled for {vm_name} with Let's Encrypt certificates")
                logger.info(f"💡 Client should connect to: https://bastion.chiaret.to:{port}/redfish/v1/")
            else:
                logger.warning(f"⚠️  Let's Encrypt certificates not found, running HTTP only")
                logger.warning(f"   Expected: {ssl_cert_path} and {ssl_key_path}")
        except Exception as ssl_error:
            logger.warning(f"⚠️  HTTPS setup failed for {vm_name}, falling back to HTTP: {ssl_error}")
    
    def _start_health_reporter(self):
        """Start background thread for periodic health reporting"""
        def health_reporter():
            while self.running:
                try:
                    time.sleep(300)  # Report every 5 minutes
                    if self.running:
                        stats = self.health_monitor.get_health_stats()
                        logger.info(f"📊 Health Report - Uptime: {stats['uptime_human']}, "
                                  f"Operations: {stats['total_operations']}, "
                                  f"Success Rate: {stats['success_rate']:.1f}%")
                except Exception as e:
                    logger.debug(f"🔧 Health reporter error: {e}")
        
        health_thread = threading.Thread(target=health_reporter, daemon=True, name="HealthReporter")
        health_thread.start()
        logger.info("📊 Health reporter started (5-minute intervals)")
    
    def _main_loop(self):
        """Main server loop with enhanced signal handling"""
        try:
            logger.info("✅ Redfish VMware Server is running")
            logger.info("💡 Press Ctrl+C to stop the server")
            
            while self.running:
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("🛑 Received shutdown signal (Ctrl+C)")
            self.stop()
        except Exception as e:
            logger.error(f"❌ Main loop error: {e}")
            logger.debug(f"📍 Main loop error details:", exc_info=True)
            self.stop()
    
    def stop(self):
        """Stop all Redfish servers with enhanced cleanup"""
        logger.info("🛑 Stopping Enhanced Redfish VMware Server...")
        self.running = False
        
        with create_debug_context()('Server Shutdown'):
            for server, thread, vm_name, port in self.servers:
                try:
                    logger.info(f"🛑 Stopping server for {vm_name} on port {port}")
                    server.shutdown()
                    server.server_close()
                    logger.info(f"✅ Server stopped for {vm_name}")
                except Exception as e:
                    logger.error(f"❌ Error stopping server for {vm_name}: {e}")
            
            # Log final statistics
            final_stats = self.health_monitor.get_health_stats()
            logger.info(f"📊 Final Statistics:")
            logger.info(f"   Total Uptime: {final_stats['uptime_human']}")
            logger.info(f"   Total Operations: {final_stats['total_operations']}")
            logger.info(f"   Success Rate: {final_stats['success_rate']:.1f}%")
            
            self.servers.clear()
            logger.info("✅ All servers stopped successfully")
    
    def get_server_health(self):
        """Get current server health statistics"""
        return self.health_monitor.get_health_stats()


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='VMware Redfish Server - Modularized')
    parser.add_argument(
        '--config', 
        default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', 'config.json'),
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
