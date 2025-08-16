#!/usr/bin/env python3

import sys
import os
import logging

# Add the source directory to the path
sys.path.insert(0, '/home/lchiaret/git/ipmi-vmware/src')

# Configure logging to be more verbose
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Enable pyghmi debug
logging.getLogger('pyghmi').setLevel(logging.DEBUG)

from ipmi_bridge import VMwareBMC

# Simple test with minimal configuration
vm_config = {
    "name": "skinner-worker-2",
    "vcenter_host": "chiaretto-vcsa01.chiaret.to",
    "vcenter_user": "administrator@chiaretto.local",
    "vcenter_password": "VMware1!VMware1!",
    "port": 627,
    "ipmi_user": "admin",
    "ipmi_password": "password"
}

authdata = {
    vm_config['ipmi_user']: vm_config['ipmi_password']
}

print("Starting simple IPMI BMC test...")

try:
    bmc = VMwareBMC(authdata, vm_config['port'], vm_config)
    print(f"BMC created for {vm_config['name']} on port {vm_config['port']}")
    print("Testing basic operations...")
    
    # Test power state
    power_state = bmc.get_power_state()
    print(f"Power state: {power_state}")
    
    print("Starting listener...")
    bmc.listen()
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
