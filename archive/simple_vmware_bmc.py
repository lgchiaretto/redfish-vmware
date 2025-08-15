#!/usr/bin/env python3
"""
Simple VMware BMC based on pyghmi fakebmc
Keeps it very close to the original to avoid issues
"""

import sys
import pyghmi.ipmi.bmc as bmc
import logging

class VMwareBmc(bmc.Bmc):
    """Simple VMware BMC that extends fakebmc"""
    
    def __init__(self, authdata, port):
        super(VMwareBmc, self).__init__(authdata, port)
        
        # Single power state for now - will extend later
        self.powerstate = 'off'
        self.bootdevice = 'default'
        
        # Setup logging
        self.logger = logging.getLogger('vmware_bmc')
        self.logger.setLevel(logging.DEBUG)
        
        self.logger.info(f"VMware BMC started on port {port}")
    
    def get_boot_device(self):
        """Get boot device - same as fakebmc"""
        return self.bootdevice

    def set_boot_device(self, bootdevice):
        """Set boot device - same as fakebmc"""
        self.bootdevice = bootdevice

    def cold_reset(self):
        """BMC cold reset - just log, don't exit"""
        self.logger.info("BMC cold reset requested - ignoring")
        # Don't exit like fakebmc
        pass

    def get_power_state(self):
        """Get power state - same as fakebmc"""
        self.logger.info(f"🔋 Power state: {self.powerstate}")
        return self.powerstate

    def power_off(self):
        """Power off - same as fakebmc"""
        self.powerstate = 'off'
        self.logger.info('⚡ Power OFF executed')

    def power_on(self):
        """Power on - same as fakebmc"""
        self.powerstate = 'on'
        self.logger.info('⚡ Power ON executed')

    def power_reset(self):
        """Power reset - same as fakebmc"""
        self.logger.info('⚡ Power RESET executed')
        pass

    def power_shutdown(self):
        """Power shutdown - same as fakebmc"""
        self.logger.info('⚡ Power SHUTDOWN executed')
        self.powerstate = 'off'

    def is_active(self):
        """Check if active - same as fakebmc"""
        active = self.powerstate == 'on'
        self.logger.debug(f"🔍 Is active: {active}")
        return active

    def iohandler(self, data):
        """IO handler - same as fakebmc"""
        self.logger.debug(f"💬 IO data: {data}")
        if self.sol:
            self.sol.send_data(data)

def main():
    """Main function"""
    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger('main')
    logger.info("Starting Simple VMware BMC")
    
    # Authentication - exactly like fakebmc
    authdata = {'admin': 'password'}
    
    try:
        # Create BMC - same as fakebmc original
        mybmc = VMwareBmc(authdata, 623)
        
        logger.info("Simple VMware BMC started successfully")
        logger.info("Test with: ipmitool -I lanplus -H <IP> -U admin -P password chassis power status")
        logger.info("Press Ctrl+C to stop")
        
        # Listen for connections
        mybmc.listen()
        
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main()
