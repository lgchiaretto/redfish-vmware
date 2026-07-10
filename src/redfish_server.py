#!/usr/bin/env python3
"""
Enhanced VMware Redfish Server with Comprehensive Debugging

This application provides a Redfish REST API interface for VMware VMs management
with enhanced debugging, performance monitoring, and comprehensive logging.
Converts Redfish operations to VMware vSphere API calls with detailed tracking.
"""

import ipaddress
import json
import logging
import os
import ssl
import socketserver
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import HTTPServer
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.logging_config import setup_logging, log_performance_metric, create_debug_context
from utils.health_monitor import health_monitor
from handlers.http_handler import RedfishRequestHandler, get_request_statistics
from handlers.redfish_handler import RedfishHandler

# Setup enhanced logging first
logger = setup_logging()


class RedfishHTTPServer(HTTPServer):
    """Enhanced HTTP server with Redfish handler and health monitoring"""
    
    def __init__(self, server_address, RequestHandlerClass, handler, ssl_context=None):
        self.ssl_context = ssl_context
        self.handler = handler
        self.allow_reuse_address = True
        self.health_monitor = health_monitor
        super().__init__(server_address, RequestHandlerClass)
        
    def server_bind(self):
        """Override to apply SSL wrapping BEFORE binding and ensure proper socket configuration"""
        if self.ssl_context:
            # Wrap the socket with SSL BEFORE binding — avoids "connection reset by peer"
            self.socket = self.ssl_context.wrap_socket(self.socket, server_side=True)
        self.socket.setsockopt(socketserver.socket.SOL_SOCKET, socketserver.socket.SO_REUSEADDR, 1)
        super().server_bind()
        logger.debug(f"🔧 Server socket configured for {self.server_address}")


