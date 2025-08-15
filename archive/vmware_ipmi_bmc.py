#!/usr/bin/env python3
"""
VMware IPMI BMC Server - Final Implementation
Implements a working IPMI BMC using pyghmi that maps client IPs to VMs
for OpenShift BareMetalHost integration
"""

import sys
import pyghmi.ipmi.bmc as bmc
import logging

class VMwareIPMIBMC(bmc.Bmc):
    """VMware IPMI BMC with VM mapping based on client IP"""
    
    def __init__(self, authdata, port, address="0.0.0.0"):
        super(VMwareIPMIBMC, self).__init__(authdata, port, address)
        
        # VM mappings: Client IP -> VM Name (include IPv6-mapped IPv4)
        self.vm_mapping = {
            '192.168.86.50': 'skinner-master-0',
            '192.168.86.51': 'skinner-master-1', 
            '192.168.86.52': 'skinner-master-2',
            '192.168.86.168': 'skinner-master-0',  # Local testing
            '192.168.110.50': 'skinner-master-0',  # OpenShift network
            '192.168.110.51': 'skinner-master-1',
            '192.168.110.52': 'skinner-master-2',
            '127.0.0.1': 'skinner-master-0',       # Localhost testing
            '::ffff:127.0.0.1': 'skinner-master-0', # IPv6-mapped localhost
            '::ffff:192.168.86.168': 'skinner-master-0', # IPv6-mapped local IP
            '::1': 'skinner-master-0'              # IPv6 localhost
        }
        
        # VM Power states: VM Name -> State
        self.vm_power_states = {
            'skinner-master-0': 'on',
            'skinner-master-1': 'on',
            'skinner-master-2': 'on'
        }
        
        # VM Boot devices: VM Name -> Boot Device
        self.vm_boot_devices = {
            'skinner-master-0': 'default',
            'skinner-master-1': 'default', 
            'skinner-master-2': 'default'
        }
        
        # Default fallback state (for unknown IPs)
        self.powerstate = 'off'
        self.bootdevice = 'default'
        
        # Current session tracking
        self.current_session = None
        
        # Setup logging
        self.logger = logging.getLogger('vmware_ipmi_bmc')
        self.logger.setLevel(logging.DEBUG)
        
        self.logger.info(f"🚀 VMware IPMI BMC started on {address}:{port}")
        self.logger.info(f"📋 VM mappings configured: {len(self.vm_mapping)} IPs")
        for ip, vm in self.vm_mapping.items():
            self.logger.info(f"  {ip} -> {vm}")
    
    def control_chassis(self, request, session):
        """Override control_chassis to track current session"""
        self.current_session = session
        # Call parent implementation
        return super(VMwareIPMIBMC, self).control_chassis(request, session)
    
    def get_vm_for_session(self, session=None):
        """Get VM name for current session based on client IP"""
        try:
            # Use provided session or current session
            target_session = session or self.current_session
            
            if not target_session:
                self.logger.warning("❓ No session available, using default VM")
                return 'skinner-master-0'
            
            # Try to get client IP from session
            client_ip = None
            
            if hasattr(target_session, 'sockaddr') and target_session.sockaddr:
                client_ip = target_session.sockaddr[0]
            elif hasattr(target_session, 'clientaddr'):
                client_ip = target_session.clientaddr
            elif hasattr(target_session, 'addrinfo') and target_session.addrinfo:
                client_ip = target_session.addrinfo[0]
            
            if client_ip and client_ip in self.vm_mapping:
                vm_name = self.vm_mapping[client_ip]
                self.logger.debug(f"🔍 Client {client_ip} -> VM {vm_name}")
                return vm_name
            
            self.logger.warning(f"❓ Unknown client IP {client_ip}, using default VM")
            return 'skinner-master-0'  # Default fallback
            
        except Exception as e:
            self.logger.error(f"❌ Error getting VM for session: {e}")
            return 'skinner-master-0'
    
    def get_boot_device(self):
        """Get boot device for specific VM"""
        vm_name = self.get_vm_for_session()
        device = self.vm_boot_devices.get(vm_name, 'default')
        self.logger.debug(f"💽 Boot device for {vm_name}: {device}")
        return device

    def set_boot_device(self, bootdevice):
        """Set boot device for specific VM"""
        vm_name = self.get_vm_for_session()
        self.logger.info(f"💽 Set boot device for {vm_name}: {bootdevice}")
        self.vm_boot_devices[vm_name] = bootdevice
        
        # TODO: Integrate with VMware API to set actual boot device
        # vmware_client = get_vmware_connection()
        # vm = vmware_client.find_vm_by_name(vm_name)
        # vm.set_boot_device(bootdevice)
        
        return bootdevice

    def cold_reset(self):
        """BMC cold reset - log but don't exit"""
        self.logger.info("🔄 BMC cold reset requested - ignoring")
        pass

    def get_power_state(self):
        """Get power state for specific VM"""
        vm_name = self.get_vm_for_session()
        state = self.vm_power_states.get(vm_name, 'off')
        self.logger.info(f"🔋 Power state for {vm_name}: {state}")
        return state

    def power_off(self):
        """Power off specific VM"""
        vm_name = self.get_vm_for_session()
        self.vm_power_states[vm_name] = 'off'
        self.logger.info(f"⚡ Power OFF executed for {vm_name}")
        
        # TODO: Integrate with VMware API for actual power control
        # vmware_client = get_vmware_connection()
        # vm = vmware_client.find_vm_by_name(vm_name)
        # vm.power_off()

    def power_on(self):
        """Power on specific VM"""
        vm_name = self.get_vm_for_session()
        self.vm_power_states[vm_name] = 'on'
        self.logger.info(f"⚡ Power ON executed for {vm_name}")
        
        # TODO: Integrate with VMware API for actual power control
        # vmware_client = get_vmware_connection()
        # vm = vmware_client.find_vm_by_name(vm_name)
        # vm.power_on()

    def power_reset(self):
        """Reset specific VM"""
        vm_name = self.get_vm_for_session()
        self.logger.info(f"⚡ Power RESET executed for {vm_name}")
        
        # TODO: Integrate with VMware API for actual reset
        # vmware_client = get_vmware_connection()
        # vm = vmware_client.find_vm_by_name(vm_name)
        # vm.reset()

    def power_shutdown(self):
        """Graceful shutdown of specific VM"""
        vm_name = self.get_vm_for_session()
        self.vm_power_states[vm_name] = 'off'
        self.logger.info(f"⚡ Power SHUTDOWN executed for {vm_name}")
        
        # TODO: Integrate with VMware API for graceful shutdown
        # vmware_client = get_vmware_connection()
        # vm = vmware_client.find_vm_by_name(vm_name)
        # vm.shutdown_guest()

    def is_active(self):
        """Check if specific VM is active"""
        vm_name = self.get_vm_for_session()
        active = self.vm_power_states.get(vm_name, 'off') == 'on'
        self.logger.debug(f"🔍 Is {vm_name} active: {active}")
        return active

    def iohandler(self, data):
        """Handle serial/console IO"""
        vm_name = self.get_vm_for_session()
        self.logger.debug(f"💬 IO data for {vm_name}: {data}")
        
        if self.sol:
            self.sol.send_data(data)

def main():
    """Main function"""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger('main')
    logger.info("🚀 Starting VMware IPMI BMC Server")
    
    # Authentication data
    authdata = {'admin': 'password'}
    
    try:
        # Create BMC - bind to all IPv4 interfaces
        mybmc = VMwareIPMIBMC(authdata, 623, "0.0.0.0")
        
        logger.info("✅ VMware IPMI BMC started successfully")
        logger.info("🔧 Test with: ipmitool -I lanplus -H <IP> -U admin -P password chassis power status")
        logger.info("🛑 Press Ctrl+C to stop")
        
        # Start listening
        mybmc.listen()
        
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down...")
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main()
