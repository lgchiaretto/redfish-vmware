#!/usr/bin/env python3

import sys
import os
import logging
import signal
import time

# Add the source directory to the path
sys.path.insert(0, '/home/lchiaret/git/ipmi-vmware/src')

# Configure logging to be very verbose
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Import our modules
from ipmi_bridge import VMwareBMC

def signal_handler(sig, frame):
    print("\nShutting down...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

print("Starting single IPMI BMC with debug enabled...")

try:
    # Get VM config for skinner-worker-2
    vm_config = {
        "name": "skinner-worker-2",
        "vcenter_host": "chiaretto-vcsa01.chiaret.to",
        "vcenter_user": "administrator@chiaretto.local",
        "vcenter_password": "VMware1!VMware1!",
        "port": 627,
        "ipmi_user": "admin",
        "ipmi_password": "password"
    }
    
    # Authentication data
    authdata = {
        vm_config['ipmi_user']: vm_config['ipmi_password']
    }
    
    # Create BMC instance
    bmc = VMwareBMC(authdata, vm_config['port'], vm_config)
    
    # Start listening on port 627
    print(f"Starting BMC for {vm_config['name']} on port {vm_config['port']}")
    print("Press Ctrl+C to stop...")
    
    bmc.listen()
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
