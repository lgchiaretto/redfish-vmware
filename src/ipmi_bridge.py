#!/usr/bin/env python3
"""
VMware IPMI Bridge Service
Provides IPMI interface for VMware VMs using pyghmi FakeBmc as base.
"""

import json
import logging
import threading
import time
import sys
import os

# Add the current directory to the path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pyghmi.ipmi.bmc as bmc
from vmware_client import VMwareClient

# Configure logging with DEBUG level for detailed OpenShift communication tracking
debug_enabled = os.getenv('IPMI_DEBUG', 'true').lower() == 'true'
log_level = logging.DEBUG if debug_enabled else logging.INFO

# Setup log file path - try multiple locations
log_paths = [
    '/var/log/ipmi-vmware-bridge.log',  # System log (requires root)
    os.path.expanduser('~/ipmi-vmware-bridge.log'),  # User home
    './ipmi-vmware-bridge.log'  # Current directory
]

log_file = None
for path in log_paths:
    try:
        # Test if we can write to this location
        with open(path, 'a') as f:
            pass
        log_file = path
        break
    except (PermissionError, FileNotFoundError):
        continue

handlers = [logging.StreamHandler()]
if log_file:
    handlers.append(logging.FileHandler(log_file))

logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=handlers
)

# Set pyghmi to DEBUG to see all IPMI protocol details
logging.getLogger('pyghmi').setLevel(logging.DEBUG if debug_enabled else logging.WARNING)
logging.getLogger('pyghmi.ipmi.bmc').setLevel(logging.DEBUG if debug_enabled else logging.WARNING)

logger = logging.getLogger(__name__)

if log_file:
    logger.info(f"📝 Logging to: {log_file}")

if debug_enabled:
    logger.info("🐛 DEBUG MODE ENABLED - All IPMI calls from OpenShift will be logged in detail")
else:
    logger.info("📋 PRODUCTION MODE - Limited logging enabled")

