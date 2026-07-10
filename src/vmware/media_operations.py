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

    def _collect_boot_device_keys(self, vm):
        """Map boot device categories to hardware device keys on the VM."""
        device_keys = {'cdrom': [], 'disk': [], 'network': []}
        for device in vm.config.hardware.device:
            if isinstance(device, vim.vm.device.VirtualCdrom):
                device_keys['cdrom'].append(device.key)
            elif isinstance(device, vim.vm.device.VirtualDisk):
                device_keys['disk'].append(device.key)
            elif isinstance(device, vim.vm.device.VirtualEthernetCard):
                device_keys['network'].append(device.key)
        return device_keys

    def _create_boot_device(self, device_type, device_keys):
        """Create a VMware boot device object bound to a real hardware device key."""
        device_type_lower = device_type.lower()
        if device_type_lower == 'cdrom':
            keys = device_keys['cdrom']
            if not keys:
                return None
            boot_device = vim.vm.BootOptions.BootableCdromDevice()
            boot_device.deviceKey = keys[0]
            return boot_device

        if device_type_lower == 'disk':
            keys = device_keys['disk']
            if not keys:
                return None
            boot_device = vim.vm.BootOptions.BootableDiskDevice()
            boot_device.deviceKey = keys[0]
            return boot_device

        if device_type_lower in ('network', 'pxe'):
            keys = device_keys['network']
            if not keys:
                return None
            boot_device = vim.vm.BootOptions.BootableEthernetDevice()
            boot_device.deviceKey = keys[0]
            return boot_device

        return None
    
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

            device_keys = self._collect_boot_device_keys(vm)
            logger.debug(
                "Boot device keys for VM '%s': cdrom=%s disk=%s network=%s",
                vm_name,
                device_keys['cdrom'],
                device_keys['disk'],
                device_keys['network'],
            )

            boot_devices = []
            for device_type in boot_order:
                boot_device = self._create_boot_device(device_type, device_keys)
                if boot_device is None:
                    logger.warning(
                        "Skipping boot device type '%s' for VM '%s' — no matching hardware device found",
                        device_type,
                        vm_name,
                    )
                    continue
                boot_devices.append(boot_device)
            
            if not boot_devices:
                logger.error(f"No valid boot devices found for requested boot order: {boot_order}")
                return False
            
            logger.debug(
                "Boot devices created: %s",
                [(type(d).__name__, getattr(d, 'deviceKey', None)) for d in boot_devices],
            )
            
            # Configure boot options
            boot_spec = vim.vm.BootOptions()
            boot_spec.bootOrder = boot_devices
            
            config_spec = vim.vm.ConfigSpec()
            config_spec.bootOptions = boot_spec
            
            task = vm.Reconfigure(config_spec)
            result = self._wait_for_task(task)
            
            if result:
                logger.info(f"Successfully set boot order for VM '{vm_name}'")
            else:
                logger.error(f"Failed to set boot order for VM '{vm_name}'")
            
            return result
            
        except vim.fault.NotAuthenticated:
            raise
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
            
        except vim.fault.NotAuthenticated:
            raise
        except Exception as e:
            logger.error(f"Error mounting ISO to VM '{vm_name}': {e}")
            return False
    
    def unmount_iso(self, vm_name, force=False):
        """
        Unmount ISO from VM's CD/DVD drive
        
        Args:
            vm_name: Name of the virtual machine
            force: If True, attempt to force eject bypassing OS locks (timeout after 5s)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            vm = self.vm_operations.get_vm(vm_name)
            if not vm:
                logger.error(f"VM '{vm_name}' not found")
                return False
            
            logger.info(f"Unmounting ISO from VM '{vm_name}'{' (force mode)' if force else ''}")
            
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
            # For force eject, just disconnect without changing backing
            cdrom_spec = vim.vm.device.VirtualDeviceSpec()
            cdrom_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
            cdrom_spec.device = cdrom_device
            
            # Don't change backing info - just disconnect the device
            # This bypasses OS locks by simply marking it as disconnected
            cdrom_spec.device.backing = vim.vm.device.VirtualCdrom.IsoBackingInfo()
            cdrom_spec.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
            cdrom_spec.device.connectable.connected = False
            cdrom_spec.device.connectable.startConnected = False
            
            config_spec = vim.vm.ConfigSpec()
            config_spec.deviceChange = [cdrom_spec]
            
            task = vm.Reconfigure(config_spec)
            
            # For force eject, wait for task and handle any runtime questions
            if force:
                result = self._wait_for_task_with_questions(task, vm, timeout=5)
            else:
                result = self._wait_for_task(task, timeout=None)
            
            if result:
                logger.info(f"Successfully unmounted ISO from VM '{vm_name}'")
            else:
                logger.error(f"Failed to unmount ISO from VM '{vm_name}'")
                # If force eject timed out, try again with longer timeout
                if force:
                    logger.warning(f"Force eject timed out for VM '{vm_name}', retrying with longer timeout...")
                    result = self._wait_for_task_with_questions(task, vm, timeout=15)
            
            return result
            
        except vim.fault.NotAuthenticated:
            raise
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

    def _wait_for_task(self, task, timeout=None):
        """
        Wait for a vCenter task to complete
        
        Args:
            task: Task object
            timeout: Maximum seconds to wait (None = no timeout)
            
        Returns:
            True if task completed successfully, False otherwise
        """
        try:
            import time
            start_time = time.time()
            
            while task.info.state in ['running', 'queued']:
                if timeout is not None:
                    elapsed = time.time() - start_time
                    if elapsed > timeout:
                        logger.warning(f"Task timeout after {timeout}s in state '{task.info.state}'")
                        return False
                time.sleep(1)
            
            if task.info.state == 'success':
                return True
            else:
                logger.error(f"Task failed: {task.info.error}")
                return False
                
        except Exception as e:
            logger.error(f"Error waiting for task: {e}")
            return False

    def _wait_for_task_with_questions(self, task, vm, timeout=None):
        """
        Wait for a vCenter task to complete, handling any runtime questions.
        Used for CD eject operations that may prompt for confirmation.
        
        Args:
            task: Task object
            vm: VM object to check for runtime questions
            timeout: Maximum seconds to wait (None = no timeout)
            
        Returns:
            True if task completed successfully, False otherwise
        """
        try:
            import time
            start_time = time.time()
            
            while task.info.state in ['running', 'queued']:
                # Check for runtime questions and answer CD-related ones
                if vm.runtime.question:
                    question = vm.runtime.question
                    question_text = question.text if hasattr(question, 'text') else str(question)
                    logger.info(f"🤖 VM runtime question detected: {question_text}")
                    
                    # Check if this is a CD ejection question
                    if 'cd' in question_text.lower() or 'cdrom' in question_text.lower() or 'dvd' in question_text.lower():
                        logger.info(f"✅ Answering CD ejection question for VM")
                        try:
                            # vim.option.ChoiceOption stores choices in .choiceInfo (list of ElementDescription)
                            # Each ElementDescription has a .key attribute to use as the answer
                            if hasattr(question, 'choice') and hasattr(question.choice, 'choiceInfo') and question.choice.choiceInfo:
                                answer = question.choice.choiceInfo[0].key
                                vm.AnswerVM(question.id, answer)
                                logger.info(f"✅ Answered CD ejection question with key: {answer}")
                            else:
                                logger.warning(f"No choices available in runtime question")
                        except Exception as e:
                            logger.warning(f"Could not answer runtime question: {e}")
                
                if timeout is not None:
                    elapsed = time.time() - start_time
                    if elapsed > timeout:
                        logger.warning(f"Task timeout after {timeout}s in state '{task.info.state}'")
                        return False
                time.sleep(1)
            
            if task.info.state == 'success':
                return True
            else:
                logger.error(f"Task failed: {task.info.error}")
                return False
                
        except Exception as e:
            logger.error(f"Error waiting for task with questions: {e}")
            return False
