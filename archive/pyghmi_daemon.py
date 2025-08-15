#!/usr/bin/env python3
"""
Simple daemon wrapper for pyghmi server
"""

import os
import sys
import signal
import time
import logging
import subprocess

def daemonize():
    """Fork the process to run as daemon"""
    try:
        pid = os.fork()
        if pid > 0:
            # Parent process
            sys.exit(0)
    except OSError as e:
        sys.stderr.write(f"Fork failed: {e}\n")
        sys.exit(1)
    
    # Decouple from parent environment
    os.chdir("/")
    os.setsid()
    os.umask(0)
    
    # Second fork
    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
    except OSError as e:
        sys.stderr.write(f"Second fork failed: {e}\n")
        sys.exit(1)
    
    # Redirect standard file descriptors
    sys.stdout.flush()
    sys.stderr.flush()
    
    with open('/dev/null', 'r') as si:
        os.dup2(si.fileno(), sys.stdin.fileno())
    with open('/tmp/pyghmi_daemon.log', 'a+') as so:
        os.dup2(so.fileno(), sys.stdout.fileno())
    with open('/tmp/pyghmi_daemon.log', 'a+') as se:
        os.dup2(se.fileno(), sys.stderr.fileno())

def main():
    """Main daemon function"""
    if len(sys.argv) > 1 and sys.argv[1] == '--daemon':
        daemonize()
    
    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        filename='/tmp/pyghmi_daemon.log'
    )
    
    logger = logging.getLogger('daemon')
    logger.info("Starting pyghmi daemon")
    
    # Import and run pyghmi server
    try:
        sys.path.append('/home/lchiaret/git/ipmi-vmware')
        import pyghmi.ipmi.bmc as bmc
        
        class VMwareBMC(bmc.Bmc):
            def __init__(self, authdata, port=623, address="0.0.0.0"):
                self.vm_mapping = {
                    '192.168.86.50': 'skinner-master-0',
                    '192.168.86.51': 'skinner-master-1', 
                    '192.168.86.52': 'skinner-master-2',
                    '192.168.86.168': 'skinner-master-0',
                    '192.168.110.50': 'skinner-master-0',
                    '192.168.110.51': 'skinner-master-1',
                    '192.168.110.52': 'skinner-master-2'
                }
                
                self.power_states = {
                    'skinner-master-0': 'on',
                    'skinner-master-1': 'on', 
                    'skinner-master-2': 'on'
                }
                
                self.boot_devices = {
                    'skinner-master-0': 'default',
                    'skinner-master-1': 'default', 
                    'skinner-master-2': 'default'
                }
                
                self.logger = logging.getLogger('vmware_bmc')
                super(VMwareBMC, self).__init__(authdata, port=port, address=address)
                self.logger.info(f"VMware BMC initialized on {address}:{port}")
            
            def get_vm_name_from_session(self, session):
                try:
                    if hasattr(session, 'sockaddr') and session.sockaddr:
                        client_ip = session.sockaddr[0]
                        vm_name = self.vm_mapping.get(client_ip)
                        self.logger.debug(f"Client IP {client_ip} -> VM {vm_name}")
                        return vm_name
                    elif hasattr(session, 'clientaddr'):
                        client_ip = session.clientaddr
                        vm_name = self.vm_mapping.get(client_ip)
                        self.logger.debug(f"Client IP {client_ip} -> VM {vm_name}")
                        return vm_name
                    return None
                except Exception as e:
                    self.logger.error(f"Error getting VM name: {e}")
                    return None
            
            def get_power_state(self, session=None):
                try:
                    vm_name = self.get_vm_name_from_session(session) if session else 'skinner-master-0'
                    if not vm_name:
                        vm_name = 'skinner-master-0'
                    
                    power_state = self.power_states.get(vm_name, 'off')
                    self.logger.info(f"🔋 Power state for {vm_name}: {power_state}")
                    return power_state
                except Exception as e:
                    self.logger.error(f"Error getting power state: {e}")
                    return 'off'
            
            def set_power_state(self, powerstate, session=None):
                try:
                    vm_name = self.get_vm_name_from_session(session) if session else 'skinner-master-0'
                    if not vm_name:
                        vm_name = 'skinner-master-0'
                    
                    self.logger.info(f"⚡ Power control for {vm_name}: {powerstate}")
                    
                    if powerstate in ['on', 'off', 'reset', 'boot']:
                        new_state = 'on' if powerstate in ['on', 'reset', 'boot'] else 'off'
                        self.power_states[vm_name] = new_state
                        self.logger.info(f"✅ Power {powerstate} executed for {vm_name}")
                        return new_state
                    
                    return self.power_states.get(vm_name, 'off')
                except Exception as e:
                    self.logger.error(f"Error setting power state: {e}")
                    return 'off'
            
            def get_boot_device(self, session=None):
                try:
                    vm_name = self.get_vm_name_from_session(session) if session else 'skinner-master-0'
                    if not vm_name:
                        vm_name = 'skinner-master-0'
                    return self.boot_devices.get(vm_name, 'default')
                except Exception as e:
                    self.logger.error(f"Error getting boot device: {e}")
                    return 'default'
            
            def set_boot_device(self, bootdevice, session=None):
                try:
                    vm_name = self.get_vm_name_from_session(session) if session else 'skinner-master-0'
                    if not vm_name:
                        vm_name = 'skinner-master-0'
                    self.logger.info(f"💽 Set boot device for {vm_name}: {bootdevice}")
                    self.boot_devices[vm_name] = bootdevice
                    return bootdevice
                except Exception as e:
                    self.logger.error(f"Error setting boot device: {e}")
                    return 'default'
            
            def cold_reset(self):
                self.logger.info("BMC cold reset requested")
                pass
        
        # Authentication data
        authdata = {
            'admin': 'admin',
            'user': 'password', 
            '': ''
        }
        
        # Create and run BMC
        logger.info("Creating VMware BMC")
        mybmc = VMwareBMC(authdata, port=623, address="0.0.0.0")
        
        logger.info("BMC daemon started successfully")
        
        # Keep running
        while True:
            time.sleep(10)
            logger.debug("BMC daemon heartbeat")
            
    except Exception as e:
        logger.error(f"Error in daemon: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main()
