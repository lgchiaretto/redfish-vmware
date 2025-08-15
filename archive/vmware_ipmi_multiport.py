#!/usr/bin/env python3
"""
VMware IPMI BMC Server - Multi-Port Version
Usa diferentes portas para diferentes VMs, resolvendo o problema de routing
"""

import sys
import pyghmi.ipmi.bmc as bmc
import logging
import threading
import time

class VMwareIPMIBMC(bmc.Bmc):
    """VMware IPMI BMC with port-based VM mapping"""
    
    def __init__(self, authdata, port, vm_name):
        # Use default address (all interfaces)
        super(VMwareIPMIBMC, self).__init__(authdata, port)
        
        # This instance represents a specific VM
        self.vm_name = vm_name
        self.port = port
        
        # VM state
        self.powerstate = 'on'  # Default state
        self.bootdevice = 'default'
        
        # Setup logging
        self.logger = logging.getLogger(f'vmware_bmc_{port}')
        self.logger.setLevel(logging.INFO)
        
        self.logger.info(f"🚀 VMware IPMI BMC started for {vm_name} on port {port}")
    
    def get_boot_device(self):
        """Get boot device for this VM"""
        self.logger.debug(f"💽 Boot device for {self.vm_name}: {self.bootdevice}")
        return self.bootdevice

    def set_boot_device(self, bootdevice):
        """Set boot device for this VM"""
        self.logger.info(f"💽 Set boot device for {self.vm_name}: {bootdevice}")
        self.bootdevice = bootdevice
        return bootdevice

    def cold_reset(self):
        """BMC cold reset - log but don't exit"""
        self.logger.info(f"🔄 BMC cold reset requested for {self.vm_name} - ignoring")
        pass

    def get_power_state(self):
        """Get power state for this VM"""
        self.logger.info(f"🔋 Power state for {self.vm_name}: {self.powerstate}")
        return self.powerstate

    def power_off(self):
        """Power off this VM"""
        self.powerstate = 'off'
        self.logger.info(f"⚡ Power OFF executed for {self.vm_name}")

    def power_on(self):
        """Power on this VM"""
        self.powerstate = 'on'
        self.logger.info(f"⚡ Power ON executed for {self.vm_name}")

    def power_reset(self):
        """Reset this VM"""
        self.logger.info(f"⚡ Power RESET executed for {self.vm_name}")

    def power_shutdown(self):
        """Graceful shutdown of this VM"""
        self.powerstate = 'off'
        self.logger.info(f"⚡ Power SHUTDOWN executed for {self.vm_name}")

    def is_active(self):
        """Check if this VM is active"""
        active = self.powerstate == 'on'
        self.logger.debug(f"🔍 Is {self.vm_name} active: {active}")
        return active

    def iohandler(self, data):
        """Handle serial/console IO"""
        self.logger.debug(f"💬 IO data for {self.vm_name}: {data}")
        if self.sol:
            self.sol.send_data(data)

def run_bmc_instance(vm_name, port):
    """Run a BMC instance for specific VM on specific port"""
    logger = logging.getLogger(f'bmc_{port}')
    
    try:
        # Authentication data
        authdata = {'admin': 'password'}
        
        # Create BMC instance
        mybmc = VMwareIPMIBMC(authdata, port, vm_name)
        
        logger.info(f"✅ Starting BMC for {vm_name} on port {port}")
        
        # Start listening
        mybmc.listen()
        
    except Exception as e:
        logger.error(f"❌ Error in BMC for {vm_name}: {e}")
        import traceback
        logger.error(traceback.format_exc())

def main():
    """Main function"""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger('main')
    logger.info("🚀 Starting VMware IPMI BMC Multi-Port Server")
    
    # VM configurations - different ports to avoid conflicts
    vm_configs = [
        ('skinner-master-0', 623),  # Standard IPMI port
        ('skinner-master-1', 624),  # IPMI + 1  
        ('skinner-master-2', 625),  # IPMI + 2
    ]
    
    threads = []
    
    try:
        # Start BMC instance for each VM on different port
        for vm_name, port in vm_configs:
            logger.info(f"📋 Configuring {vm_name} on port {port}")
            
            # Create thread for this BMC instance
            thread = threading.Thread(
                target=run_bmc_instance,
                args=(vm_name, port),
                daemon=True
            )
            thread.start()
            threads.append(thread)
            
            # Small delay to avoid startup conflicts
            time.sleep(1)
        
        logger.info(f"✅ Started {len(vm_configs)} BMC instances")
        logger.info("🔧 Test with:")
        logger.info("  # skinner-master-0:")
        logger.info("  ipmitool -I lanplus -H <ANY_IP> -p 623 -U admin -P password chassis power status")
        logger.info("  # skinner-master-1:")
        logger.info("  ipmitool -I lanplus -H <ANY_IP> -p 624 -U admin -P password chassis power status")
        logger.info("  # skinner-master-2:")
        logger.info("  ipmitool -I lanplus -H <ANY_IP> -p 625 -U admin -P password chassis power status")
        
        logger.info("🛑 Press Ctrl+C to stop")
        
        # Keep main thread alive
        while True:
            time.sleep(10)
            # Check if any thread died
            alive_threads = [t for t in threads if t.is_alive()]
            if len(alive_threads) != len(threads):
                logger.warning(f"⚠️  Only {len(alive_threads)}/{len(threads)} threads alive")
            
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down...")
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main()
