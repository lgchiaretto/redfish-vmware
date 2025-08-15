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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/ipmi-vmware-bridge.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class VMwareBMC(bmc.Bmc):
    """VMware BMC implementation based on pyghmi Bmc"""
    
    def __init__(self, authdata, port, address=None, vm_config=None):
        super(VMwareBMC, self).__init__(authdata, port, address)
        self.vm_config = vm_config
        self.vm_name = vm_config['name']
        self.powerstate = 'unknown'
        self.bootdevice = 'default'
        
        # Initialize VMware client
        try:
            self.vmware_client = VMwareClient(
                vm_config['vcenter_host'],
                vm_config['vcenter_user'], 
                vm_config['vcenter_password']
            )
            logger.info(f"VMware client initialized for VM: {self.vm_name}")
            
            # Get initial power state
            self._update_power_state()
            
        except Exception as e:
            logger.error(f"Failed to initialize VMware client for {self.vm_name}: {e}")
            self.vmware_client = None

    def _update_power_state(self):
        """Update power state from VMware"""
        if not self.vmware_client:
            return
            
        try:
            is_powered_on = self.vmware_client.is_vm_powered_on(self.vm_name)
            self.powerstate = 'on' if is_powered_on else 'off'
            logger.debug(f"VM {self.vm_name} power state: {self.powerstate}")
        except Exception as e:
            logger.warning(f"Failed to get power state for {self.vm_name}: {e}")

    def get_power_state(self):
        """Get current power state - required by pyghmi BMC"""
        self._update_power_state()
        return self.powerstate  # Should return 'on' or 'off' as string

    def power_off(self):
        """Power off the VM"""
        if not self.vmware_client:
            logger.error(f"No VMware client available for {self.vm_name}")
            return
            
        try:
            logger.info(f"Powering off VM: {self.vm_name}")
            success = self.vmware_client.power_off_vm(self.vm_name)
            if success:
                self.powerstate = 'off'
                logger.info(f"VM {self.vm_name} powered off successfully")
            else:
                logger.error(f"Failed to power off VM {self.vm_name}")
        except Exception as e:
            logger.error(f"Error powering off VM {self.vm_name}: {e}")

    def power_on(self):
        """Power on the VM"""
        if not self.vmware_client:
            logger.error(f"No VMware client available for {self.vm_name}")
            return
            
        try:
            logger.info(f"Powering on VM: {self.vm_name}")
            success = self.vmware_client.power_on_vm(self.vm_name)
            if success:
                self.powerstate = 'on'
                logger.info(f"VM {self.vm_name} powered on successfully")
            else:
                logger.error(f"Failed to power on VM {self.vm_name}")
        except Exception as e:
            logger.error(f"Error powering on VM {self.vm_name}: {e}")

    def power_reset(self):
        """Reset the VM"""
        if not self.vmware_client:
            logger.error(f"No VMware client available for {self.vm_name}")
            return
            
        try:
            logger.info(f"Resetting VM: {self.vm_name}")
            success = self.vmware_client.reset_vm(self.vm_name)
            if success:
                self.powerstate = 'on'  # Reset leaves VM in powered on state
                logger.info(f"VM {self.vm_name} reset successfully")
            else:
                logger.error(f"Failed to reset VM {self.vm_name}")
        except Exception as e:
            logger.error(f"Error resetting VM {self.vm_name}: {e}")

    def power_shutdown(self):
        """Gracefully shutdown the VM"""
        if not self.vmware_client:
            logger.error(f"No VMware client available for {self.vm_name}")
            return
            
        try:
            logger.info(f"Gracefully shutting down VM: {self.vm_name}")
            success = self.vmware_client.shutdown_vm(self.vm_name)
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
        return self.bootdevice

    def set_boot_device(self, bootdevice):
        """Set boot device"""
        if not self.vmware_client:
            logger.error(f"No VMware client available for {self.vm_name}")
            return
            
        try:
            logger.info(f"Setting boot device for VM {self.vm_name}: {bootdevice}")
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
            success = self.vmware_client.set_boot_device(self.vm_name, vmware_device)
            
            if success:
                self.bootdevice = bootdevice
                logger.info(f"Boot device set to {bootdevice} for VM {self.vm_name}")
            else:
                logger.error(f"Failed to set boot device for VM {self.vm_name}")
                
        except Exception as e:
            logger.error(f"Error setting boot device for VM {self.vm_name}: {e}")

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
    config_path = '/opt/ipmi-vmware-bridge/config.json'
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        logger.info(f"Configuration loaded from {config_path}")
        return config
    except FileNotFoundError:
        logger.error(f"Configuration file not found: {config_path}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in configuration file: {e}")
        return None

def main():
    """Main function to start the IPMI VMware bridge"""
    logger.info("Starting IPMI VMware Bridge Service")
    
    # Load configuration
    config = load_config()
    if not config:
        logger.error("Failed to load configuration. Exiting.")
        sys.exit(1)
    
    # Start BMC instances for each VM
    bmc_instances = []
    threads = []
    
    try:
        for vm_config in config['vms']:
            try:
                # Create authentication data
                authdata = {
                    vm_config.get('ipmi_user', 'admin'): vm_config.get('ipmi_password', 'password')
                }
                
                # Create BMC instance
                bmc_instance = VMwareBMC(authdata, vm_config['port'], address='0.0.0.0', vm_config=vm_config)
                bmc_instances.append(bmc_instance)
                
                # Start BMC in separate thread
                thread = threading.Thread(target=bmc_instance.listen, daemon=True)
                thread.start()
                threads.append(thread)
                
                logger.info(f"BMC started for VM '{vm_config['name']}' on port {vm_config['port']}")
                
            except Exception as e:
                logger.error(f"Failed to start BMC for VM {vm_config.get('name', 'unknown')}: {e}")
        
        if not bmc_instances:
            logger.error("No BMC instances started. Exiting.")
            sys.exit(1)
            
        logger.info(f"IPMI VMware Bridge started with {len(bmc_instances)} BMC instances")
        
        # Keep the main thread alive
        try:
            while True:
                time.sleep(10)
                # Check if any threads died
                for i, thread in enumerate(threads):
                    if not thread.is_alive():
                        logger.warning(f"BMC thread {i} died, restarting...")
                        vm_config = config['vms'][i]
                        authdata = {
                            vm_config.get('ipmi_user', 'admin'): vm_config.get('ipmi_password', 'password')
                        }
                        bmc_instance = VMwareBMC(authdata, vm_config['port'], address='0.0.0.0', vm_config=vm_config)
                        thread = threading.Thread(target=bmc_instance.listen, daemon=True)
                        thread.start()
                        threads[i] = thread
                        bmc_instances[i] = bmc_instance
                        
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")
            
    except Exception as e:
        logger.error(f"Unexpected error in main: {e}")
        sys.exit(1)
    
    finally:
        # Cleanup
        for bmc_instance in bmc_instances:
            try:
                if hasattr(bmc_instance, 'vmware_client') and bmc_instance.vmware_client:
                    bmc_instance.vmware_client.disconnect()
            except Exception as e:
                logger.warning(f"Error during cleanup: {e}")
        
        logger.info("IPMI VMware Bridge stopped")

if __name__ == '__main__':
    main()
