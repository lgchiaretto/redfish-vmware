#!/usr/bin/env python3
"""
VMware IPMI BMC Multi-Instance Server
Cria uma instância separada do BMC para cada IP específico
"""

import sys
import pyghmi.ipmi.bmc as bmc
import logging
import threading
import time

class VMwareIPMIBMC(bmc.Bmc):
    """VMware IPMI BMC with VM mapping based on client IP"""
    
    def __init__(self, authdata, port, address, vm_name):
        super(VMwareIPMIBMC, self).__init__(authdata, port, address)
        
        # This instance represents a specific VM
        self.vm_name = vm_name
        self.powerstate = 'on'  # Default state
        self.bootdevice = 'default'
        
        # Setup logging
        self.logger = logging.getLogger(f'vmware_ipmi_bmc_{vm_name}')
        self.logger.setLevel(logging.DEBUG)
        
        self.logger.info(f"🚀 VMware IPMI BMC started for {vm_name} on {address}:{port}")
    
    def get_boot_device(self):
        """Get boot device for this VM"""
        self.logger.debug(f"💽 Boot device for {self.vm_name}: {self.bootdevice}")
        return self.bootdevice

    def set_boot_device(self, bootdevice):
        """Set boot device for this VM"""
        self.logger.info(f"💽 Set boot device for {self.vm_name}: {bootdevice}")
        self.bootdevice = bootdevice
        
        # TODO: Integrate with VMware API
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
        
        # TODO: Integrate with VMware API

    def power_on(self):
        """Power on this VM"""
        self.powerstate = 'on'
        self.logger.info(f"⚡ Power ON executed for {self.vm_name}")
        
        # TODO: Integrate with VMware API

    def power_reset(self):
        """Reset this VM"""
        self.logger.info(f"⚡ Power RESET executed for {self.vm_name}")
        
        # TODO: Integrate with VMware API

    def power_shutdown(self):
        """Graceful shutdown of this VM"""
        self.powerstate = 'off'
        self.logger.info(f"⚡ Power SHUTDOWN executed for {self.vm_name}")
        
        # TODO: Integrate with VMware API

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

def run_bmc_instance(ip_address, vm_name, port=623):
    """Run a BMC instance for specific IP and VM"""
    logger = logging.getLogger(f'bmc_instance_{vm_name}')
    
    try:
        # Authentication data
        authdata = {'admin': 'password'}
        
        # Create BMC instance for specific IP
        mybmc = VMwareIPMIBMC(authdata, port, ip_address, vm_name)
        
        logger.info(f"✅ Starting BMC for {vm_name} on {ip_address}:{port}")
        
        # Start listening
        mybmc.listen()
        
    except Exception as e:
        logger.error(f"❌ Error in BMC instance for {vm_name}: {e}")
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
    logger.info("🚀 Starting VMware IPMI BMC Multi-Instance Server")
    
    # VM to IP mappings
    vm_configs = [
        ('192.168.86.50', 'willie-master-0', 623),
        ('192.168.86.51', 'willie-master-1', 624),  # Different ports
        ('192.168.86.52', 'willie-master-2', 625),  # to avoid conflicts
    ]
    
    threads = []
    
    try:
        # Start BMC instance for each VM
        for ip_address, vm_name, port in vm_configs:
            logger.info(f"📋 Configuring {vm_name} on {ip_address}:{port}")
            
            # Create thread for this BMC instance
            thread = threading.Thread(
                target=run_bmc_instance,
                args=(ip_address, vm_name, port),
                daemon=True
            )
            thread.start()
            threads.append(thread)
            
            # Small delay to avoid startup conflicts
            time.sleep(1)
        
        logger.info(f"✅ Started {len(vm_configs)} BMC instances")
        logger.info("🔧 Test with:")
        for ip_address, vm_name, port in vm_configs:
            logger.info(f"  ipmitool -I lanplus -H {ip_address} -p {port} -U admin -P password chassis power status")
        
        logger.info("🛑 Press Ctrl+C to stop")
        
        # Keep main thread alive
        while True:
            time.sleep(10)
            # Check if any thread died
            for i, thread in enumerate(threads):
                if not thread.is_alive():
                    logger.error(f"❌ Thread {i} died, restarting...")
                    # Restart thread logic could go here
            
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down...")
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main()
