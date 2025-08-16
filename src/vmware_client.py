#!/usr/bin/env python3
"""
VMware vSphere Client

This module provides a client interface to VMware vSphere for VM operations.
Used by the Redfish server to perform actual VM management operations.
"""

import ssl
import logging
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim
import atexit

logger = logging.getLogger(__name__)


class VMwareClient:
    """
    VMware vSphere client for VM operations
    """
    
    def __init__(self, host, user, password, port=443, disable_ssl_verification=None, disable_ssl=None):
        """
        Initialize VMware client
        
        Args:
            host: vCenter/ESXi host
            user: Username
            password: Password
            port: Connection port
            disable_ssl_verification: Disable SSL verification (deprecated)
            disable_ssl: Disable SSL verification (new name)
        """
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        
        # Handle both parameter names for backward compatibility
        if disable_ssl is not None:
            self.disable_ssl_verification = disable_ssl
        elif disable_ssl_verification is not None:
            self.disable_ssl_verification = disable_ssl_verification
        else:
            self.disable_ssl_verification = True
            
        self.service_instance = None
        self.content = None
        
        self.connect()
    
    def connect(self):
        """Connect to VMware vSphere"""
        try:
            # Disable SSL verification if requested
            if self.disable_ssl_verification:
                context = ssl._create_unverified_context()
            else:
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
            
            # Connect to vSphere
            self.service_instance = SmartConnect(
                host=self.host,
                user=self.user,
                pwd=self.password,
                port=self.port,
                sslContext=context
            )
            
            if self.service_instance:
                self.content = self.service_instance.RetrieveContent()
                logger.info(f"Successfully connected to {self.host}")
                
                # Register disconnect function
                atexit.register(self.disconnect)
            else:
                raise Exception("Failed to connect to vSphere")
                
        except Exception as e:
            logger.error(f"Error connecting to VMware: {e}")
            raise
    
    def disconnect(self):
        """Disconnect from VMware vSphere"""
        try:
            if self.service_instance:
                Disconnect(self.service_instance)
                logger.info("Disconnected from VMware")
        except Exception as e:
            logger.error(f"Error disconnecting: {e}")
    
    def get_vm(self, vm_name):
        """
        Get VM object by name
        
        Args:
            vm_name: Name of the virtual machine
            
        Returns:
            VM object or None if not found
        """
        try:
            if not self.content:
                self.connect()
            
            # Get all VMs
            container = self.content.viewManager.CreateContainerView(
                self.content.rootFolder, [vim.VirtualMachine], True
            )
            
            for vm in container.view:
                if vm.name == vm_name:
                    container.Destroy()
                    return vm
            
            container.Destroy()
            logger.warning(f"VM {vm_name} not found")
            return None
            
        except Exception as e:
            logger.error(f"Error getting VM {vm_name}: {e}")
            return None
    
    def list_vms(self):
        """
        List all virtual machines
        
        Returns:
            List of VM objects
        """
        try:
            if not self.content:
                self.connect()
            
            container = self.content.viewManager.CreateContainerView(
                self.content.rootFolder, [vim.VirtualMachine], True
            )
            
            vms = list(container.view)
            container.Destroy()
            return vms
            
        except Exception as e:
            logger.error(f"Error listing VMs: {e}")
            return []
    
    def power_on_vm(self, vm_name):
        """
        Power on a virtual machine
        
        Args:
            vm_name: Name of the virtual machine
            
        Returns:
            True if successful, False otherwise
        """
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                logger.error(f"VM {vm_name} not found")
                return False
            
            if vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOn:
                logger.info(f"VM {vm_name} is already powered on")
                return True
            
            task = vm.PowerOnVM_Task()
            self._wait_for_task(task)
            
            logger.info(f"VM {vm_name} powered on successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error powering on VM {vm_name}: {e}")
            return False
    
    def power_off_vm(self, vm_name):
        """
        Power off a virtual machine
        
        Args:
            vm_name: Name of the virtual machine
            
        Returns:
            True if successful, False otherwise
        """
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                logger.error(f"VM {vm_name} not found")
                return False
            
            if vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOff:
                logger.info(f"VM {vm_name} is already powered off")
                return True
            
            task = vm.PowerOffVM_Task()
            self._wait_for_task(task)
            
            logger.info(f"VM {vm_name} powered off successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error powering off VM {vm_name}: {e}")
            return False
    
    def reset_vm(self, vm_name):
        """
        Reset a virtual machine
        
        Args:
            vm_name: Name of the virtual machine
            
        Returns:
            True if successful, False otherwise
        """
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                logger.error(f"VM {vm_name} not found")
                return False
            
            if vm.runtime.powerState != vim.VirtualMachinePowerState.poweredOn:
                logger.warning(f"VM {vm_name} is not powered on, cannot reset")
                return False
            
            task = vm.ResetVM_Task()
            self._wait_for_task(task)
            
            logger.info(f"VM {vm_name} reset successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error resetting VM {vm_name}: {e}")
            return False
    
    def shutdown_vm(self, vm_name):
        """
        Gracefully shutdown a virtual machine (requires VMware Tools)
        
        Args:
            vm_name: Name of the virtual machine
            
        Returns:
            True if successful, False otherwise
        """
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                logger.error(f"VM {vm_name} not found")
                return False
            
            if vm.runtime.powerState != vim.VirtualMachinePowerState.poweredOn:
                logger.info(f"VM {vm_name} is already powered off")
                return True
            
            # Check if VMware Tools is running
            if vm.summary.guest.toolsStatus != 'toolsOk':
                logger.warning(f"VMware Tools not running on {vm_name}, falling back to power off")
                return self.power_off_vm(vm_name)
            
            vm.ShutdownGuest()
            logger.info(f"VM {vm_name} shutdown initiated (graceful)")
            
            # Wait a bit for shutdown to complete
            import time
            for _ in range(30):  # Wait up to 30 seconds
                vm_updated = self.get_vm(vm_name)
                if vm_updated and vm_updated.runtime.powerState == vim.VirtualMachinePowerState.poweredOff:
                    logger.info(f"VM {vm_name} shutdown completed")
                    return True
                time.sleep(1)
            
            logger.warning(f"VM {vm_name} graceful shutdown timed out, forcing power off")
            return self.power_off_vm(vm_name)
            
        except Exception as e:
            logger.error(f"Error shutting down VM {vm_name}: {e}")
            return False
    
    def restart_vm(self, vm_name):
        """
        Gracefully restart a virtual machine (requires VMware Tools)
        
        Args:
            vm_name: Name of the virtual machine
            
        Returns:
            True if successful, False otherwise
        """
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                logger.error(f"VM {vm_name} not found")
                return False
            
            if vm.runtime.powerState != vim.VirtualMachinePowerState.poweredOn:
                logger.info(f"VM {vm_name} is powered off, powering on instead")
                return self.power_on_vm(vm_name)
            
            # Check if VMware Tools is running
            if vm.summary.guest.toolsStatus != 'toolsOk':
                logger.warning(f"VMware Tools not running on {vm_name}, falling back to reset")
                return self.reset_vm(vm_name)
            
            vm.RebootGuest()
            logger.info(f"VM {vm_name} restart initiated (graceful)")
            return True
            
        except Exception as e:
            logger.error(f"Error restarting VM {vm_name}: {e}")
            return False
    
    def get_vm_power_state(self, vm_name):
        """
        Get the power state of a virtual machine
        
        Args:
            vm_name: Name of the virtual machine
            
        Returns:
            Power state string or None if error
        """
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                return None
            
            return vm.runtime.powerState
            
        except Exception as e:
            logger.error(f"Error getting power state for VM {vm_name}: {e}")
            return None
    
    def get_vm_info(self, vm_name):
        """
        Get detailed information about a virtual machine
        
        Args:
            vm_name: Name of the virtual machine
            
        Returns:
            Dictionary with VM information or None if error
        """
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                return None
            
            info = {
                'name': vm.name,
                'power_state': str(vm.runtime.powerState),
                'guest_os': vm.config.guestFullName if vm.config else 'Unknown',
                'memory_mb': vm.config.hardware.memoryMB if vm.config else 0,
                'num_cpu': vm.config.hardware.numCPU if vm.config else 0,
                'guest_tools_status': str(vm.summary.guest.toolsStatus),
                'guest_ip': vm.summary.guest.ipAddress,
                'guest_hostname': vm.summary.guest.hostName,
                'uuid': vm.config.uuid if vm.config else None
            }
            
            return info
            
        except Exception as e:
            logger.error(f"Error getting VM info for {vm_name}: {e}")
            return None
    
    def set_vm_boot_order(self, vm_name, boot_order):
        """
        Set the boot order for a virtual machine
        
        Args:
            vm_name: Name of the virtual machine
            boot_order: List of boot devices ['disk', 'cdrom', 'network']
            
        Returns:
            True if successful, False otherwise
        """
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                logger.error(f"VM {vm_name} not found")
                return False
            
            # Create boot options
            boot_options = []
            for device in boot_order:
                if device.lower() == 'disk':
                    boot_options.append(vim.vm.BootOptions.BootableDiskDevice())
                elif device.lower() == 'cdrom':
                    boot_options.append(vim.vm.BootOptions.BootableCdromDevice())
                elif device.lower() == 'network':
                    boot_options.append(vim.vm.BootOptions.BootableEthernetDevice())
            
            # Configure boot options
            boot_config = vim.vm.BootOptions()
            boot_config.bootOrder = boot_options
            
            # Create VM config spec
            spec = vim.vm.ConfigSpec()
            spec.bootOptions = boot_config
            
            # Apply configuration
            task = vm.ReconfigVM_Task(spec)
            self._wait_for_task(task)
            
            logger.info(f"Boot order set for VM {vm_name}: {boot_order}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting boot order for VM {vm_name}: {e}")
            return False
    
    def mount_iso(self, vm_name, iso_path):
        """
        Mount an ISO file to a virtual machine's CD/DVD drive
        
        Args:
            vm_name: Name of the virtual machine
            iso_path: Path to the ISO file on the datastore
            
        Returns:
            True if successful, False otherwise
        """
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                logger.error(f"VM {vm_name} not found")
                return False
            
            # Find CD/DVD drive
            cd_drive = None
            for device in vm.config.hardware.device:
                if isinstance(device, vim.vm.device.VirtualCdrom):
                    cd_drive = device
                    break
            
            if not cd_drive:
                logger.error(f"No CD/DVD drive found in VM {vm_name}")
                return False
            
            # Configure ISO backing
            cdrom_spec = vim.vm.device.VirtualDeviceSpec()
            cdrom_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
            cdrom_spec.device = cd_drive
            
            # Set ISO file as backing
            cdrom_spec.device.backing = vim.vm.device.VirtualCdrom.IsoBackingInfo()
            cdrom_spec.device.backing.fileName = iso_path
            cdrom_spec.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
            cdrom_spec.device.connectable.connected = True
            cdrom_spec.device.connectable.startConnected = True
            
            # Apply changes
            spec = vim.vm.ConfigSpec()
            spec.deviceChange = [cdrom_spec]
            
            task = vm.ReconfigVM_Task(spec)
            self._wait_for_task(task)
            
            logger.info(f"ISO {iso_path} mounted to VM {vm_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error mounting ISO to VM {vm_name}: {e}")
            return False
    
    def unmount_iso(self, vm_name):
        """
        Unmount ISO from a virtual machine's CD/DVD drive
        
        Args:
            vm_name: Name of the virtual machine
            
        Returns:
            True if successful, False otherwise
        """
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                logger.error(f"VM {vm_name} not found")
                return False
            
            # Find CD/DVD drive
            cd_drive = None
            for device in vm.config.hardware.device:
                if isinstance(device, vim.vm.device.VirtualCdrom):
                    cd_drive = device
                    break
            
            if not cd_drive:
                logger.error(f"No CD/DVD drive found in VM {vm_name}")
                return False
            
            # Configure device spec to disconnect
            cdrom_spec = vim.vm.device.VirtualDeviceSpec()
            cdrom_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
            cdrom_spec.device = cd_drive
            
            # Disconnect the device
            cdrom_spec.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
            cdrom_spec.device.connectable.connected = False
            cdrom_spec.device.connectable.startConnected = False
            
            # Apply changes
            spec = vim.vm.ConfigSpec()
            spec.deviceChange = [cdrom_spec]
            
            task = vm.ReconfigVM_Task(spec)
            self._wait_for_task(task)
            
            logger.info(f"ISO unmounted from VM {vm_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error unmounting ISO from VM {vm_name}: {e}")
            return False
    
    def _wait_for_task(self, task):
        """
        Wait for a VMware task to complete
        
        Args:
            task: VMware task object
            
        Returns:
            Task result
        """
        while task.info.state in [vim.TaskInfo.State.running, vim.TaskInfo.State.queued]:
            import time
            time.sleep(0.1)
        
        if task.info.state == vim.TaskInfo.State.success:
            return task.info.result
        else:
            raise Exception(f"Task failed: {task.info.error}")
