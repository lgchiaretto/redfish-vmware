#!/usr/bin/env python3

import sys
import os
import logging

# Add the source directory to the path
sys.path.insert(0, '/home/lchiaret/git/ipmi-vmware/src')

# Configure logging to be more verbose
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

import pyghmi.ipmi.command as ipmi

def test_chassis_status():
    """Test chassis status command specifically"""
    print("Testing chassis status command...")
    
    try:
        # Try to get chassis status from our BMC
        bmc = ipmi.Command(bmc='127.0.0.1', userid='admin', password='password', port=627)
        
        # Try chassis status
        print("Getting chassis status...")
        result = bmc.get_power()
        print(f"Chassis status result: {result}")
        
    except Exception as e:
        print(f"Error testing chassis status: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_chassis_status()
