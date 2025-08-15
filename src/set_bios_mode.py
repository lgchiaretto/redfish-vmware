#!/usr/bin/env python3
"""
Script to set VM firmware to legacy BIOS mode
"""

import json
import logging
from vmware_client import VMwareClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Set willie-worker-1 to legacy BIOS mode"""
    try:
        # Load configuration
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        vmware_config = config['vmware']
        
        # Connect to VMware
        client = VMwareClient(
            host=vmware_config['host'],
            user=vmware_config['user'],
            password=vmware_config['password'],
            port=vmware_config.get('port', 443),
            disable_ssl=vmware_config.get('disable_ssl', True)
        )
        
        # Set willie-worker-1 firmware to EFI
        vm_name = 'willie-worker-1'
        logger.info(f"Setting {vm_name} firmware to EFI...")
        
        result = client.set_vm_firmware(vm_name, 'efi')
        
        if result:
            logger.info(f"✅ Successfully set {vm_name} to EFI mode")
        else:
            logger.error(f"❌ Failed to set {vm_name} to EFI mode")
        
        client.disconnect()
        
    except Exception as e:
        logger.error(f"Error: {e}")

if __name__ == '__main__':
    main()
