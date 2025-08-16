#!/usr/bin/env python3
"""
VMware Virtual Media Operations
Handles ISO mounting, boot order, and virtual media operations.
"""

import logging
from pyVmomi import vim

logger = logging.getLogger(__name__)


class MediaOperations:
    """Virtual media and boot operations"""
    
    def __init__(self, connection, vm_operations):
        """
        Initialize media operations
        
        Args:
            connection: VMwareConnection instance
            vm_operations: VMOperations instance
        """
        self.connection = connection
        self.vm_operations = vm_operations
    
    def set_vm_boot_order(self, vm_name, boot_order):
        """
        Set VM boot order
        
        Args:
            vm_name: Name of the virtual machine
            boot_order: List of boot devices ['cdrom', 'disk', 'network']
            
        Returns:
            True if successful, False otherwise
        """
        try:
            vm = self.vm_operations.get_vm(vm_name)
            if not vm:
                logger.error(f"VM '{vm_name}' not found")
                return False
            
            logger.info(f"Setting boot order for VM '{vm_name}': {boot_order}")
            
            # Create boot options
            boot_options = []
            for device in boot_order:
                if device.lower() == 'cdrom':
                    boot_options.append(vim.vm.BootOptions.BootableCdromDevice())
                elif device.lower() == 'disk':
                    boot_options.append(vim.vm.BootOptions.BootableDiskDevice())
                elif device.lower() == 'network':
                    boot_options.append(vim.vm.BootOptions.BootableEthernetDevice())
            
            # Configure boot options
            boot_spec = vim.vm.BootOptions()
            boot_spec.bootOrder = boot_options
            
            config_spec = vim.vm.ConfigSpec()
            config_spec.bootOptions = boot_spec
            
            task = vm.Reconfigure(config_spec)
            result = self._wait_for_task(task)
            
            if result:
                logger.info(f"Successfully set boot order for VM '{vm_name}'")
            else:
                logger.error(f"Failed to set boot order for VM '{vm_name}'")
            
            return result
            
        except Exception as e:
            logger.error(f"Error setting boot order for VM '{vm_name}': {e}")
            return False
    
    def mount_iso(self, vm_name, iso_path):
        """
        Mount ISO to VM's CD/DVD drive
        
        Args:
            vm_name: Name of the virtual machine
            iso_path: Path to the ISO file on the datastore
            
        Returns:
            True if successful, False otherwise
        """
        try:
            vm = self.vm_operations.get_vm(vm_name)
            if not vm:
                logger.error(f"VM '{vm_name}' not found")
                return False
            
            logger.info(f"Mounting ISO '{iso_path}' to VM '{vm_name}'")
            
            # Find CD/DVD device
            cdrom_device = None
            for device in vm.config.hardware.device:
                if isinstance(device, vim.vm.device.VirtualCdrom):
                    cdrom_device = device
                    break
            
            if not cdrom_device:
                logger.error(f"No CD/DVD device found for VM '{vm_name}'")
                return False
            
            # Configure CD/DVD device to use ISO
            cdrom_spec = vim.vm.device.VirtualDeviceSpec()
            cdrom_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
            cdrom_spec.device = cdrom_device
            cdrom_spec.device.backing = vim.vm.device.VirtualCdrom.IsoBackingInfo()
            cdrom_spec.device.backing.fileName = iso_path
            cdrom_spec.device.connectable = vim.vm.device.VirtualDevice.ConnectableDevice()
            cdrom_spec.device.connectable.connected = True
            cdrom_spec.device.connectable.startConnected = True
            
            config_spec = vim.vm.ConfigSpec()
            config_spec.deviceChange = [cdrom_spec]
            
            task = vm.Reconfigure(config_spec)
            result = self._wait_for_task(task)
            
            if result:
                logger.info(f"Successfully mounted ISO '{iso_path}' to VM '{vm_name}'")
            else:
                logger.error(f"Failed to mount ISO '{iso_path}' to VM '{vm_name}'")
            
            return result
            
        except Exception as e:
            logger.error(f"Error mounting ISO to VM '{vm_name}': {e}")
            return False
    
    def unmount_iso(self, vm_name):
        """
        Unmount ISO from VM's CD/DVD drive
        
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
            
            logger.info(f"Unmounting ISO from VM '{vm_name}'")
            
            # Find CD/DVD device
            cdrom_device = None
            for device in vm.config.hardware.device:
                if isinstance(device, vim.vm.device.VirtualCdrom):
                    cdrom_device = device
                    break
            
            if not cdrom_device:
                logger.error(f"No CD/DVD device found for VM '{vm_name}'")
                return False
            
            # Configure CD/DVD device to disconnect
            cdrom_spec = vim.vm.device.VirtualDeviceSpec()
            cdrom_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
            cdrom_spec.device = cdrom_device
            cdrom_spec.device.backing = vim.vm.device.VirtualCdrom.RemotePassthroughBackingInfo()
            cdrom_spec.device.connectable = vim.vm.device.VirtualDevice.ConnectableDevice()
            cdrom_spec.device.connectable.connected = False
            cdrom_spec.device.connectable.startConnected = False
            
            config_spec = vim.vm.ConfigSpec()
            config_spec.deviceChange = [cdrom_spec]
            
            task = vm.Reconfigure(config_spec)
            result = self._wait_for_task(task)
            
            if result:
                logger.info(f"Successfully unmounted ISO from VM '{vm_name}'")
            else:
                logger.error(f"Failed to unmount ISO from VM '{vm_name}'")
            
            return result
            
        except Exception as e:
            logger.error(f"Error unmounting ISO from VM '{vm_name}': {e}")
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
            import time
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
