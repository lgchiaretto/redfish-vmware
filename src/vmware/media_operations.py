#!/usr/bin/env python3
"""
VMware Virtual Media Operations
Handles ISO mounting, boot order, and virtual media operations.
"""

import logging
import ssl
import urllib.request
import urllib.error
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
            cdrom_spec.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
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
            cdrom_spec.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
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
    
    def upload_iso_to_datastore(self, source_url: str, datastore_path: str) -> bool:
        """
        Download an ISO from *source_url* and upload it to the vSphere datastore.

        Args:
            source_url:     HTTP/HTTPS URL of the ISO to fetch.
            datastore_path: vSphere datastore path, e.g. '[DS1] isos/rhcos.iso'.

        Returns:
            True on success, False otherwise.
        """
        try:
            # Parse '[DatastoreName] folder/file.iso'
            if not (datastore_path.startswith('[') and ']' in datastore_path):
                logger.error(f"Invalid datastore path for upload: {datastore_path}")
                return False

            bracket_end = datastore_path.index(']')
            ds_name = datastore_path[1:bracket_end].strip()
            file_path = datastore_path[bracket_end + 1:].strip().lstrip('/')

            content = self.connection.content
            if not content:
                logger.error("No vSphere content available for ISO upload")
                return False

            # Resolve the datacenter and its name
            datacenter_name = self._get_datacenter_name_for_datastore(content, ds_name)
            if not datacenter_name:
                logger.warning(f"Could not resolve datacenter for datastore '{ds_name}'; using 'ha-datacenter'")
                datacenter_name = 'ha-datacenter'

            # Build the vSphere datastore browser upload URL
            vcenter_host = self.connection.host
            upload_url = (
                f"https://{vcenter_host}/folder/{urllib.request.pathname2url(file_path)}"
                f"?dcPath={urllib.request.quote(datacenter_name)}"
                f"&dsName={urllib.request.quote(ds_name)}"
            )

            logger.info(f"Uploading ISO from {source_url} to {datastore_path}")

            # Obtain the session cookie from the pyVmomi service instance
            session_cookie = self._get_vsphere_session_cookie()

            # Stream-download from the source URL
            ssl_ctx = ssl._create_unverified_context()
            source_req = urllib.request.Request(source_url)
            with urllib.request.urlopen(source_req, context=ssl_ctx, timeout=300) as source_response:
                content_length = source_response.headers.get('Content-Length')
                logger.info(f"  Source size: {content_length or 'unknown'} bytes")
                iso_data = source_response.read()

            logger.info(f"  Downloaded {len(iso_data):,} bytes; uploading to vSphere...")

            # Upload to vSphere datastore
            upload_req = urllib.request.Request(
                upload_url,
                data=iso_data,
                method='PUT',
                headers={
                    'Content-Type': 'application/octet-stream',
                    'Content-Length': str(len(iso_data)),
                    'Cookie': session_cookie,
                }
            )
            with urllib.request.urlopen(upload_req, context=ssl_ctx, timeout=600) as upload_response:
                status = upload_response.status
                if status in (200, 201):
                    logger.info(f"Successfully uploaded ISO to {datastore_path} (HTTP {status})")
                    return True
                else:
                    logger.error(f"Unexpected upload response: HTTP {status}")
                    return False

        except urllib.error.HTTPError as e:
            logger.error(f"HTTP error uploading ISO to {datastore_path}: {e.code} {e.reason}")
            return False
        except Exception as e:
            logger.error(f"Error uploading ISO to {datastore_path}: {e}")
            return False

    def _get_datacenter_name_for_datastore(self, content, ds_name: str):
        """Return the name of the datacenter that hosts the named datastore."""
        try:
            container = content.viewManager.CreateContainerView(
                content.rootFolder, [vim.Datacenter], True
            )
            for dc in container.view:
                ds_view = content.viewManager.CreateContainerView(
                    dc, [vim.Datastore], True
                )
                for ds in ds_view.view:
                    if ds.name == ds_name:
                        ds_view.Destroy()
                        container.Destroy()
                        return dc.name
                ds_view.Destroy()
            container.Destroy()
        except Exception as e:
            logger.debug(f"Could not resolve datacenter for datastore '{ds_name}': {e}")
        return None

    def _get_vsphere_session_cookie(self) -> str:
        """Extract the SOAP session cookie from the current pyVmomi connection."""
        try:
            session_manager = self.connection.service_instance._stub
            cookie = session_manager.cookie
            return cookie
        except Exception as e:
            logger.debug(f"Could not extract vSphere session cookie: {e}")
            return ''

    def delete_datastore_file(self, datastore_path: str) -> bool:
        """
        Delete a file from a vSphere datastore.

        Args:
            datastore_path: vSphere datastore path, e.g. '[DS1] isos/rhcos.iso'

        Returns:
            True if the deletion succeeded, False otherwise.
        """
        try:
            content = self.connection.content
            if not content:
                logger.error("No vSphere content available for file deletion")
                return False

            file_manager = content.fileManager
            if not file_manager:
                logger.error("vSphere FileManager not available")
                return False

            # Resolve datacenter — use the first available datacenter
            datacenter = None
            container = content.rootFolder
            object_view = content.viewManager.CreateContainerView(
                container, [__import__('pyVmomi', fromlist=['vim']).vim.Datacenter], True
            )
            if object_view.view:
                datacenter = object_view.view[0]
            object_view.Destroy()

            logger.info(f"Deleting datastore file: {datastore_path}")
            task = file_manager.DeleteFile(datastore_path, datacenter)
            result = self._wait_for_task(task)

            if result:
                logger.info(f"Successfully deleted datastore file: {datastore_path}")
            else:
                logger.error(f"Failed to delete datastore file: {datastore_path}")

            return result

        except Exception as e:
            logger.error(f"Error deleting datastore file '{datastore_path}': {e}")
            return False

    def get_iso_status(self, vm_name):
        """
        Get current ISO mount status for a VM.

        Args:
            vm_name: Name of the virtual machine

        Returns:
            dict with keys: inserted (bool), image (str|None), connected (bool)
        """
        try:
            vm = self.vm_operations.get_vm(vm_name)
            if not vm:
                logger.warning(f"VM '{vm_name}' not found when checking ISO status")
                return {'inserted': False, 'image': None, 'connected': False}

            for device in vm.config.hardware.device:
                if isinstance(device, vim.vm.device.VirtualCdrom):
                    backing = device.backing
                    connectable = device.connectable
                    if isinstance(backing, vim.vm.device.VirtualCdrom.IsoBackingInfo):
                        iso_path = backing.fileName
                        connected = connectable.connected if connectable else False
                        return {
                            'inserted': bool(iso_path),
                            'image': iso_path or None,
                            'connected': connected
                        }
                    return {'inserted': False, 'image': None, 'connected': False}

            return {'inserted': False, 'image': None, 'connected': False}

        except Exception as e:
            logger.error(f"Error getting ISO status for VM '{vm_name}': {e}")
            return {'inserted': False, 'image': None, 'connected': False}

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
