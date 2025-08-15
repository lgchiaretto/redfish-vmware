#!/usr/bin/env python3
"""
List all VMs in the VMware environment
"""

import logging
from vmware_client import VMwareClient
from configparser import ConfigParser

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def list_all_vms():
    """List all VMs with their power states"""
    logger = logging.getLogger(__name__)
    
    # Load config
    config = ConfigParser()
    config.read('config.ini')
    
    # Create VMware client
    vmware_client = VMwareClient(config)
    
    logger.info("Listing all VMs in the environment:")
    
    try:
        # Get all VMs
        from pyVmomi import vim
        vms = vmware_client.get_obj([vim.VirtualMachine])
        
        logger.info(f"Found {len(vms)} VMs:")
        
        powered_off_vms = []
        powered_on_vms = []
        
        for vm in vms:
            power_state = vm.runtime.powerState
            vm_info = f"  - {vm.name} ({power_state})"
            
            if "poweredOff" in str(power_state):
                powered_off_vms.append(vm.name)
            elif "poweredOn" in str(power_state):
                powered_on_vms.append(vm.name)
            
            logger.info(vm_info)
        
        logger.info(f"\nSummary:")
        logger.info(f"Powered On VMs: {len(powered_on_vms)}")
        logger.info(f"Powered Off VMs: {len(powered_off_vms)}")
        
        if powered_off_vms:
            logger.info("\nPowered Off VMs (good for testing):")
            for vm_name in powered_off_vms[:5]:  # Show first 5
                logger.info(f"  - {vm_name}")
        
    except Exception as e:
        logger.error(f"Error listing VMs: {e}")

if __name__ == "__main__":
    setup_logging()
    list_all_vms()
