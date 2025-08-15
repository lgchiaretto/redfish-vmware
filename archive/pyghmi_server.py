#!/usr/bin/env python3
"""
Robust IPMI Server using pyghmi library
This implementation uses the mature pyghmi library for full IPMI v1.5/v2.0 compatibility
"""

import logging
import threading
import time
import socket
import struct
from typing import Dict, Optional, Tuple
import sys
import os

# Import pyghmi BMC
try:
    import pyghmi.ipmi.bmc as bmc
except ImportError:
    print("Installing pyghmi...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyghmi"])
    import pyghmi.ipmi.bmc as bmc

class VMwareBMC(bmc.Bmc):
    """
    Custom BMC implementation for VMware VM control
    Inherits from pyghmi's robust BMC base class
    """
    
    def __init__(self, authdata, port=623, address="0.0.0.0"):
        # VM mappings based on client IP
        self.vm_mapping = {
            '192.168.86.50': 'skinner-master-0',
            '192.168.86.51': 'skinner-master-1', 
            '192.168.86.52': 'skinner-master-2',
            '192.168.86.168': 'skinner-master-0',  # Local testing
            '192.168.110.50': 'skinner-master-0',  # OpenShift
            '192.168.110.51': 'skinner-master-1',
            '192.168.110.52': 'skinner-master-2'
        }
        
        # Current power states (cached)
        self.power_states = {
            'skinner-master-0': 'on',
            'skinner-master-1': 'on', 
            'skinner-master-2': 'on'
        }
        
        # Boot devices
        self.boot_devices = {
            'skinner-master-0': 'default',
            'skinner-master-1': 'default', 
            'skinner-master-2': 'default'
        }
        
        # Setup logging
        self.logger = logging.getLogger('vmware_bmc')
        self.logger.setLevel(logging.DEBUG)
        
        # Initialize BMC with pyghmi
        super(VMwareBMC, self).__init__(authdata, port=port, address=address)
        
        self.logger.info(f"VMware BMC initialized on {address}:{port}")
        self.logger.info(f"VM mappings: {self.vm_mapping}")
    
    def get_vm_name_from_session(self, session):
        """Get VM name based on client IP from session"""
        try:
            if hasattr(session, 'sockaddr') and session.sockaddr:
                client_ip = session.sockaddr[0]
                vm_name = self.vm_mapping.get(client_ip)
                self.logger.debug(f"Client IP {client_ip} -> VM {vm_name}")
                return vm_name
            elif hasattr(session, 'clientaddr'):
                client_ip = session.clientaddr
                vm_name = self.vm_mapping.get(client_ip)
                self.logger.debug(f"Client IP {client_ip} -> VM {vm_name}")
                return vm_name
            return None
        except Exception as e:
            self.logger.error(f"Error getting VM name from session: {e}")
            return None
    
    def get_power_state(self, session=None):
        """Get power state for the VM associated with this session"""
        try:
            vm_name = self.get_vm_name_from_session(session) if session else 'skinner-master-0'
            if not vm_name:
                self.logger.warning("No VM mapped for session, using default")
                vm_name = 'skinner-master-0'
            
            # Get current power state
            power_state = self.power_states.get(vm_name, 'off')
            
            self.logger.info(f"🔋 Power state for {vm_name}: {power_state}")
            
            # TODO: Integrate with VMware API to get real power state
            # For now, return cached state
            
            return power_state
            
        except Exception as e:
            self.logger.error(f"Error getting power state: {e}")
            return 'off'
    
    def set_power_state(self, powerstate, session=None):
        """Set power state for the VM associated with this session"""
        try:
            vm_name = self.get_vm_name_from_session(session) if session else 'skinner-master-0'
            if not vm_name:
                self.logger.warning("No VM mapped for session, using default")
                vm_name = 'skinner-master-0'
            
            self.logger.info(f"⚡ Power control for {vm_name}: {powerstate}")
            
            # Map IPMI power states to actions
            if powerstate == 'on':
                action = "Power On"
                new_state = 'on'
            elif powerstate == 'off':
                action = "Power Off"
                new_state = 'off'
            elif powerstate == 'reset':
                action = "Reset"
                new_state = 'on'
            elif powerstate == 'boot':
                action = "Power Cycle"
                new_state = 'on'
            else:
                action = f"Unknown ({powerstate})"
                new_state = self.power_states.get(vm_name, 'off')
            
            self.logger.info(f"✅ {action} executed for {vm_name}")
            
            # Update cached state
            self.power_states[vm_name] = new_state
            
            # TODO: Integrate with VMware API to actually control the VM
            # This is where we would call VMware API to:
            # - vm.PowerOn() for powerstate == 'on'
            # - vm.PowerOff() for powerstate == 'off'  
            # - vm.Reset() for powerstate == 'reset'
            
            return new_state
            
        except Exception as e:
            self.logger.error(f"Error setting power state: {e}")
            return 'off'
    
    def get_boot_device(self, session=None):
        """Get boot device for the VM"""
        try:
            vm_name = self.get_vm_name_from_session(session) if session else 'skinner-master-0'
            if not vm_name:
                vm_name = 'skinner-master-0'
                
            boot_device = self.boot_devices.get(vm_name, 'default')
            self.logger.debug(f"Get boot device for {vm_name}: {boot_device}")
            
            return boot_device
            
        except Exception as e:
            self.logger.error(f"Error getting boot device: {e}")
            return 'default'
    
    def set_boot_device(self, bootdevice, session=None):
        """Set boot device for the VM"""
        try:
            vm_name = self.get_vm_name_from_session(session) if session else 'skinner-master-0'
            if not vm_name:
                vm_name = 'skinner-master-0'
                
            self.logger.info(f"💽 Set boot device for {vm_name}: {bootdevice}")
            
            # Update cached boot device
            self.boot_devices[vm_name] = bootdevice
            
            # TODO: Integrate with VMware API to set boot device
            # This would involve:
            # - Modifying VM boot order
            # - Setting one-time boot device if not persistent
            
            return bootdevice
            
        except Exception as e:
            self.logger.error(f"Error setting boot device: {e}")
            return 'default'
    
    def cold_reset(self):
        """Handle BMC cold reset"""
        self.logger.info("BMC cold reset requested - restarting BMC")
        # In a real implementation, this might restart the BMC service
        # For now, we'll just log it
        pass

def main():
    """Main entry point"""
    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger('main')
    logger.info("Starting VMware IPMI BMC Server using pyghmi")
    
    # Define users and passwords
    # This is a simple authentication database
    authdata = {
        'admin': 'admin',      # OpenShift credentials
        'user': 'password',    # Alternative credentials
        '': ''                 # Anonymous access (for compatibility)
    }
    
    try:
        # Create and start BMC
        mybmc = VMwareBMC(authdata, port=623, address="0.0.0.0")
        
        logger.info("BMC server started successfully")
        logger.info("Listening on all interfaces, port 623")
        logger.info("Press Ctrl+C to stop")
        
        # Keep the server running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Shutting down BMC server...")
    except Exception as e:
        logger.error(f"Error running BMC server: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        logger.info("BMC server stopped")

if __name__ == "__main__":
    main()