class VMwareBMC(bmc.Bmc):
    """VMware BMC implementation based on pyghmi Bmc with enhanced debugging"""
    
    def __init__(self, authdata, port, vm_config):
        super(VMwareBMC, self).__init__(authdata, port)
        self.vm_config = vm_config
        self.vm_name = vm_config['name']
        self.powerstate = 'unknown'
        self.bootdevice = 'default'
        
        # Set up BMC-specific logger
        self.logger = logging.getLogger(f"BMC-{self.vm_name}")
        self.logger.info(f"🚀 Initializing BMC for VM: {self.vm_name} on port {port}")
        
        # Log authentication data (without passwords)
        auth_users = list(authdata.keys())
        self.logger.debug(f"🔐 IPMI Auth Users: {auth_users}")
        
        # Initialize VMware client
        try:
            self.vmware_client = VMwareClient(
                vm_config['vcenter_host'],
                vm_config['vcenter_user'], 
                vm_config['vcenter_password']
            )
            self.logger.info(f"✅ VMware client initialized for VM: {self.vm_name}")
            
            # Get initial power state
            self._update_power_state()
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize VMware client for {self.vm_name}: {e}")
            self.vmware_client = None

    def _update_power_state(self):
        """Update power state from VMware"""
        if not self.vmware_client:
            return
            
        try:
            is_powered_on = self.vmware_client.is_vm_powered_on(self.vm_name)
            old_state = self.powerstate
            self.powerstate = 'on' if is_powered_on else 'off'
            if old_state != self.powerstate:
                self.logger.info(f"🔄 VM {self.vm_name} power state changed: {old_state} → {self.powerstate}")
            else:
                self.logger.debug(f"📊 VM {self.vm_name} power state: {self.powerstate}")
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to get power state for {self.vm_name}: {e}")

    # Override BMC methods to add detailed logging for OpenShift communication
    def handle_raw_request(self, request, sockaddr):
        """Override to log all incoming IPMI requests from OpenShift"""
        client_info = f"{sockaddr[0]}:{sockaddr[1]}" if sockaddr else "unknown"
        self.logger.debug(f"📨 IPMI RAW REQUEST from {client_info} to VM {self.vm_name}")
        self.logger.debug(f"🔍 Raw Request Data: {request.hex() if hasattr(request, 'hex') else str(request)}")
        
        try:
            response = super().handle_raw_request(request, sockaddr)
            self.logger.debug(f"📤 IPMI RAW RESPONSE to {client_info}: {response.hex() if hasattr(response, 'hex') else str(response)}")
            return response
        except Exception as e:
            self.logger.error(f"❌ Error handling raw request from {client_info}: {e}")
            raise

    def handle_request(self, request, sockaddr):
        """Override to log structured IPMI requests"""
        client_info = f"{sockaddr[0]}:{sockaddr[1]}" if sockaddr else "unknown"
        self.logger.info(f"🎯 IPMI REQUEST from OpenShift/BMH at {client_info} → VM {self.vm_name}")
        
        # Log request details if available
        if hasattr(request, 'command'):
            self.logger.info(f"📋 Command: {request.command}")
        if hasattr(request, 'netfn'):
            self.logger.info(f"📋 NetFN: {request.netfn}")
        if hasattr(request, 'data'):
            self.logger.debug(f"📋 Data: {request.data}")
            
        try:
            response = super().handle_request(request, sockaddr)
            self.logger.debug(f"✅ Request handled successfully for {client_info}")
            return response
        except Exception as e:
            self.logger.error(f"❌ Error handling request from {client_info}: {e}")
            raise

    def get_power_state(self):
        """Get current power state - required by pyghmi BMC"""
        self.logger.debug(f"🔍 OpenShift requesting power state for VM {self.vm_name}")
        self._update_power_state()
        self.logger.info(f"📊 Reporting power state to OpenShift: VM {self.vm_name} is {self.powerstate}")
        return self.powerstate  # Should return 'on' or 'off' as string

    def power_off(self):
        """Power off the VM"""
        self.logger.info(f"🔴 OpenShift requesting POWER OFF for VM: {self.vm_name}")
        
        if not self.vmware_client:
            self.logger.error(f"❌ No VMware client available for {self.vm_name}")
            return
            
        try:
            self.logger.info(f"⚡ Executing VMware power off for VM: {self.vm_name}")
            success = self.vmware_client.power_off_vm(self.vm_name)
            if success:
                self.powerstate = 'off'
                self.logger.info(f"✅ VM {self.vm_name} powered off successfully - OpenShift notified")
            else:
                self.logger.error(f"❌ Failed to power off VM {self.vm_name} - OpenShift will see error")
        except Exception as e:
            self.logger.error(f"💥 Error powering off VM {self.vm_name}: {e}")

    def power_on(self):
        """Power on the VM"""
        self.logger.info(f"🟢 OpenShift requesting POWER ON for VM: {self.vm_name}")
        
        if not self.vmware_client:
            self.logger.error(f"❌ No VMware client available for {self.vm_name}")
            return
            
        try:
            self.logger.info(f"⚡ Executing VMware power on for VM: {self.vm_name}")
            success = self.vmware_client.power_on_vm(self.vm_name)
            if success:
                self.powerstate = 'on'
                self.logger.info(f"✅ VM {self.vm_name} powered on successfully - OpenShift notified")
            else:
                self.logger.error(f"❌ Failed to power on VM {self.vm_name} - OpenShift will see error")
        except Exception as e:
            self.logger.error(f"💥 Error powering on VM {self.vm_name}: {e}")

    def power_reset(self):
        """Reset the VM"""
        self.logger.info(f"🔄 OpenShift requesting RESET for VM: {self.vm_name}")
        
        if not self.vmware_client:
            self.logger.error(f"❌ No VMware client available for {self.vm_name}")
            return
            
        try:
            self.logger.info(f"⚡ Executing VMware reset for VM: {self.vm_name}")
            success = self.vmware_client.reset_vm(self.vm_name)
            if success:
                self.powerstate = 'on'  # Reset leaves VM in powered on state
                self.logger.info(f"✅ VM {self.vm_name} reset successfully - OpenShift notified")
            else:
                self.logger.error(f"❌ Failed to reset VM {self.vm_name} - OpenShift will see error")
        except Exception as e:
            self.logger.error(f"💥 Error resetting VM {self.vm_name}: {e}")

    def power_shutdown(self):
        """Gracefully shutdown the VM"""
        if not self.vmware_client:
            logger.error(f"No VMware client available for {self.vm_name}")
            return
            
        try:
            logger.info(f"Gracefully shutting down VM: {self.vm_name}")
            success = self.vmware_client.power_off_vm(self.vm_name, force=False)
            if success:
                # Wait a bit for shutdown to complete
                time.sleep(5)
                self._update_power_state()
                logger.info(f"VM {self.vm_name} shutdown initiated")
            else:
                logger.error(f"Failed to shutdown VM {self.vm_name}")
        except Exception as e:
            logger.error(f"Error shutting down VM {self.vm_name}: {e}")

    def get_boot_device(self):
        """Get boot device"""
        self.logger.debug(f"🔍 OpenShift requesting boot device for VM {self.vm_name}")
        self.logger.info(f"📋 Reporting boot device to OpenShift: VM {self.vm_name} → {self.bootdevice}")
        return self.bootdevice

    def set_boot_device(self, bootdevice):
        """Set boot device"""
        self.logger.info(f"💾 OpenShift requesting boot device change for VM {self.vm_name}: {self.bootdevice} → {bootdevice}")
        
        if not self.vmware_client:
            self.logger.error(f"❌ No VMware client available for {self.vm_name}")
            return
            
        try:
            # Map IPMI boot devices to VMware boot devices
            device_map = {
                'network': 'network',
                'hd': 'disk',
                'disk': 'disk',
                'cdrom': 'cdrom',
                'cd': 'cdrom',
                'dvd': 'cdrom',
                'default': 'disk'
            }
            
            vmware_device = device_map.get(bootdevice.lower(), 'disk')
            self.logger.debug(f"🔄 Mapping IPMI device '{bootdevice}' → VMware device '{vmware_device}'")
            
            success = self.vmware_client.set_boot_device(self.vm_name, vmware_device)
            
            if success:
                old_device = self.bootdevice
                self.bootdevice = bootdevice
                self.logger.info(f"✅ Boot device changed for VM {self.vm_name}: {old_device} → {bootdevice} - OpenShift notified")
            else:
                self.logger.error(f"❌ Failed to set boot device for VM {self.vm_name} - OpenShift will see error")
                
        except Exception as e:
            self.logger.error(f"💥 Error setting boot device for VM {self.vm_name}: {e}")

    def mount_cdrom_iso(self, iso_path, datastore_name=None):
        """
        Mount ISO to VM's CDROM
        
        Args:
            iso_path: Path to ISO file
            datastore_name: Datastore name (optional)
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.vmware_client:
            logger.error(f"No VMware client available for {self.vm_name}")
            return False
            
        try:
            logger.info(f"Mounting ISO {iso_path} to VM {self.vm_name}")
            success = self.vmware_client.mount_iso(self.vm_name, iso_path, datastore_name)
            
            if success:
                logger.info(f"ISO {iso_path} mounted successfully to VM {self.vm_name}")
                return True
            else:
                logger.error(f"Failed to mount ISO to VM {self.vm_name}")
                return False
                
        except Exception as e:
            logger.error(f"Error mounting ISO to VM {self.vm_name}: {e}")
            return False

    def unmount_cdrom_iso(self):
        """
        Unmount ISO from VM's CDROM
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.vmware_client:
            logger.error(f"No VMware client available for {self.vm_name}")
            return False
            
        try:
            logger.info(f"Unmounting ISO from VM {self.vm_name}")
            success = self.vmware_client.unmount_iso(self.vm_name)
            
            if success:
                logger.info(f"ISO unmounted successfully from VM {self.vm_name}")
                return True
            else:
                logger.error(f"Failed to unmount ISO from VM {self.vm_name}")
                return False
                
        except Exception as e:
            logger.error(f"Error unmounting ISO from VM {self.vm_name}: {e}")
            return False

    def set_boot_from_cdrom(self):
        """
        Set VM to boot from CDROM
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info(f"Setting VM {self.vm_name} to boot from CDROM")
            # Set boot device to CDROM
            self.set_boot_device('cdrom')
            
            # Also set boot order to prioritize CDROM
            if hasattr(self.vmware_client, 'set_boot_order'):
                success = self.vmware_client.set_boot_order(self.vm_name, ['cdrom', 'disk', 'network'])
                if success:
                    logger.info(f"Boot order set to CDROM first for VM {self.vm_name}")
                else:
                    logger.warning(f"Failed to set boot order for VM {self.vm_name}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error setting CDROM boot for VM {self.vm_name}: {e}")
            return False

    def cold_reset(self):
        """Cold reset - just reset the VM, don't exit"""
        logger.info(f"Cold reset requested for VM: {self.vm_name}")
        self.power_reset()