class RedfishServer:
    """Enhanced VMware Redfish Server with comprehensive monitoring"""
    
    def __init__(self, config_path):
        self.config_path = config_path
        self.config = self._load_config()
        self.servers = []
        self.running = False
        self.health_monitor = health_monitor
        self.redfish_handler = None
        
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

    def _get_datacenter_folder_refresh_interval_seconds(self, config=None):
        """Return the configured datacenter-folder refresh interval in seconds."""
        config = config or self.config
        interval = config.get('datacenter_folder_refresh_interval_seconds', 300)

        try:
            interval = int(interval)
        except (TypeError, ValueError):
            logger.warning(f"⚠️  Invalid datacenter_folder_refresh_interval_seconds '{interval}', defaulting to 300")
            return 300

        if interval <= 0:
            logger.warning("⚠️  Datacenter folder refresh interval must be positive, defaulting to 300 seconds")
            return 300

        return interval

    def _discover_vms_from_folders(self, config):
        """Discover VMs from configured datacenter folders and merge with manual VMs."""
        return self._sync_discovered_vms_from_folders(config, prune_stale=False)

    def _refresh_discovered_vms_from_folders(self, config):
        """Re-discover VMs from folders and prune stale discovered entries."""
        return self._sync_discovered_vms_from_folders(config, prune_stale=True)

    def _sync_discovered_vms_from_folders(self, config, prune_stale=False):
        """Synchronize discovered VMs from configured datacenter folders with the current config."""
        folder_configs = config.get('datacenter_folders', [])
        if not folder_configs:
            if prune_stale:
                self._prune_stale_discovered_vms(config, set())
            return set()
        
        # Collect manually configured VM names to avoid duplicates
        manual_vm_names = {vm['name'] for vm in config.get('vms', []) if isinstance(vm, dict) and 'name' in vm}
        
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
            return set()
        
        discovered_vm_names = set()
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
                    discovered_vm_names.add(vm_name)
                    
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

        if prune_stale:
            self._prune_stale_discovered_vms(config, discovered_vm_names)

        return discovered_vm_names

    def _prune_stale_discovered_vms(self, config, active_discovered_vm_names):
        """Remove discovered VM entries that are no longer present in the folder discovery set."""
        active_names = set(active_discovered_vm_names or [])
        if 'vms' not in config:
            config['vms'] = []

        pruned_vms = []
        for vm in config.get('vms', []):
            if isinstance(vm, dict) and vm.get('discovered') and vm.get('name') not in active_names:
                logger.info(f"🗑️ Pruning stale discovered VM: {vm.get('name')}")
                continue
            pruned_vms.append(vm)

        config['vms'] = pruned_vms
        return config['vms']
    
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
                self.redfish_handler = redfish_handler
                
                # Start a single server for all VMs (use {ID} in URI to select VM)
                self._start_single_server(vm_configs, redfish_handler)

                if self.servers:
                    logger.info(f"🎯 Redfish server started successfully on port {self.servers[0][3]}")
                    logger.info("🔍 Enhanced Metal3/Ironic compatibility enabled")
                    logger.info("🔄 UpdateService, TaskService, and FirmwareInventory endpoints active")
                    logger.info("📊 Health monitoring available at /redfish/v1/health")
                    
                    # Start health reporting thread
                    self._start_health_reporter()
                    self._start_folder_refresh_monitor()
                    
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
    
    def _generate_self_signed_cert(self, cert_path, key_path):
        """Generate a self-signed SSL certificate and private key"""
        try:
            cert_dir = os.path.dirname(cert_path)
            if cert_dir and not os.path.exists(cert_dir):
                os.makedirs(cert_dir, mode=0o755)
                logger.debug(f"📁 Created certificate directory: {cert_dir}")

            logger.debug("🔧 Generating RSA private key (2048 bits)...")
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend()
            )

            logger.debug("🔧 Generating self-signed certificate...")
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "CA"),
                x509.NameAttribute(NameOID.LOCALITY_NAME, "San Jose"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "RedFish VMware Bridge"),
                x509.NameAttribute(NameOID.COMMON_NAME, "redfish-vmware-server"),
            ])

            cert = x509.CertificateBuilder().subject_name(
                subject
            ).issuer_name(
                issuer
            ).public_key(
                private_key.public_key()
            ).serial_number(
                x509.random_serial_number()
            ).not_valid_before(
                datetime.now(timezone.utc)
            ).not_valid_after(
                datetime.now(timezone.utc) + timedelta(days=365)
            ).add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName("localhost"),
                    x509.DNSName("*.chiaret.to"),
                    x509.DNSName("bastion.chiaret.to"),
                    x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                ]),
                critical=False,
            ).sign(private_key, hashes.SHA256(), default_backend())

            logger.debug(f"💾 Writing private key to: {key_path}")
            with open(key_path, "wb") as f:
                f.write(private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption()
                ))
            os.chmod(key_path, 0o600)

            logger.debug(f"💾 Writing certificate to: {cert_path}")
            with open(cert_path, "wb") as f:
                f.write(cert.public_bytes(serialization.Encoding.PEM))
            os.chmod(cert_path, 0o644)

            logger.info(f"✅ Self-signed SSL certificate generated successfully")
            logger.info(f"   cert: {cert_path}")
            logger.info(f"   key:  {key_path}")
            logger.info(f"   validity: 365 days")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to generate self-signed certificate: {e}")
            return False

    def _setup_ssl(self, vm_name, port):
        """Setup SSL — generating a self-signed cert if no certificates exist. Returns SSLContext or None."""
        ssl_config = self.config.get('ssl', {})
        ssl_cert_path = ssl_config.get('cert_path')
        ssl_key_path = ssl_config.get('key_path')

        if not ssl_cert_path or not ssl_key_path:
            default_cert_dir = "/etc/redfish-vmware/ssl"
            ssl_cert_path = os.path.join(default_cert_dir, "server.crt")
            ssl_key_path = os.path.join(default_cert_dir, "server.key")
            logger.info(f"⚙️  No SSL paths configured, will use self-signed certificates")

        if not os.path.exists(ssl_cert_path) or not os.path.exists(ssl_key_path):
            logger.info(f"📝 SSL certificates not found, generating self-signed certificate...")
            if not self._generate_self_signed_cert(ssl_cert_path, ssl_key_path):
                logger.warning(f"⚠️  Failed to generate self-signed certificate, falling back to HTTP")
                return None

        try:
            logger.debug(f"🔐 Creating SSL context and loading certificates")
            context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            context.load_cert_chain(ssl_cert_path, ssl_key_path)
            logger.info(f"🔒 HTTPS enabled for {vm_name} on port {port}")
            logger.info(f"   cert: {ssl_cert_path}")
            return context
        except Exception as ssl_error:
            logger.warning(f"⚠️  HTTPS setup failed for {vm_name}, falling back to HTTP: {ssl_error}")
            return None
    
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

    def _start_folder_refresh_monitor(self):
        """Start a background thread that periodically refreshes discovered VMs from datacenter folders."""
        if not self.config.get('datacenter_folders'):
            return

        refresh_interval = self._get_datacenter_folder_refresh_interval_seconds()

        def folder_refresh_loop():
            while self.running:
                try:
                    time.sleep(refresh_interval)
                    if self.running:
                        logger.info("🔄 Refreshing discovered VMs from datacenter folders")
                        self._refresh_discovered_vms_from_folders(self.config)
                        if self.redfish_handler:
                            self.redfish_handler.refresh_vm_configs(self.config.get('vms', []), self.config)
                except Exception as e:
                    logger.warning(f"⚠️  Datacenter folder refresh error: {e}")

        refresh_thread = threading.Thread(target=folder_refresh_loop, daemon=True, name="FolderRefreshMonitor")
        refresh_thread.start()
        logger.info(f"📅 Datacenter folder refresh monitor started (interval {refresh_interval}s)")
    
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

            # Build SSL context before creating the server so the socket is
            # wrapped BEFORE binding (prevents "connection reset by peer")
            ssl_context = None
            if not disable_ssl:
                ssl_context = self._setup_ssl('redfish-server', port)
                if ssl_context is None:
                    logger.info(f"📄 SSL setup failed, falling back to HTTP mode")
            else:
                logger.info(f"📄 HTTP mode enabled for server (SSL disabled)")
                logger.info(f"💡 Client should connect to: http://bastion.chiaret.to:{port}/redfish/v1/")

            server = RedfishHTTPServer(
                ('0.0.0.0', port),
                RedfishRequestHandler,
                redfish_handler,
                ssl_context=ssl_context
            )

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
