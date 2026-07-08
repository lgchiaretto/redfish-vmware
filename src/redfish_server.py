#!/usr/bin/env python3
"""
Enhanced VMware Redfish Server with Comprehensive Debugging

This application provides a Redfish REST API interface for VMware VMs management
with enhanced debugging, performance monitoring, and comprehensive logging.
Converts Redfish operations to VMware vSphere API calls with detailed tracking.
"""

import json
import logging
import os
import ssl
import socketserver
import sys
import threading
import time
from http.server import HTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
            effective_port = self._get_effective_server_port(vm_config=vm)
            logger.info(f"🖥️  VM: {vm['name']} - vCenter: {vm['vcenter_host']} - Port: {effective_port}")
    
    def _load_config(self):
        """Load and validate configuration with enhanced error reporting"""
        try:
            with create_debug_context()('Configuration Loading'):
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                
                logger.info(f"✅ Configuration file loaded successfully")
                
                # Enhanced validation
                self._validate_config(config)
                
                # Discover and merge VMs from datacenter folders (if configured)
                self._discover_vms_from_folders(config)
                
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
        # Allow either 'vms' or 'datacenter_folders' (or both)
        has_vms = 'vms' in config and config['vms']
        has_folders = 'datacenter_folders' in config and config['datacenter_folders']
        
        if not has_vms and not has_folders:
            raise ValueError("Configuration must contain either 'vms' section or 'datacenter_folders' section")
        
        required_vm_fields = ['name', 'vcenter_host', 'vcenter_user', 'vcenter_password']
        
        # Validate manually configured VMs
        if has_vms:
            for i, vm in enumerate(config['vms']):
                for field in required_vm_fields:
                    if field not in vm:
                        raise ValueError(f"VM {i+1}: Missing required field '{field}'")
        
        # Validate datacenter_folders configuration
        if has_folders:
            for i, folder_config in enumerate(config['datacenter_folders']):
                if 'datacenter' not in folder_config:
                    raise ValueError(f"Datacenter folder {i+1}: Missing 'datacenter' field")
                if 'folder_path' not in folder_config:
                    raise ValueError(f"Datacenter folder {i+1}: Missing 'folder_path' field")
        
        # Top-level server port may be provided instead of per-VM ports
        server_port = self._get_effective_server_port(config=config)
        if server_port is not None:
            if not isinstance(server_port, int) or server_port < 1024 or server_port > 65535:
                raise ValueError(f"Invalid redfish_port {server_port} (must be 1024-65535)")
        
        logger.info(f"✅ Configuration validation passed")
    
    def _get_effective_server_port(self, config=None, vm_config=None):
        """Return the effective Redfish server port from env, config, or VM config."""
        config = config or self.config

        env_port = os.getenv('REDFISH_PORT')
        if env_port is not None:
            try:
                return int(env_port)
            except ValueError:
                logger.warning(f"⚠️  Invalid REDFISH_PORT value '{env_port}', ignoring it")

        if config and config.get('redfish_port') is not None:
            return config.get('redfish_port')

        if vm_config and vm_config.get('redfish_port') is not None:
            return vm_config.get('redfish_port')

        return 8443

    def _get_effective_redfish_port(self, config=None, vm_config=None):
        """Backward-compatible alias for effective port lookup."""
        return self._get_effective_server_port(config=config, vm_config=vm_config)

    def _discover_vms_from_folders(self, config):
        """Discover VMs from configured datacenter folders and merge with manual VMs"""
        folder_configs = config.get('datacenter_folders', [])
        if not folder_configs:
            return
        
        # Collect manually configured VM names to avoid duplicates
        manual_vm_names = {vm['name'] for vm in config.get('vms', [])}
        
        # Initialize if needed
        if 'vms' not in config:
            config['vms'] = []
        
        # Get VMware credentials from the first manually configured VM or global config
        vmware_config = config.get('vmware', {})
        vmware_host = vmware_config.get('host')
        vmware_user = vmware_config.get('user')
        vmware_password = vmware_config.get('password')
        vmware_port = vmware_config.get('port', 443)
        disable_ssl_vmware = vmware_config.get('disable_ssl', True)
        
        # If no global config, use first VM's credentials
        if not vmware_host and config['vms']:
            first_vm = config['vms'][0]
            vmware_host = first_vm.get('vcenter_host')
            vmware_user = first_vm.get('vcenter_user')
            vmware_password = first_vm.get('vcenter_password')
        
        if not vmware_host or not vmware_user or not vmware_password:
            logger.warning("⚠️  Cannot auto-discover VMs from folders: VMware credentials not available")
            return
        
        discovered_count = 0
        
        for folder_config in folder_configs:
            datacenter = folder_config['datacenter']
            folder_path = folder_config['folder_path']
            
            try:
                logger.info(f"🔍 Discovering VMs in {datacenter}/{folder_path}...")
                
                # Import here to avoid circular dependencies
                from vmware.connection import VMwareConnection
                from vmware.vm_operations import VMOperations
                
                # Create temporary connection for discovery
                connection = VMwareConnection(
                    vmware_host, 
                    vmware_user, 
                    vmware_password,
                    vmware_port,
                    disable_ssl_vmware
                )
                
                vm_ops = VMOperations(connection)
                discovered_vms = vm_ops.list_vms_in_folder(datacenter, folder_path)
                
                connection.disconnect()
                
                # Add discovered VMs to config (avoid duplicates)
                for vm_info in discovered_vms:
                    vm_name = vm_info['name']
                    
                    if vm_name in manual_vm_names:
                        logger.debug(f"  ℹ️  VM '{vm_name}' already manually configured, skipping")
                        continue
                    
                    # Create VM configuration entry
                    vm_config = {
                        'name': vm_name,
                        'vcenter_host': vmware_host,
                        'vcenter_user': vmware_user,
                        'vcenter_password': vmware_password,
                        'redfish_user': 'admin',  # Default credentials
                        'redfish_password': 'password',
                        'discovered': True,
                        'discovered_from': f"{datacenter}/{folder_path}"
                    }
                    
                    config['vms'].append(vm_config)
                    manual_vm_names.add(vm_name)
                    discovered_count += 1
                    logger.info(f"  ✅ Added discovered VM: {vm_name}")
                
                logger.info(f"📊 Discovered {discovered_count} new VMs from {datacenter}/{folder_path}")
                
            except Exception as e:
                logger.error(f"❌ Failed to discover VMs in {datacenter}/{folder_path}: {e}")
                logger.debug(f"📍 Discovery error details:", exc_info=True)
    
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
                
                # Start a single server for all VMs (use {ID} in URI to select VM)
                self._start_single_server(vm_configs, redfish_handler)

                if self.servers:
                    logger.info(f"🎯 Redfish server started successfully on port {self.servers[0][3]}")
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
        """(deprecated) Per-VM server startup is no longer used."""
        logger.warning("_start_vm_server called but per-VM servers are deprecated")
    
    def _setup_ssl(self, server, vm_name, port):
        """Setup SSL configuration for a server"""
        ssl_config = self.config.get('ssl', {})
        ssl_cert_path = ssl_config.get('cert_path')
        ssl_key_path = ssl_config.get('key_path')
        
        if not ssl_cert_path or not ssl_key_path:
            logger.warning(f"⚠️  SSL cert_path/key_path not defined in config, running HTTP only for {vm_name}")
            logger.warning(f"💡 Add 'ssl' section with 'cert_path' and 'key_path' to config.json to enable HTTPS")
            return
        
        try:
            if os.path.exists(ssl_cert_path) and os.path.exists(ssl_key_path):
                context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
                context.load_cert_chain(ssl_cert_path, ssl_key_path)
                server.socket = context.wrap_socket(server.socket, server_side=True)
                logger.info(f"🔒 HTTPS enabled for {vm_name} using certificates from config")
                logger.info(f"   cert: {ssl_cert_path}")
            else:
                logger.warning(f"⚠️  SSL certificates not found, running HTTP only for {vm_name}")
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
            for server_info in self.servers:
                try:
                    server, thread, name, port = server_info
                    logger.info(f"🛑 Stopping server on port {port}")
                    server.shutdown()
                    server.server_close()
                    logger.info(f"✅ Server stopped on port {port}")
                except Exception as e:
                    logger.error(f"❌ Error stopping server: {e}")
            
            # Log final statistics
            final_stats = self.health_monitor.get_health_stats()
            logger.info(f"📊 Final Statistics:")
            logger.info(f"   Total Uptime: {final_stats['uptime_human']}")
            logger.info(f"   Total Operations: {final_stats['total_operations']}")
            logger.info(f"   Success Rate: {final_stats['success_rate']:.1f}%")
            
            self.servers.clear()
            logger.info("✅ All servers stopped successfully")

    def _start_single_server(self, vm_configs, redfish_handler):
        """Start a single HTTP(S) server that handles all VMs based on the {ID} in the URI"""
        # Determine server port
        port = self._get_effective_server_port(vm_config=vm_configs[0] if vm_configs else None)

        # Determine SSL setting: prefer top-level, else derive from VM configs
        if 'disable_ssl' in self.config:
            disable_ssl = self.config.get('disable_ssl', True)
        else:
            vm_ssl_set = {bool(vm.get('disable_ssl', False)) for vm in vm_configs}
            if len(vm_ssl_set) > 1:
                logger.warning("🔀 Conflicting per-VM 'disable_ssl' values; defaulting to HTTP (disable_ssl=True)")
                disable_ssl = True
            else:
                disable_ssl = vm_ssl_set.pop() if vm_ssl_set else True

        try:
            logger.info(f"🚀 Starting single Redfish server on port {port} (SSL disabled={disable_ssl})")

            server = RedfishHTTPServer(
                ('0.0.0.0', port),
                RedfishRequestHandler,
                redfish_handler
            )

            if not disable_ssl:
                # Use a generic server name for SSL messages
                self._setup_ssl(server, 'redfish-server', port)
            else:
                logger.info(f"📄 HTTP mode enabled for server (SSL disabled)")
                logger.info(f"💡 Client should connect to: http://bastion.chiaret.to:{port}/redfish/v1/")

            server_thread = threading.Thread(
                target=server.serve_forever,
                daemon=True,
                name=f"RedfishServer-main-{port}"
            )
            server_thread.start()

            # Store tuple: (server, thread, name, port)
            self.servers.append((server, server_thread, 'redfish-server', port))
            logger.info(f"✅ Single Redfish server started on port {port}")

        except Exception as e:
            logger.error(f"❌ Failed to start single Redfish server on port {port}: {e}")
            logger.debug(f"📍 Server startup error:", exc_info=True)
    
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
