#!/usr/bin/env python3
"""
IPMI to VMware Bridge Server

This application receives IPMI commands and translates them to VMware vSphere operations.
It simulates a physical BMC (Baseboard Management Controller) for virtual machines.

Requirements:
- pyVmomi for VMware vSphere API
- pyghmi for IPMI protocol handling
- python-daemon for proper daemon functionality
"""

import sys
import logging
import argparse
from pyghmi.ipmi.bmc import Bmc
from pyghmi.ipmi import sdr
from threading import Thread
import time
import json
import os
from vmware_client import VMwareClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/ipmi-vmware-bridge.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class VMwareBMC(Bmc):
    """
    BMC implementation that bridges IPMI commands to VMware vSphere operations
    """
    
    def __init__(self, vm_name, vmware_config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.vm_name = vm_name
        self.vmware_client = VMwareClient(
            host=vmware_config['host'],
            user=vmware_config['user'],
            password=vmware_config['password'],
            port=vmware_config.get('port', 443),
            disable_ssl_verification=vmware_config.get('disable_ssl', True)
        )
        
        # BMC sensor data
        self.sensors = {
            'power_state': {'name': 'Power State', 'type': 'power', 'value': 0},
            'temperature': {'name': 'CPU Temperature', 'type': 'temperature', 'value': 25.0},
            'fan_speed': {'name': 'Fan Speed', 'type': 'fan', 'value': 2000},
            'voltage': {'name': 'System Voltage', 'type': 'voltage', 'value': 12.0}
        }
        
        logger.info(f"Initialized VMware BMC for VM: {vm_name}")
    
    def get_power_state(self):
        """Get the current power state from VMware"""
        try:
            vm = self.vmware_client.get_vm(self.vm_name)
            if vm:
                power_state = vm.runtime.powerState
                if power_state == 'poweredOn':
                    return 'on'
                elif power_state == 'poweredOff':
                    return 'off'
                else:
                    return 'unknown'
            return 'unknown'
        except Exception as e:
            logger.error(f"Error getting power state: {e}")
            return 'unknown'
    
    def set_power_state(self, state):
        """Set the power state in VMware"""
        try:
            vm = self.vmware_client.get_vm(self.vm_name)
            if not vm:
                logger.error(f"VM {self.vm_name} not found")
                return False
            
            if state == 'on':
                if vm.runtime.powerState == 'poweredOff':
                    task = vm.PowerOnVM_Task()
                    logger.info(f"Powering on VM {self.vm_name}")
                    return True
            elif state == 'off':
                if vm.runtime.powerState == 'poweredOn':
                    task = vm.PowerOffVM_Task()
                    logger.info(f"Powering off VM {self.vm_name}")
                    return True
            elif state == 'reset':
                if vm.runtime.powerState == 'poweredOn':
                    task = vm.ResetVM_Task()
                    logger.info(f"Resetting VM {self.vm_name}")
                    return True
            elif state == 'cycle':
                if vm.runtime.powerState == 'poweredOn':
                    # Power off then on
                    task = vm.PowerOffVM_Task()
                    time.sleep(2)
                    task = vm.PowerOnVM_Task()
                    logger.info(f"Power cycling VM {self.vm_name}")
                    return True
            
            return True
        except Exception as e:
            logger.error(f"Error setting power state: {e}")
            return False
    
    def get_boot_device(self):
        """Get current boot device"""
        try:
            vm = self.vmware_client.get_vm(self.vm_name)
            if vm and vm.config and vm.config.bootOptions:
                boot_order = vm.config.bootOptions.bootOrder
                if boot_order:
                    first_device = boot_order[0]
                    if hasattr(first_device, 'deviceKey'):
                        # Map device keys to boot device names
                        return 'disk'  # Default to disk
                return 'disk'
            return 'disk'
        except Exception as e:
            logger.error(f"Error getting boot device: {e}")
            return 'disk'
    
    def set_boot_device(self, device):
        """Set boot device"""
        try:
            vm = self.vmware_client.get_vm(self.vm_name)
            if not vm:
                return False
            
            # This is a simplified implementation
            # In a real scenario, you'd modify the VM's boot order
            logger.info(f"Boot device set to {device} for VM {self.vm_name}")
            return True
        except Exception as e:
            logger.error(f"Error setting boot device: {e}")
            return False
    
    def get_system_info(self):
        """Get system information"""
        try:
            vm = self.vmware_client.get_vm(self.vm_name)
            if vm:
                return {
                    'system_guid': vm.config.instanceUuid if vm.config else 'unknown',
                    'system_type': 'Virtual Machine',
                    'manufacturer': 'VMware, Inc.',
                    'product_name': vm.config.guestFullName if vm.config else 'Unknown',
                    'serial_number': vm.config.instanceUuid if vm.config else 'unknown'
                }
            return {}
        except Exception as e:
            logger.error(f"Error getting system info: {e}")
            return {}
    
    def update_sensors(self):
        """Update sensor values from VMware"""
        try:
            vm = self.vmware_client.get_vm(self.vm_name)
            if vm and vm.runtime:
                # Update power state sensor
                power_state = vm.runtime.powerState
                self.sensors['power_state']['value'] = 1 if power_state == 'poweredOn' else 0
                
                # Simulate other sensor readings
                if vm.runtime.powerState == 'poweredOn':
                    self.sensors['temperature']['value'] = 35.0 + (hash(self.vm_name) % 20)
                    self.sensors['fan_speed']['value'] = 2000 + (hash(self.vm_name) % 1000)
                    self.sensors['voltage']['value'] = 12.0 + (hash(self.vm_name) % 2)
                else:
                    self.sensors['temperature']['value'] = 25.0
                    self.sensors['fan_speed']['value'] = 0
                    self.sensors['voltage']['value'] = 0.0
                    
        except Exception as e:
            logger.error(f"Error updating sensors: {e}")


class IPMIVMwareBridge:
    """
    Main bridge application that manages multiple BMC instances
    """
    
    def __init__(self, config_file):
        self.config_file = config_file
        self.config = self.load_config()
        self.bmc_instances = {}
        self.running = False
    
    def load_config(self):
        """Load configuration from JSON file"""
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            return config
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            sys.exit(1)
    
    def start_bmc_instance(self, vm_config):
        """Start a BMC instance for a VM"""
        try:
            vm_name = vm_config['vm_name']
            listen_port = vm_config['ipmi_port']
            listen_address = vm_config.get('ipmi_address', '0.0.0.0')
            
            bmc = VMwareBMC(
                vm_name=vm_name,
                vmware_config=self.config['vmware'],
                authdata={vm_config['ipmi_user']: vm_config['ipmi_password']},
                address=listen_address,
                port=listen_port
            )
            
            # Start the BMC in a separate thread
            thread = Thread(target=bmc.listen, daemon=True)
            thread.start()
            
            self.bmc_instances[vm_name] = {
                'bmc': bmc,
                'thread': thread,
                'config': vm_config
            }
            
            logger.info(f"Started BMC for VM {vm_name} on {listen_address}:{listen_port}")
            
        except Exception as e:
            logger.error(f"Error starting BMC instance: {e}")
    
    def start(self):
        """Start the bridge service"""
        logger.info("Starting IPMI VMware Bridge Service")
        
        # Start BMC instances for each configured VM
        for vm_config in self.config['vms']:
            self.start_bmc_instance(vm_config)
        
        self.running = True
        
        # Keep the main thread alive
        try:
            while self.running:
                time.sleep(1)
                # Update sensors periodically
                for instance in self.bmc_instances.values():
                    instance['bmc'].update_sensors()
                time.sleep(30)  # Update every 30 seconds
                
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
            self.stop()
    
    def stop(self):
        """Stop the bridge service"""
        logger.info("Stopping IPMI VMware Bridge Service")
        self.running = False
        
        # Stop all BMC instances
        for vm_name, instance in self.bmc_instances.items():
            try:
                instance['bmc'].poweroff = True
                logger.info(f"Stopped BMC for VM {vm_name}")
            except Exception as e:
                logger.error(f"Error stopping BMC for {vm_name}: {e}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='IPMI VMware Bridge Service')
    parser.add_argument('--config', '-c', required=True, 
                      help='Configuration file path')
    parser.add_argument('--daemon', '-d', action='store_true',
                      help='Run as daemon')
    parser.add_argument('--verbose', '-v', action='store_true',
                      help='Verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create and start the bridge
    bridge = IPMIVMwareBridge(args.config)
    
    if args.daemon:
        # In production, you'd use python-daemon here
        logger.info("Starting in daemon mode")
    
    try:
        bridge.start()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
