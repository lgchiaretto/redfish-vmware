#!/usr/bin/env python3
"""
VMware client to control VMs via vSphere API
"""

import logging
import ssl
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim
import atexit

class VMwareClient:
    def __init__(self, config):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.service_instance = None
        self.content = None
        
        # VMware settings
        self.vcenter_host = config.get('vmware', 'vcenter_host')
        self.username = config.get('vmware', 'username')
        self.password = config.get('vmware', 'password')
        self.port = config.getint('vmware', 'port', fallback=443)
        self.ignore_ssl = config.getboolean('vmware', 'ignore_ssl', fallback=True)
        
        self.connect()
    
    def connect(self):
        """Connect to vCenter"""
        try:
            self.logger.info(f"Connecting to vCenter: {self.vcenter_host}")
            
            # SSL configuration
            context = None
            if self.ignore_ssl:
                context = ssl._create_unverified_context()
            
            # Connect to vCenter
            self.service_instance = SmartConnect(
                host=self.vcenter_host,
                user=self.username,
                pwd=self.password,
                port=self.port,
                sslContext=context
            )
            
            self.content = self.service_instance.RetrieveContent()
            atexit.register(Disconnect, self.service_instance)
            
            self.logger.info("VMware connection established successfully")
            
        except Exception as e:
            self.logger.error(f"Error connecting to VMware: {e}")
            raise
    
    def test_connection(self):
        """Test connection by listing datacenters"""
        try:
            self.logger.info("Testing VMware connection...")
            
            # List datacenters
            datacenters = self.get_obj([vim.Datacenter])
            self.logger.info(f"Datacenters found: {len(datacenters)}")
            
            for dc in datacenters:
                self.logger.info(f"  - {dc.name}")
                
                # List VMs in datacenter
                vms = self.get_obj([vim.VirtualMachine], dc)
                self.logger.info(f"    VMs: {len(vms)}")
                
                for vm in vms[:5]:  # Show only first 5
                    power_state = vm.runtime.powerState
                    self.logger.info(f"      - {vm.name} ({power_state})")
                    
                if len(vms) > 5:
                    self.logger.info(f"      ... and {len(vms) - 5} more VMs")
            
            self.logger.info("Connection test completed successfully!")
            
        except Exception as e:
            self.logger.error(f"Error in connection test: {e}")
            raise
    
    def get_obj(self, vimtype, root=None):
        """
        Get VMware objects by type
        """
        if root is None:
            root = self.content.rootFolder
        
        container = self.content.viewManager.CreateContainerView(
            root, vimtype, True
        )
        
        return container.view
    
    def get_vm_by_name(self, vm_name):
        """Find VM by name"""
        try:
            vms = self.get_obj([vim.VirtualMachine])
            for vm in vms:
                if vm.name == vm_name:
                    return vm
            return None
        except Exception as e:
            self.logger.error(f"Error searching for VM {vm_name}: {e}")
            return None
    
    def power_on_vm(self, vm_name):
        """Power on a VM"""
        try:
            vm = self.get_vm_by_name(vm_name)
            if not vm:
                raise Exception(f"VM {vm_name} not found")
            
            if vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOn:
                self.logger.info(f"VM {vm_name} is already powered on")
                return True
            
            self.logger.info(f"Powering on VM {vm_name}...")
            task = vm.PowerOnVM_Task()
            self.wait_for_task(task)
            
            self.logger.info(f"VM {vm_name} powered on successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error powering on VM {vm_name}: {e}")
            return False
    
    def power_off_vm(self, vm_name):
        """Power off a VM"""
        try:
            vm = self.get_vm_by_name(vm_name)
            if not vm:
                raise Exception(f"VM {vm_name} not found")
            
            if vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOff:
                self.logger.info(f"VM {vm_name} is already powered off")
                return True
            
            self.logger.info(f"Powering off VM {vm_name}...")
            task = vm.PowerOffVM_Task()
            self.wait_for_task(task)
            
            self.logger.info(f"VM {vm_name} powered off successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error powering off VM {vm_name}: {e}")
            return False
    
    def reset_vm(self, vm_name):
        """Reset a VM"""
        try:
            vm = self.get_vm_by_name(vm_name)
            if not vm:
                raise Exception(f"VM {vm_name} not found")
            
            if vm.runtime.powerState != vim.VirtualMachinePowerState.poweredOn:
                self.logger.warning(f"VM {vm_name} is not powered on, powering on first...")
                return self.power_on_vm(vm_name)
            
            self.logger.info(f"Resetting VM {vm_name}...")
            task = vm.ResetVM_Task()
            self.wait_for_task(task)
            
            self.logger.info(f"VM {vm_name} reset successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error resetting VM {vm_name}: {e}")
            return False
    
    def get_vm_power_state(self, vm_name):
        """Get VM power state"""
        try:
            vm = self.get_vm_by_name(vm_name)
            if not vm:
                return None
            
            return vm.runtime.powerState
            
        except Exception as e:
            self.logger.error(f"Error getting VM {vm_name} state: {e}")
            return None
    
    def wait_for_task(self, task):
        """Wait for VMware task completion"""
        while task.info.state in [vim.TaskInfo.State.running, vim.TaskInfo.State.queued]:
            pass
        
        if task.info.state == vim.TaskInfo.State.success:
            return True
        else:
            raise Exception(f"Task failed: {task.info.error.msg}")
    
    def disconnect(self):
        """Disconnect from vCenter"""
        try:
            if self.service_instance:
                Disconnect(self.service_instance)
                self.logger.info("Disconnected from VMware")
        except Exception as e:
            self.logger.error(f"Error disconnecting from VMware: {e}")
    
    def mount_iso(self, vm_name, iso_path, datastore=None):
        """Mount ISO to VM"""
        try:
            vm = self.get_vm_by_name(vm_name)
            if not vm:
                raise Exception(f"VM {vm_name} not found")
            
            self.logger.info(f"Mounting ISO {iso_path} to VM {vm_name}")
            
            # Find CD/DVD device
            cdrom_device = None
            for device in vm.config.hardware.device:
                if isinstance(device, vim.vm.device.VirtualCdrom):
                    cdrom_device = device
                    break
            
            if not cdrom_device:
                # Add a CD/DVD device if none exists
                self.logger.info("No CD/DVD device found, adding one...")
                cdrom_device = self._add_cdrom_device(vm)
            
            # Configure the CD/DVD device to use the ISO
            cdrom_spec = vim.vm.device.VirtualDeviceSpec()
            cdrom_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
            cdrom_spec.device = cdrom_device
            
            # Set the ISO file as backing
            cdrom_spec.device.backing = vim.vm.device.VirtualCdrom.IsoBackingInfo()
            if datastore:
                cdrom_spec.device.backing.fileName = f"[{datastore}] {iso_path}"
            else:
                cdrom_spec.device.backing.fileName = iso_path
            
            # Connect the device
            cdrom_spec.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
            cdrom_spec.device.connectable.allowGuestControl = True
            cdrom_spec.device.connectable.connected = True
            cdrom_spec.device.connectable.startConnected = True
            
            # Apply the configuration
            config_spec = vim.vm.ConfigSpec()
            config_spec.deviceChange = [cdrom_spec]
            
            task = vm.ReconfigVM_Task(config_spec)
            self.wait_for_task(task)
            
            self.logger.info(f"ISO {iso_path} mounted successfully to VM {vm_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error mounting ISO to VM {vm_name}: {e}")
            return False
    
    def unmount_iso(self, vm_name):
        """Unmount ISO from VM"""
        try:
            vm = self.get_vm_by_name(vm_name)
            if not vm:
                raise Exception(f"VM {vm_name} not found")
            
            self.logger.info(f"Unmounting ISO from VM {vm_name}")
            
            # Find CD/DVD device
            cdrom_device = None
            for device in vm.config.hardware.device:
                if isinstance(device, vim.vm.device.VirtualCdrom):
                    cdrom_device = device
                    break
            
            if not cdrom_device:
                self.logger.warning(f"No CD/DVD device found in VM {vm_name}")
                return True
            
            # Configure the CD/DVD device to disconnect
            cdrom_spec = vim.vm.device.VirtualDeviceSpec()
            cdrom_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
            cdrom_spec.device = cdrom_device
            
            # Disconnect the device
            cdrom_spec.device.connectable.connected = False
            cdrom_spec.device.connectable.startConnected = False
            
            # Apply the configuration
            config_spec = vim.vm.ConfigSpec()
            config_spec.deviceChange = [cdrom_spec]
            
            task = vm.ReconfigVM_Task(config_spec)
            self.wait_for_task(task)
            
            self.logger.info(f"ISO unmounted successfully from VM {vm_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error unmounting ISO from VM {vm_name}: {e}")
            return False
    
    def set_boot_order(self, vm_name, boot_from_cdrom=True):
        """Set VM boot order (CD/DVD first or HDD first)"""
        try:
            vm = self.get_vm_by_name(vm_name)
            if not vm:
                raise Exception(f"VM {vm_name} not found")
            
            self.logger.info(f"Setting boot order for VM {vm_name} (CD/DVD first: {boot_from_cdrom})")
            
            # Create boot options
            boot_options = vim.vm.BootOptions()
            
            if boot_from_cdrom:
                # Boot from CD/DVD first, then hard disk
                boot_order = [
                    vim.vm.BootOptions.BootableCdromDevice(),
                    vim.vm.BootOptions.BootableDiskDevice()
                ]
            else:
                # Boot from hard disk first
                boot_order = [
                    vim.vm.BootOptions.BootableDiskDevice(),
                    vim.vm.BootOptions.BootableCdromDevice()
                ]
            
            boot_options.bootOrder = boot_order
            
            # Apply the configuration
            config_spec = vim.vm.ConfigSpec()
            config_spec.bootOptions = boot_options
            
            task = vm.ReconfigVM_Task(config_spec)
            self.wait_for_task(task)
            
            self.logger.info(f"Boot order set successfully for VM {vm_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error setting boot order for VM {vm_name}: {e}")
            return False
    
    def _add_cdrom_device(self, vm):
        """Add a CD/DVD device to VM"""
        try:
            # Find IDE controller
            ide_controller = None
            for device in vm.config.hardware.device:
                if isinstance(device, vim.vm.device.VirtualIDEController):
                    ide_controller = device
                    break
            
            if not ide_controller:
                raise Exception("No IDE controller found")
            
            # Create CD/DVD device
            cdrom_device = vim.vm.device.VirtualCdrom()
            cdrom_device.key = -1
            cdrom_device.controllerKey = ide_controller.key
            cdrom_device.unitNumber = 0
            
            # Set up backing (empty by default)
            cdrom_device.backing = vim.vm.device.VirtualCdrom.RemotePassthroughBackingInfo()
            cdrom_device.backing.exclusive = False
            
            # Set up connection info
            cdrom_device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
            cdrom_device.connectable.allowGuestControl = True
            cdrom_device.connectable.connected = False
            cdrom_device.connectable.startConnected = False
            
            # Create device spec
            cdrom_spec = vim.vm.device.VirtualDeviceSpec()
            cdrom_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
            cdrom_spec.device = cdrom_device
            
            # Apply the configuration
            config_spec = vim.vm.ConfigSpec()
            config_spec.deviceChange = [cdrom_spec]
            
            task = vm.ReconfigVM_Task(config_spec)
            self.wait_for_task(task)
            
            # Return the new device
            for device in vm.config.hardware.device:
                if isinstance(device, vim.vm.device.VirtualCdrom):
                    return device
            
            return cdrom_device
            
        except Exception as e:
            self.logger.error(f"Error adding CD/DVD device: {e}")
            raise
    
    def get_vm_info(self, vm_name):
        """Get detailed VM information including mounted ISO"""
        try:
            vm = self.get_vm_by_name(vm_name)
            if not vm:
                return None
            
            info = {
                'name': vm.name,
                'power_state': vm.runtime.powerState,
                'guest_os': vm.config.guestFullName,
                'memory_mb': vm.config.hardware.memoryMB,
                'num_cpu': vm.config.hardware.numCPU,
                'cdrom_devices': []
            }
            
            # Get CD/DVD device information
            for device in vm.config.hardware.device:
                if isinstance(device, vim.vm.device.VirtualCdrom):
                    cdrom_info = {
                        'key': device.key,
                        'connected': device.connectable.connected if device.connectable else False,
                        'start_connected': device.connectable.startConnected if device.connectable else False
                    }
                    
                    # Check if ISO is mounted
                    if hasattr(device.backing, 'fileName'):
                        cdrom_info['iso_file'] = device.backing.fileName
                    else:
                        cdrom_info['iso_file'] = None
                    
                    info['cdrom_devices'].append(cdrom_info)
            
            return info
            
        except Exception as e:
            self.logger.error(f"Error getting VM info for {vm_name}: {e}")
            return None
