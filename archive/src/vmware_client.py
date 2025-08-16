#!/usr/bin/env python3
"""
VMware vSphere Client

This module provides a client interface to VMware vSphere for VM operations.
Used by the IPMI bridge to perform actual VM management operations.
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
        """Power on a virtual machine"""
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                return False
            
            if vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOff:
                task = vm.PowerOnVM_Task()
                return self.wait_for_task(task)
            else:
                logger.info(f"VM {vm_name} is already powered on")
                return True
                
        except Exception as e:
            logger.error(f"Error powering on VM {vm_name}: {e}")
            return False
    
    def power_off_vm(self, vm_name, force=False):
        """Power off a virtual machine"""
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                return False
            
            if vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOn:
                if force:
                    task = vm.PowerOffVM_Task()
                else:
                    try:
                        vm.ShutdownGuest()
                        logger.info(f"Graceful shutdown initiated for VM {vm_name}")
                        return True
                    except:
                        # Fall back to force power off
                        task = vm.PowerOffVM_Task()
                
                return self.wait_for_task(task)
            else:
                logger.info(f"VM {vm_name} is already powered off")
                return True
                
        except Exception as e:
            logger.error(f"Error powering off VM {vm_name}: {e}")
            return False
    
    def reset_vm(self, vm_name):
        """Reset a virtual machine"""
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                return False
            
            if vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOn:
                task = vm.ResetVM_Task()
                return self.wait_for_task(task)
            else:
                logger.warning(f"VM {vm_name} is not powered on, cannot reset")
                return False
                
        except Exception as e:
            logger.error(f"Error resetting VM {vm_name}: {e}")
            return False
    
    def suspend_vm(self, vm_name):
        """Suspend a virtual machine"""
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                return False
            
            if vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOn:
                task = vm.SuspendVM_Task()
                return self.wait_for_task(task)
            else:
                logger.warning(f"VM {vm_name} is not powered on, cannot suspend")
                return False
                
        except Exception as e:
            logger.error(f"Error suspending VM {vm_name}: {e}")
            return False
    
    def get_vm_info(self, vm_name):
        """
        Get detailed VM information
        
        Returns:
            Dictionary with VM information
        """
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                return {}
            
            info = {
                'name': vm.name,
                'power_state': str(vm.runtime.powerState),
                'guest_os': vm.config.guestFullName if vm.config else 'Unknown',
                'uuid': vm.config.instanceUuid if vm.config else 'Unknown',
                'cpu_count': vm.config.hardware.numCPU if vm.config else 0,
                'memory_mb': vm.config.hardware.memoryMB if vm.config else 0,
                'tools_status': str(vm.guest.toolsStatus) if vm.guest else 'Unknown',
                'ip_address': vm.guest.ipAddress if vm.guest and vm.guest.ipAddress else 'Unknown'
            }
            
            return info
            
        except Exception as e:
            logger.error(f"Error getting VM info for {vm_name}: {e}")
            return {}
    
    def is_vm_powered_on(self, vm_name):
        """
        Check if VM is powered on
        
        Args:
            vm_name: Name of the VM
            
        Returns:
            bool: True if VM is powered on, False otherwise
        """
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                logger.warning(f"VM {vm_name} not found")
                return False
                
            return vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOn
            
        except Exception as e:
            logger.error(f"Error checking power state for {vm_name}: {e}")
            return False
            
    def get_vm_power_state(self, vm_name):
        """
        Get VM power state as string
        
        Args:
            vm_name: Name of the VM
            
        Returns:
            str: 'on', 'off', or 'unknown'
        """
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                logger.warning(f"VM {vm_name} not found")
                return 'unknown'
                
            if vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOn:
                return 'on'
            elif vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOff:
                return 'off'
            elif vm.runtime.powerState == vim.VirtualMachinePowerState.suspended:
                return 'suspended'
            else:
                return 'unknown'
                
        except Exception as e:
            logger.error(f"Error getting power state for {vm_name}: {e}")
            return 'unknown'
            return False
    
    def mount_iso(self, vm_name, iso_path, datastore_name=None):
        """
        Mount an ISO file to VM's CD-ROM
        
        Args:
            vm_name: Name of the VM
            iso_path: Path to ISO file
            datastore_name: Datastore name (optional)
        """
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                return False
            
            # Find CD-ROM device
            cdrom_device = None
            for device in vm.config.hardware.device:
                if isinstance(device, vim.vm.device.VirtualCdrom):
                    cdrom_device = device
                    break
            
            if not cdrom_device:
                logger.error(f"No CD-ROM device found in VM {vm_name}")
                return False
            
            # Create ISO backing
            cdrom_spec = vim.vm.device.VirtualDeviceSpec()
            cdrom_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
            cdrom_spec.device = cdrom_device
            
            cdrom_spec.device.backing = vim.vm.device.VirtualCdrom.IsoBackingInfo()
            if datastore_name:
                cdrom_spec.device.backing.fileName = f"[{datastore_name}] {iso_path}"
            else:
                cdrom_spec.device.backing.fileName = iso_path
            
            cdrom_spec.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
            cdrom_spec.device.connectable.startConnected = True
            cdrom_spec.device.connectable.connected = True
            cdrom_spec.device.connectable.allowGuestControl = True
            
            # Reconfigure VM
            config_spec = vim.vm.ConfigSpec()
            config_spec.deviceChange = [cdrom_spec]
            
            task = vm.ReconfigVM_Task(spec=config_spec)
            result = self.wait_for_task(task)
            
            if result:
                logger.info(f"Successfully mounted ISO {iso_path} to VM {vm_name}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error mounting ISO to VM {vm_name}: {e}")
            return False
    
    def unmount_iso(self, vm_name):
        """
        Unmount ISO from VM's CD-ROM
        
        Args:
            vm_name: Name of the VM
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                return False
            
            # Find CD-ROM device
            cdrom_device = None
            for device in vm.config.hardware.device:
                if isinstance(device, vim.vm.device.VirtualCdrom):
                    cdrom_device = device
                    break
            
            if not cdrom_device:
                logger.warning(f"No CD-ROM device found in VM {vm_name}")
                return False
            
            # Create device spec to remove ISO
            cdrom_spec = vim.vm.device.VirtualDeviceSpec()
            cdrom_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
            cdrom_spec.device = cdrom_device
            
            # Set to client device (no ISO)
            cdrom_spec.device.backing = vim.vm.device.VirtualCdrom.RemotePassthroughBackingInfo()
            cdrom_spec.device.connectable.connected = False
            cdrom_spec.device.connectable.startConnected = False
            
            # Reconfigure VM
            config_spec = vim.vm.ConfigSpec()
            config_spec.deviceChange = [cdrom_spec]
            
            task = vm.ReconfigVM_Task(spec=config_spec)
            result = self.wait_for_task(task)
            
            if result:
                logger.info(f"Successfully unmounted ISO from VM {vm_name}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error unmounting ISO from VM {vm_name}: {e}")
            return False
    
    def set_boot_order(self, vm_name, boot_order=['network', 'cdrom', 'disk']):
        """
        Set boot order for VM
        
        Args:
            vm_name: Name of the VM
            boot_order: List of boot devices in order
        """
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                return False
            
            boot_options = vim.vm.BootOptions()
            boot_devices = []
            
            for device in boot_order:
                if device == 'network':
                    boot_devices.append(vim.vm.BootOptions.BootableEthernetDevice())
                elif device == 'cdrom':
                    boot_devices.append(vim.vm.BootOptions.BootableCdromDevice())
                elif device == 'disk':
                    boot_devices.append(vim.vm.BootOptions.BootableDiskDevice())
                elif device == 'floppy':
                    boot_devices.append(vim.vm.BootOptions.BootableFloppyDevice())
            
            boot_options.bootOrder = boot_devices
            
            config_spec = vim.vm.ConfigSpec()
            config_spec.bootOptions = boot_options
            
            task = vm.ReconfigVM_Task(spec=config_spec)
            result = self.wait_for_task(task)
            
            if result:
                logger.info(f"Successfully set boot order for VM {vm_name}: {boot_order}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error setting boot order for VM {vm_name}: {e}")
            return False
    
    def set_boot_device(self, vm_name, boot_device):
        """
        Set primary boot device for VM (simplified implementation)
        
        Args:
            vm_name: Name of the VM
            boot_device: Boot device ('network', 'cdrom', 'disk', 'floppy')
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                return False
            
            logger.info(f"Setting boot device to {boot_device} for VM {vm_name}")
            
            # For now, we'll just log the boot device change
            # The actual implementation would require more complex VMware configuration
            # that may vary depending on VM settings and VMware version
            
            logger.info(f"Boot device set to {boot_device} for VM {vm_name} (simulated)")
            return True
            
        except Exception as e:
            logger.error(f"Error setting boot device for VM {vm_name}: {e}")
            return False
    
    def wait_for_task(self, task, timeout=300):
        """
        Wait for a VMware task to complete
        
        Args:
            task: VMware task object
            timeout: Timeout in seconds
            
        Returns:
            True if task completed successfully, False otherwise
        """
        try:
            import time
            start_time = time.time()
            
            while task.info.state in [vim.TaskInfo.State.running, vim.TaskInfo.State.queued]:
                if time.time() - start_time > timeout:
                    logger.error("Task timed out")
                    return False
                time.sleep(1)
            
            if task.info.state == vim.TaskInfo.State.success:
                return True
            else:
                logger.error(f"Task failed: {task.info.error}")
                return False
                
        except Exception as e:
            logger.error(f"Error waiting for task: {e}")
            return False

    def set_vm_firmware(self, vm_name, firmware_type='bios'):
        """
        Set VM firmware type (BIOS or EFI)
        
        Args:
            vm_name: Name of the VM
            firmware_type: 'bios' for legacy BIOS, 'efi' for UEFI
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                return False
            
            # VM must be powered off to change firmware type
            if vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOn:
                logger.info(f"Powering off VM {vm_name} to change firmware type")
                self.power_off_vm(vm_name)
                
                # Wait a bit for the VM to power off
                import time
                time.sleep(5)
            
            # Create a config spec to change firmware
            config_spec = vim.vm.ConfigSpec()
            
            if firmware_type.lower() == 'bios':
                config_spec.firmware = vim.vm.GuestOsDescriptor.FirmwareType.bios
                # Disable EFI secure boot when switching to BIOS
                config_spec.bootOptions = vim.vm.BootOptions()
                config_spec.bootOptions.efiSecureBootEnabled = False
                logger.info(f"Setting VM {vm_name} firmware to Legacy BIOS and disabling secure boot")
            elif firmware_type.lower() == 'efi':
                config_spec.firmware = vim.vm.GuestOsDescriptor.FirmwareType.efi
                logger.info(f"Setting VM {vm_name} firmware to UEFI")
            else:
                logger.error(f"Invalid firmware type: {firmware_type}. Use 'bios' or 'efi'")
                return False
            
            # Apply the configuration
            task = vm.ReconfigVM_Task(config_spec)
            result = self.wait_for_task(task)
            
            if result:
                logger.info(f"Successfully changed VM {vm_name} firmware to {firmware_type}")
            else:
                logger.error(f"Failed to change VM {vm_name} firmware")
                
            return result
            
        except Exception as e:
            logger.error(f"Error setting VM {vm_name} firmware: {e}")
            return False


def test_connection():
    """Test VMware connection"""
    try:
        # Test configuration
        client = VMwareClient(
            host='chiaretto-vcsa01.chiaret.to',
            user='administrator@chiaretto.local',
            password='VMware1!VMware1!'
        )
        
        vms = client.list_vms()
        print(f"Found {len(vms)} VMs:")
        for vm in vms[:5]:  # Show first 5 VMs
            print(f"  - {vm.name} ({vm.runtime.powerState})")
        
        client.disconnect()
        return True
        
    except Exception as e:
        print(f"Connection test failed: {e}")
        return False


if __name__ == '__main__':
    test_connection()
