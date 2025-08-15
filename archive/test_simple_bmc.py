#!/usr/bin/env python3
"""
Simple IPMI VMware Bridge Test

A simplified version to test basic IPMI functionality
"""

from pyghmi.ipmi import bmc
import logging
import threading
import time
from vmware_client import VMwareClient
import json

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class SimpleVMwareBMC(bmc.Bmc):
    """Simple BMC implementation for testing"""
    
    def __init__(self, vm_name, vmware_config, authdata, **kwargs):
        super().__init__(authdata=authdata, **kwargs)
        self.vm_name = vm_name
        self.vmware_client = VMwareClient(**vmware_config)
        logger.info(f"Initialized Simple BMC for {vm_name}")
    
    def get_power_state(self):
        """Get power state from VMware"""
        try:
            vm = self.vmware_client.get_vm(self.vm_name)
            if vm:
                state = vm.runtime.powerState
                if state == 'poweredOn':
                    return 'on'
                elif state == 'poweredOff':
                    return 'off'
                else:
                    return 'unknown'
            return 'off'
        except Exception as e:
            logger.error(f"Error getting power state: {e}")
            return 'off'
    
    def power_on(self):
        """Power on VM"""
        try:
            return self.vmware_client.power_on_vm(self.vm_name)
        except Exception as e:
            logger.error(f"Error powering on: {e}")
            return False
    
    def power_off(self):
        """Power off VM"""
        try:
            return self.vmware_client.power_off_vm(self.vm_name, force=True)
        except Exception as e:
            logger.error(f"Error powering off: {e}")
            return False
    
    def power_reset(self):
        """Reset VM"""
        try:
            return self.vmware_client.reset_vm(self.vm_name)
        except Exception as e:
            logger.error(f"Error resetting: {e}")
            return False

def test_single_bmc():
    """Test single BMC instance"""
    
    # Load config
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    vm_config = config['vms'][0]  # Test first VM
    
    print(f"Testing BMC for {vm_config['vm_name']} on port {vm_config['ipmi_port']}")
    
    try:
        # Create BMC
        bmc_instance = SimpleVMwareBMC(
            vm_name=vm_config['vm_name'],
            vmware_config=config['vmware'],
            authdata={vm_config['ipmi_user']: vm_config['ipmi_password']},
            address='127.0.0.1',
            port=vm_config['ipmi_port']
        )
        
        # Start BMC in thread
        bmc_thread = threading.Thread(target=bmc_instance.listen, daemon=True)
        bmc_thread.start()
        
        print(f"BMC started on port {vm_config['ipmi_port']}")
        print("Waiting for connections...")
        
        # Keep running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping BMC...")
            
    except Exception as e:
        print(f"Error: {e}")
        logger.exception("BMC test failed")

if __name__ == '__main__':
    test_single_bmc()
