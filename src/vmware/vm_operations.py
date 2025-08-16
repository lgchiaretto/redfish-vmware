#!/usr/bin/env python3
"""
VMware VM Operations
Handles VM discovery, information retrieval, and basic operations.
"""

import logging
from pyVmomi import vim

logger = logging.getLogger(__name__)


class VMOperations:
    """VM operations management"""
    
    def __init__(self, connection):
        """
        Initialize VM operations
        
        Args:
            connection: VMwareConnection instance
        """
        self.connection = connection
        self.content = connection.get_content()
    
    def get_vm(self, vm_name):
        """
        Get VM object by name
        
        Args:
            vm_name: Name of the virtual machine
            
        Returns:
            VM object or None if not found
        """
        try:
            container = self.content.viewManager.CreateContainerView(
                self.content.rootFolder,
                [vim.VirtualMachine],
                True
            )
            
            for vm in container.view:
                if vm.name == vm_name:
                    container.Destroy()
                    return vm
            
            container.Destroy()
            logger.warning(f"VM '{vm_name}' not found")
            return None
            
        except Exception as e:
            logger.error(f"Error finding VM '{vm_name}': {e}")
            return None
    
    def list_vms(self):
        """
        List all virtual machines
        
        Returns:
            List of VM information dictionaries
        """
        try:
            container = self.content.viewManager.CreateContainerView(
                self.content.rootFolder,
                [vim.VirtualMachine],
                True
            )
            
            vms = []
            for vm in container.view:
                vm_info = {
                    'name': vm.name,
                    'power_state': vm.runtime.powerState,
                    'tools_status': str(vm.guest.toolsStatus) if vm.guest else 'toolsNotInstalled',
                    'guest_os': vm.config.guestFullName if vm.config else 'Unknown'
                }
                vms.append(vm_info)
            
            container.Destroy()
            logger.info(f"Found {len(vms)} VMs")
            return vms
            
        except Exception as e:
            logger.error(f"Error listing VMs: {e}")
            return []
    
    def get_vm_info(self, vm_name):
        """
        Get detailed VM information
        
        Args:
            vm_name: Name of the virtual machine
            
        Returns:
            Dictionary with VM information
        """
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                return None
            
            return {
                'name': vm.name,
                'power_state': vm.runtime.powerState,
                'tools_status': str(vm.guest.toolsStatus) if vm.guest else 'toolsNotInstalled',
                'guest_os': vm.config.guestFullName if vm.config else 'Unknown',
                'cpu_count': vm.config.hardware.numCPU if vm.config else 0,
                'memory_mb': vm.config.hardware.memoryMB if vm.config else 0,
                'guest_ip': vm.guest.ipAddress if vm.guest else None,
                'guest_hostname': vm.guest.hostName if vm.guest else None,
                'uuid': vm.config.uuid if vm.config else None,
                'instance_uuid': vm.config.instanceUuid if vm.config else None
            }
            
        except Exception as e:
            logger.error(f"Error getting VM info for '{vm_name}': {e}")
            return None
    
    def get_vm_power_state(self, vm_name):
        """
        Get VM power state
        
        Args:
            vm_name: Name of the virtual machine
            
        Returns:
            Power state string or None
        """
        try:
            vm = self.get_vm(vm_name)
            if vm:
                return vm.runtime.powerState
            return None
            
        except Exception as e:
            logger.error(f"Error getting power state for '{vm_name}': {e}")
            return None
