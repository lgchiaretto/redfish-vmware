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
    
    @property
    def content(self):
        """Always return the live content reference so reconnects are picked up."""
        return self.connection.content

    def get_vm(self, vm_name):
        """
        Get VM object by name
        
        Args:
            vm_name: Name of the virtual machine
            
        Returns:
            VM object or None if not found
        """
        try:
            content = self.connection.content
            container = content.viewManager.CreateContainerView(
                content.rootFolder,
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
            
        except vim.fault.NotAuthenticated:
            # Re-raise so the vmware_client decorator can reconnect and retry
            raise
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
            content = self.connection.content
            container = content.viewManager.CreateContainerView(
                content.rootFolder,
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
            
        except vim.fault.NotAuthenticated:
            raise
        except Exception as e:
            logger.error(f"Error listing VMs: {e}")
            return []
    
    def _collect_nics(self, vm):
        """Collect virtual NIC details from a VM hardware configuration."""
        nics = []
        if not vm.config or not vm.config.hardware:
            return nics

        for device in vm.config.hardware.device:
            if not isinstance(device, vim.vm.device.VirtualEthernetCard):
                continue

            mac = getattr(device, 'macAddress', None)
            if not mac:
                continue

            nic_type = type(device).__name__
            connected = False
            if device.connectable:
                connected = bool(device.connectable.connected)

            nics.append({
                'mac': mac.upper(),
                'label': device.deviceInfo.label if device.deviceInfo else f'Network adapter {len(nics) + 1}',
                'connected': connected,
                'type': nic_type,
            })

        return nics

    def _collect_disks(self, vm):
        """Collect virtual disk details from a VM hardware configuration."""
        disks = []
        if not vm.config or not vm.config.hardware:
            return disks

        for device in vm.config.hardware.device:
            if not isinstance(device, vim.vm.device.VirtualDisk):
                continue

            capacity_kb = device.capacityInKB if device.capacityInKB else 0
            capacity_bytes = capacity_kb * 1024
            unit_number = device.unitNumber if device.unitNumber is not None else len(disks)
            controller_key = device.controllerKey if device.controllerKey is not None else 0
            disk_label = device.deviceInfo.label if device.deviceInfo else f'Hard disk {len(disks) + 1}'

            disks.append({
                'label': disk_label,
                'capacity_bytes': capacity_bytes,
                'capacity_gb': round(capacity_bytes / (1024 ** 3), 2),
                'unit_number': unit_number,
                'controller_key': controller_key,
            })

        disks.sort(key=lambda disk: (disk['controller_key'], disk['unit_number']))
        return disks

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
            
            firmware = None
            efi_secure_boot = False
            if vm.config:
                firmware = getattr(vm.config, 'firmware', None)
                boot_options = getattr(vm.config, 'bootOptions', None)
                if boot_options is not None:
                    efi_secure_boot = bool(
                        getattr(boot_options, 'efiSecureBootEnabled', False)
                    )

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
                'instance_uuid': vm.config.instanceUuid if vm.config else None,
                'firmware': firmware,
                'efi_secure_boot': efi_secure_boot,
                'nics': self._collect_nics(vm),
                'disks': self._collect_disks(vm),
            }
            
        except vim.fault.NotAuthenticated:
            raise
        except Exception as e:
            logger.error(f"Error getting VM info for '{vm_name}': {e}")
            return None

    def get_folder_by_path(self, datacenter_name, folder_path):
        """
        Find a folder by datacenter and path
        
        Args:
            datacenter_name: Name of the datacenter
            folder_path: Path to folder (e.g., 'vm' or 'vm/prod/kubernetes')
            
        Returns:
            Folder object or None if not found
        """
        try:
            # Find datacenter
            datacenter = self._get_datacenter(datacenter_name)
            if not datacenter:
                logger.warning(f"Datacenter '{datacenter_name}' not found")
                return None
            
            # Start from the VM folder
            current_folder = datacenter.vmFolder
            
            # Navigate through folder hierarchy
            for folder_name in folder_path.strip('/').split('/'):
                if not folder_name:
                    continue
                    
                found = False
                if hasattr(current_folder, 'childEntity'):
                    for entity in current_folder.childEntity:
                        if isinstance(entity, vim.Folder) and entity.name == folder_name:
                            current_folder = entity
                            found = True
                            break
                
                if not found:
                    logger.warning(f"Folder '{folder_path}' not found in datacenter '{datacenter_name}'")
                    return None
            
            return current_folder
            
        except Exception as e:
            logger.error(f"Error finding folder '{folder_path}' in datacenter '{datacenter_name}': {e}")
            return None

    def _get_datacenter(self, datacenter_name):
        """
        Find a datacenter by name
        
        Args:
            datacenter_name: Name of the datacenter
            
        Returns:
            Datacenter object or None
        """
        try:
            content = self.connection.content
            container = content.viewManager.CreateContainerView(
                content.rootFolder,
                [vim.Datacenter],
                False
            )
            
            for dc in container.view:
                if dc.name == datacenter_name:
                    container.Destroy()
                    return dc
            
            container.Destroy()
            return None
            
        except Exception as e:
            logger.error(f"Error finding datacenter '{datacenter_name}': {e}")
            return None

    def list_vms_in_folder(self, datacenter_name, folder_path):
        """
        List all VMs in a specific folder
        
        Args:
            datacenter_name: Name of the datacenter
            folder_path: Path to folder (e.g., 'vm' or 'vm/prod/kubernetes')
            
        Returns:
            List of VM information dictionaries
        """
        try:
            folder = self.get_folder_by_path(datacenter_name, folder_path)
            if not folder:
                return []
            
            vms = []
            self._collect_vms_recursive(folder, vms)
            
            logger.info(f"Found {len(vms)} VMs in {datacenter_name}/{folder_path}")
            return vms
            
        except Exception as e:
            logger.error(f"Error listing VMs in folder '{folder_path}': {e}")
            return []

    def _collect_vms_recursive(self, folder, vms):
        """
        Recursively collect VMs from a folder and subfolders
        
        Args:
            folder: Folder to search
            vms: List to accumulate VM info
        """
        if hasattr(folder, 'childEntity'):
            for entity in folder.childEntity:
                if isinstance(entity, vim.VirtualMachine):
                    vm_info = {
                        'name': entity.name,
                        'power_state': entity.runtime.powerState,
                        'tools_status': str(entity.guest.toolsStatus) if entity.guest else 'toolsNotInstalled',
                        'guest_os': entity.config.guestFullName if entity.config else 'Unknown'
                    }
                    vms.append(vm_info)
                elif isinstance(entity, vim.Folder):
                    # Recursively search subfolders
                    self._collect_vms_recursive(entity, vms)