def load_config():
    """Load configuration from JSON file"""
    # Try multiple config paths
    config_paths = [
        '/home/lchiaret/git/ipmi-vmware/config/config.json',  # New organized structure
        '/opt/ipmi-vmware-bridge/config.json',               # Production path
        'config/config.json',                                # Relative path
        'config.json'                                        # Fallback
    ]
    
    for config_path in config_paths:
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                logger.info(f"✅ Configuration loaded from {config_path}")
                return config
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON in configuration file {config_path}: {e}")
        except Exception as e:
            logger.debug(f"📁 Could not load config from {config_path}: {e}")
    
    logger.error(f"❌ No valid configuration file found in any of: {config_paths}")
    return None

def main():
    """Main function to start the IPMI VMware bridge"""
    logger.info("🚀 Starting IPMI VMware Bridge Service")
    logger.info("📡 This bridge will receive IPMI calls from OpenShift Virtualization BMH (BareMetalHost) resources")
    
    # Load configuration
    config = load_config()
    if not config:
        logger.error("❌ Failed to load configuration. Exiting.")
        sys.exit(1)
    
    # Log configuration summary
    vm_count = len(config.get('vms', []))
    logger.info(f"📋 Configuration loaded: {vm_count} VMs configured")
    
    # Start BMC instances for each VM
    bmc_instances = []
    threads = []
    
    try:
        for i, vm_config in enumerate(config['vms']):
            try:
                vm_name = vm_config.get('name', f'VM-{i}')
                port = vm_config.get('port', 623 + i)
                
                logger.info(f"🎯 Setting up BMC {i+1}/{vm_count} for VM '{vm_name}' on port {port}")
                
                # Create authentication data
                authdata = {
                    vm_config.get('ipmi_user', 'admin'): vm_config.get('ipmi_password', 'password')
                }
                
                # Create BMC instance
                bmc_instance = VMwareBMC(authdata, port, vm_config)
                bmc_instances.append(bmc_instance)
                
                # Start BMC in separate thread
                thread = threading.Thread(target=bmc_instance.listen, daemon=True, name=f"BMC-{vm_name}")
                thread.start()
                threads.append(thread)
                
                logger.info(f"✅ BMC started for VM '{vm_name}' on port {port}")
                logger.info(f"🔗 OpenShift BMH can connect to: IPMI over LAN+ at port {port}")
                
            except Exception as e:
                logger.error(f"❌ Failed to start BMC for VM {vm_config.get('name', 'unknown')}: {e}")
        
        if not bmc_instances:
            logger.error("❌ No BMC instances started. Exiting.")
            sys.exit(1)
            
        logger.info(f"🎉 IPMI VMware Bridge started successfully!")
        logger.info(f"📊 Active BMC instances: {len(bmc_instances)}")
        logger.info(f"🔧 Debug mode: {'ENABLED' if debug_enabled else 'DISABLED'}")
        logger.info(f"📡 Ready to receive IPMI calls from OpenShift Virtualization")
        
        # Keep the main thread alive
        try:
            while True:
                time.sleep(10)
                # Check if any threads died
                for i, thread in enumerate(threads):
                    if not thread.is_alive():
                        logger.warning(f"🔄 BMC thread {i} died, restarting...")
                        vm_config = config['vms'][i]
                        authdata = {
                            vm_config.get('ipmi_user', 'admin'): vm_config.get('ipmi_password', 'password')
                        }
                        bmc_instance = VMwareBMC(authdata, vm_config['port'], vm_config)
                        thread = threading.Thread(target=bmc_instance.listen, daemon=True, name=f"BMC-{vm_config['name']}")
                        thread.start()
                        threads[i] = thread
                        bmc_instances[i] = bmc_instance
                        logger.info(f"✅ BMC thread restarted for VM {vm_config['name']}")
                        
        except KeyboardInterrupt:
            logger.info("🛑 Received interrupt signal, shutting down...")
            
    except Exception as e:
        logger.error(f"💥 Unexpected error in main: {e}")
        sys.exit(1)
    
    finally:
        # Cleanup
        logger.info("🧹 Cleaning up resources...")
        for i, bmc_instance in enumerate(bmc_instances):
            try:
                if hasattr(bmc_instance, 'vmware_client') and bmc_instance.vmware_client:
                    bmc_instance.vmware_client.disconnect()
                    logger.debug(f"🔌 Disconnected VMware client for BMC {i}")
            except Exception as e:
                logger.warning(f"⚠️ Error during cleanup for BMC {i}: {e}")
        
        logger.info("🏁 IPMI VMware Bridge stopped")

if __name__ == '__main__':
    main()
