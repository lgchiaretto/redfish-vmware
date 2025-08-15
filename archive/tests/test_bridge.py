#!/usr/bin/env python3
"""
Test script to demonstrate IPMI-VMware Bridge functionality
"""

import time
import logging
from vmware_client import VMwareClient
from configparser import ConfigParser

def setup_logging():
    """Setup basic logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def test_vm_operations():
    """Test VM power operations"""
    logger = logging.getLogger(__name__)
    
    # Load config
    config = ConfigParser()
    config.read('config.ini')
    
    # Create VMware client
    vmware_client = VMwareClient(config)
    
    # Test VM name (you can change this to any VM in your environment)
    test_vm = "TESTE1"
    
    logger.info(f"Testing VM operations on: {test_vm}")
    
    # Test 1: Get current power state
    logger.info("=== Test 1: Get Power State ===")
    power_state = vmware_client.get_vm_power_state(test_vm)
    logger.info(f"Current power state: {power_state}")
    
    # Test 2: Power operations based on current state
    if power_state and "poweredOff" in str(power_state):
        logger.info("=== Test 2: Power On VM ===")
        success = vmware_client.power_on_vm(test_vm)
        logger.info(f"Power on result: {success}")
        
        if success:
            time.sleep(5)  # Wait a bit
            
            logger.info("=== Test 3: Get Power State After Power On ===")
            new_state = vmware_client.get_vm_power_state(test_vm)
            logger.info(f"New power state: {new_state}")
            
            logger.info("=== Test 4: Power Off VM ===")
            success = vmware_client.power_off_vm(test_vm)
            logger.info(f"Power off result: {success}")
    
    elif power_state and "poweredOn" in str(power_state):
        logger.info("=== Test 2: Reset VM ===")
        success = vmware_client.reset_vm(test_vm)
        logger.info(f"Reset result: {success}")
        
        time.sleep(3)
        
        logger.info("=== Test 3: Power Off VM ===")
        success = vmware_client.power_off_vm(test_vm)
        logger.info(f"Power off result: {success}")
    
    logger.info("VM operation tests completed!")

def test_ipmi_protocol():
    """Test IPMI protocol simulation"""
    logger = logging.getLogger(__name__)
    
    logger.info("=== IPMI Protocol Test ===")
    logger.info("This would test actual IPMI commands, but requires:")
    logger.info("1. Running the IPMI server (python main.py)")
    logger.info("2. Using ipmitool from another machine")
    logger.info("3. Example command: ipmitool -I lanplus -H <server_ip> -U admin -P admin chassis power status")
    
def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("Starting IPMI-VMware Bridge Tests...")
    
    try:
        # Test VM operations
        test_vm_operations()
        
        # Test IPMI protocol info
        test_ipmi_protocol()
        
        logger.info("All tests completed!")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")

if __name__ == "__main__":
    main()
