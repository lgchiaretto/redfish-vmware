#!/usr/bin/env python3
"""
VMware Power Operations
Handles VM power management operations.
"""

import logging
import time

logger = logging.getLogger(__name__)


class PowerOperations:
    """VM power management operations"""
    
    def __init__(self, connection, vm_operations):
        """
        Initialize power operations
        
        Args:
            connection: VMwareConnection instance
            vm_operations: VMOperations instance
        """
        self.connection = connection
        self.vm_operations = vm_operations
    
    def power_on_vm(self, vm_name):
        """
        Power on a virtual machine
        
        Args:
            vm_name: Name of the virtual machine
            
        Returns:
            True if successful, False otherwise
        """
        try:
            vm = self.vm_operations.get_vm(vm_name)
            if not vm:
                logger.error(f"VM '{vm_name}' not found")
                return False
            
            if vm.runtime.powerState == 'poweredOn':
                logger.info(f"VM '{vm_name}' is already powered on")
                return True
            
            logger.info(f"Powering on VM '{vm_name}'")
            task = vm.PowerOn()
            result = self._wait_for_task(task)
            
            if result:
                logger.info(f"Successfully powered on VM '{vm_name}'")
            else:
                logger.error(f"Failed to power on VM '{vm_name}'")
            
            return result
            
        except Exception as e:
            logger.error(f"Error powering on VM '{vm_name}': {e}")
            return False
    
    def power_off_vm(self, vm_name):
        """
        Power off a virtual machine (hard power off)
        
        Args:
            vm_name: Name of the virtual machine
            
        Returns:
            True if successful, False otherwise
        """
        try:
            vm = self.vm_operations.get_vm(vm_name)
            if not vm:
                logger.error(f"VM '{vm_name}' not found")
                return False
            
            if vm.runtime.powerState == 'poweredOff':
                logger.info(f"VM '{vm_name}' is already powered off")
                return True
            
            logger.info(f"Powering off VM '{vm_name}'")
            task = vm.PowerOff()
            result = self._wait_for_task(task)
            
            if result:
                logger.info(f"Successfully powered off VM '{vm_name}'")
            else:
                logger.error(f"Failed to power off VM '{vm_name}'")
            
            return result
            
        except Exception as e:
            logger.error(f"Error powering off VM '{vm_name}': {e}")
            return False
    
    def reset_vm(self, vm_name):
        """
        Reset a virtual machine (hard reset)
        
        Args:
            vm_name: Name of the virtual machine
            
        Returns:
            True if successful, False otherwise
        """
        try:
            vm = self.vm_operations.get_vm(vm_name)
            if not vm:
                logger.error(f"VM '{vm_name}' not found")
                return False
            
            if vm.runtime.powerState == 'poweredOff':
                logger.warning(f"VM '{vm_name}' is powered off, cannot reset")
                return False
            
            logger.info(f"Resetting VM '{vm_name}'")
            task = vm.Reset()
            result = self._wait_for_task(task)
            
            if result:
                logger.info(f"Successfully reset VM '{vm_name}'")
            else:
                logger.error(f"Failed to reset VM '{vm_name}'")
            
            return result
            
        except Exception as e:
            logger.error(f"Error resetting VM '{vm_name}': {e}")
            return False
    
    def shutdown_vm(self, vm_name):
        """
        Gracefully shutdown a virtual machine using VMware Tools
        
        Args:
            vm_name: Name of the virtual machine
            
        Returns:
            True if successful, False otherwise
        """
        try:
            vm = self.vm_operations.get_vm(vm_name)
            if not vm:
                logger.error(f"VM '{vm_name}' not found")
                return False
            
            if vm.runtime.powerState == 'poweredOff':
                logger.info(f"VM '{vm_name}' is already powered off")
                return True
            
            # Check if VMware Tools is available
            if not vm.guest or vm.guest.toolsStatus not in ['toolsOk', 'toolsOld']:
                logger.warning(f"VMware Tools not available for '{vm_name}', using power off instead")
                return self.power_off_vm(vm_name)
            
            logger.info(f"Gracefully shutting down VM '{vm_name}'")
            vm.ShutdownGuest()
            
            # Wait for shutdown to complete (up to 60 seconds)
            for i in range(60):
                time.sleep(1)
                vm_info = self.vm_operations.get_vm(vm_name)
                if vm_info and vm_info.runtime.powerState == 'poweredOff':
                    logger.info(f"Successfully shutdown VM '{vm_name}'")
                    return True
            
            # If graceful shutdown didn't work, force power off
            logger.warning(f"Graceful shutdown timed out for '{vm_name}', forcing power off")
            return self.power_off_vm(vm_name)
            
        except Exception as e:
            logger.error(f"Error shutting down VM '{vm_name}': {e}")
            return False
    
    def restart_vm(self, vm_name):
        """
        Gracefully restart a virtual machine using VMware Tools
        
        Args:
            vm_name: Name of the virtual machine
            
        Returns:
            True if successful, False otherwise
        """
        try:
            vm = self.vm_operations.get_vm(vm_name)
            if not vm:
                logger.error(f"VM '{vm_name}' not found")
                return False
            
            if vm.runtime.powerState == 'poweredOff':
                logger.info(f"VM '{vm_name}' is powered off, powering on instead")
                return self.power_on_vm(vm_name)
            
            # Check if VMware Tools is available
            if not vm.guest or vm.guest.toolsStatus not in ['toolsOk', 'toolsOld']:
                logger.warning(f"VMware Tools not available for '{vm_name}', using reset instead")
                return self.reset_vm(vm_name)
            
            logger.info(f"Gracefully restarting VM '{vm_name}'")
            vm.RebootGuest()
            
            # Wait a moment for the restart to begin
            time.sleep(5)
            
            # Wait for the VM to come back online (up to 120 seconds)
            for i in range(120):
                time.sleep(1)
                vm_current = self.vm_operations.get_vm(vm_name)
                if (vm_current and 
                    vm_current.runtime.powerState == 'poweredOn' and 
                    vm_current.guest and 
                    vm_current.guest.toolsStatus in ['toolsOk', 'toolsOld']):
                    logger.info(f"Successfully restarted VM '{vm_name}'")
                    return True
            
            logger.warning(f"Restart verification timed out for '{vm_name}', but command was sent")
            return True
            
        except Exception as e:
            logger.error(f"Error restarting VM '{vm_name}': {e}")
            return False
    
    def _wait_for_task(self, task):
        """
        Wait for a vCenter task to complete
        
        Args:
            task: Task object
            
        Returns:
            True if task completed successfully, False otherwise
        """
        try:
            while task.info.state in ['running', 'queued']:
                time.sleep(1)
            
            if task.info.state == 'success':
                return True
            else:
                logger.error(f"Task failed: {task.info.error}")
                return False
                
        except Exception as e:
            logger.error(f"Error waiting for task: {e}")
            return False
