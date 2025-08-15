#!/usr/bin/env python3
"""
VMware BMC based on pyghmi fakebmc
This is a direct adaptation of the working fakebmc for VMware control
"""

import sys
import pyghmi.ipmi.bmc as bmc
import logging

class VMwareFakeBmc(bmc.Bmc):
    """VMware BMC that mimics pyghmi's working fakebmc"""
    
    def __init__(self, authdata, port, address="0.0.0.0"):
        # VM mappings based on client IP  
        self.vm_mapping = {
            '192.168.86.50': 'skinner-master-0',
            '192.168.86.51': 'skinner-master-1', 
            '192.168.86.52': 'skinner-master-2',
            '192.168.86.168': 'skinner-master-0',  # Local testing
            '192.168.110.50': 'skinner-master-0',  # OpenShift
            '192.168.110.51': 'skinner-master-1',
            '192.168.110.52': 'skinner-master-2'
        }
        
        # Power states per VM
        self.powerstate = {
            'skinner-master-0': 'on',
            'skinner-master-1': 'on',
            'skinner-master-2': 'on'
        }
        
        # Boot devices per VM
        self.bootdevice = {
            'skinner-master-0': 'default',
            'skinner-master-1': 'default', 
            'skinner-master-2': 'default'
        }
        
        # Setup logging
        self.logger = logging.getLogger('vmware_fakebmc')
        self.logger.setLevel(logging.DEBUG)
        
        super(VMwareFakeBmc, self).__init__(authdata, port, address)
        
        self.logger.info(f"VMware FakeBMC started on {address}:{port}")
        self.logger.info(f"VM mappings: {self.vm_mapping}")
    
    def get_vm_for_session(self, session):
        """Get VM name for current session based on client IP"""
        try:
            # Try different ways to get client IP from session
            client_ip = None
            
            if hasattr(session, 'sockaddr') and session.sockaddr:
                client_ip = session.sockaddr[0]
            elif hasattr(session, 'clientaddr'):
                client_ip = session.clientaddr
            elif hasattr(session, 'addrinfo') and session.addrinfo:
                client_ip = session.addrinfo[0]
            
            if client_ip:
                vm_name = self.vm_mapping.get(client_ip)
                self.logger.debug(f"Session from {client_ip} -> VM {vm_name}")
                return vm_name or 'skinner-master-0'  # Default fallback
            
            self.logger.warning("Could not determine client IP from session, using default VM")
            return 'skinner-master-0'
            
        except Exception as e:
            self.logger.error(f"Error getting VM for session: {e}")
            return 'skinner-master-0'
    
    def get_power_state(self, session=None):
        """Get power state - modified to support VM-specific states"""
        vm_name = self.get_vm_for_session(session) if session else 'skinner-master-0'
        state = self.powerstate.get(vm_name, 'off')
        
        self.logger.info(f"🔋 Power state for {vm_name}: {state}")
        return state
    
    def set_power_state(self, powerstate, session=None):
        """Set power state - modified to support VM-specific control"""
        vm_name = self.get_vm_for_session(session) if session else 'skinner-master-0'
        
        self.logger.info(f"⚡ Power control for {vm_name}: {powerstate}")
        
        # Update power state
        self.powerstate[vm_name] = powerstate
        
        # Log the action
        actions = {
            'on': 'Power On',
            'off': 'Power Off', 
            'reset': 'Reset',
            'boot': 'Power Cycle'
        }
        action = actions.get(powerstate, f'Unknown ({powerstate})')
        self.logger.info(f"✅ {action} executed for {vm_name}")
        
        # TODO: Here we would integrate with VMware API:
        # - Get VMware connection
        # - Find VM by name
        # - Execute power action (vm.PowerOn(), vm.PowerOff(), vm.Reset())
        
        return powerstate
    
    def get_boot_device(self, session=None):
        """Get boot device for VM"""
        vm_name = self.get_vm_for_session(session) if session else 'skinner-master-0'
        device = self.bootdevice.get(vm_name, 'default')
        
        self.logger.debug(f"💽 Boot device for {vm_name}: {device}")
        return device
    
    def set_boot_device(self, bootdevice, session=None):
        """Set boot device for VM"""
        vm_name = self.get_vm_for_session(session) if session else 'skinner-master-0'
        
        self.logger.info(f"💽 Set boot device for {vm_name}: {bootdevice}")
        self.bootdevice[vm_name] = bootdevice
        
        # TODO: Here we would integrate with VMware API to set boot device
        
        return bootdevice
    
    def cold_reset(self):
        """BMC cold reset - just log it"""
        self.logger.info("BMC cold reset requested")
        # Don't exit like the original fakebmc - just log it
        pass

def main():
    """Main function"""
    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger('main')
    logger.info("Starting VMware FakeBMC based on pyghmi")
    
    # Authentication data - exactly like fakebmc
    authdata = {'admin': 'password'}
    
    try:
        # Create BMC - bind to all interfaces
        mybmc = VMwareFakeBmc(authdata, 623, "0.0.0.0")
        
        logger.info("VMware FakeBMC started successfully")
        logger.info("Compatible with: ipmitool -I lanplus -H <IP> -U admin -P password chassis power status")
        logger.info("Press Ctrl+C to stop")
        
        # Use the same listen() method as fakebmc
        mybmc.listen()
        
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main()
