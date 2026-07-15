#!/usr/bin/env python3
"""
Systems Handler
Handles Redfish Computer Systems endpoints for VM management.
"""

import json
import logging
from typing import Dict, Optional

from models.redfish_schemas import RedfishModels
from handlers.response_utils import RedfishResponseMixin

logger = logging.getLogger(__name__)


class SystemsHandler(RedfishResponseMixin):
    """Handler for Redfish Systems endpoints"""
    
    def __init__(self, vm_configs: Dict, vmware_clients: Dict, task_manager):
        self.vm_configs = vm_configs
        self.vmware_clients = vmware_clients
        self.task_manager = task_manager
        logger.info("💻 Systems handler initialized")
    
    def handle_get(self, request_handler, path: str):
        """Handle GET requests for Systems"""
        if path == '/redfish/v1/Systems':
            # Systems collection
            data = RedfishModels.get_systems_collection(list(self.vm_configs.keys()))
            self._send_json_response(request_handler, 200, data)
        elif '/redfish/v1/Systems/' in path:
            # Individual system
            vm_name = self._extract_vm_name(path)
            if vm_name and vm_name in self.vm_configs:
                if '/Bios' in path:
                    self._handle_bios_get(request_handler, vm_name, path)
                elif '/Storage' in path:
                    self._handle_storage_get(request_handler, vm_name, path)
                elif '/Processors' in path:
                    self._handle_processors_get(request_handler, vm_name, path)
                elif '/Memory' in path:
                    self._handle_memory_get(request_handler, vm_name, path)
                elif '/NetworkInterfaces' in path:
                    self._handle_network_interfaces_get(request_handler, vm_name, path)
                elif '/EthernetInterfaces' in path:
                    self._handle_ethernet_interfaces_get(request_handler, vm_name, path)
                elif '/SecureBoot' in path:
                    self._handle_secure_boot_get(request_handler, vm_name, path)
                else:
                    data = self._get_system_info(vm_name)
                    self._send_json_response(request_handler, 200, data)
            else:
                self._send_error_response(request_handler, 404, "System not found")
        else:
            self._send_error_response(request_handler, 404, "Not Found")
    
    def handle_post(self, request_handler, path: str):
        """Handle POST requests for Systems"""
        if '/Actions/' in path:
            vm_name = self._extract_vm_name(path)
            if vm_name and vm_name in self.vm_configs:
                self._handle_system_action(request_handler, vm_name, path)
            else:
                self._send_error_response(request_handler, 404, "System not found")
        else:
            self._send_error_response(request_handler, 405, "Method not allowed")
    
    def handle_patch(self, request_handler, path: str):
        """Handle PATCH requests for Systems"""
        vm_name = self._extract_vm_name(path)
        if vm_name and vm_name in self.vm_configs:
            if '/Bios' in path:
                self._handle_bios_patch(request_handler, vm_name, path)
            elif '/SecureBoot' in path:
                self._handle_secure_boot_patch(request_handler, vm_name, path)
            else:
                self._handle_system_patch(request_handler, vm_name, path)
        else:
            self._send_error_response(request_handler, 404, "System not found")
    
    def _extract_vm_name(self, path: str) -> Optional[str]:
        """Extract VM name from path"""
        parts = path.split('/')
        if 'Systems' in parts:
            systems_index = parts.index('Systems')
            if len(parts) > systems_index + 1:
                return parts[systems_index + 1]
        return None
    
    def _get_vmware_info(self, vm_name: str) -> Dict:
        """Return VMware VM info for a configured system, or an empty dict."""
        vmware_client = self.vmware_clients.get(vm_name)
        if not vmware_client:
            return {}

        try:
            return vmware_client.get_vm_info(vm_name) or {}
        except Exception as client_error:
            logger.warning(f"Unable to retrieve VMware info for {vm_name}: {client_error}")
            return {}

    @staticmethod
    def _drive_device_name(index: int) -> str:
        """Map a disk index to a Linux device name used by rootDeviceHints."""
        return f'/dev/vd{chr(ord("a") + index)}'

    def _get_vm_nics(self, vm_name: str) -> list:
        """Return NIC metadata for a VM, with a single fallback entry when unavailable."""
        vm_info = self._get_vmware_info(vm_name)
        nics = vm_info.get('nics') or []
        if nics:
            return nics

        return [{
            'mac': '00:50:56:00:00:00',
            'label': 'Network adapter 1',
            'connected': True,
            'type': 'VirtualVmxnet3',
        }]

    def _get_vm_disks(self, vm_name: str) -> list:
        """Return disk metadata for a VM, with a single fallback entry when unavailable."""
        vm_info = self._get_vmware_info(vm_name)
        disks = vm_info.get('disks') or []
        if disks:
            return disks

        return [{
            'label': 'Hard disk 1',
            'capacity_bytes': 128 * (1024 ** 3),
            'capacity_gb': 128,
            'unit_number': 0,
            'controller_key': 0,
        }]

    def _build_ethernet_interface_payload(self, vm_name: str, interface_id: str, nic: Dict) -> Dict:
        """Build a Redfish EthernetInterface payload from VMware NIC metadata."""
        mac = nic.get('mac', '00:50:56:00:00:00')
        label = nic.get('label', f'Ethernet Interface {interface_id}')
        return {
            '@odata.type': '#EthernetInterface.v1_6_0.EthernetInterface',
            '@odata.id': f'/redfish/v1/Systems/{vm_name}/EthernetInterfaces/{interface_id}',
            'Id': interface_id,
            'Name': label,
            'Description': f'{label} for {vm_name}',
            'Status': {
                'State': 'Enabled',
                'Health': 'OK',
            },
            'InterfaceEnabled': bool(nic.get('connected', True)),
            'PermanentMACAddress': mac,
            'MACAddress': mac,
            'SpeedMbps': 10000,
            'FullDuplex': True,
            'LinkStatus': 'LinkUp' if nic.get('connected', True) else 'LinkDown',
        }

    def _build_drive_payload(self, vm_name: str, storage_id: str, drive_id: str, disk: Dict, index: int) -> Dict:
        """Build a Redfish Drive payload from VMware disk metadata."""
        device_name = self._drive_device_name(index)
        capacity_bytes = disk.get('capacity_bytes') or 0
        return {
            '@odata.type': '#Drive.v1_7_0.Drive',
            '@odata.id': f'/redfish/v1/Systems/{vm_name}/Storage/{storage_id}/Drives/{drive_id}',
            'Id': drive_id,
            'Name': device_name,
            'Description': disk.get('label', f'Virtual disk {index + 1}'),
            'Status': {
                'State': 'Enabled',
                'Health': 'OK',
            },
            'CapacityBytes': capacity_bytes,
            'MediaType': 'SSD',
            'Protocol': 'SATA',
            'RotationSpeedRPM': 0,
            'BlockSizeBytes': 512,
            'SerialNumber': f'VMware-{vm_name}-{drive_id}',
            'Identifiers': [
                {
                    'DurableNameFormat': 'NAA',
                    'DurableName': f'VMware-{vm_name}-{index}',
                }
            ],
        }

    def _get_system_info(self, vm_name: str) -> Dict:
        """Get a Redfish ComputerSystem payload for a VM."""
        try:
            vm_info = self._get_vmware_info(vm_name)
            power_state = 'Off'
            if vm_info:
                power_state = RedfishModels.get_power_state_mapping().get(
                    vm_info.get('power_state', 'poweredOff'), 'Off'
                )

            cpu_count = vm_info.get('cpu_count', 0) or 0
            memory_mb = vm_info.get('memory_mb', 0) or 0
            memory_gib = max(1, int(round(memory_mb / 1024))) if memory_mb else 0
            guest_hostname = vm_info.get('guest_hostname') or vm_info.get('guest_ip') or f'{vm_name}.local'
            uuid = vm_info.get('uuid') or vm_info.get('instance_uuid') or f'00000000-0000-0000-0000-{vm_name[-12:].ljust(12, "0")}'

            return {
                '@odata.type': '#ComputerSystem.v1_13_0.ComputerSystem',
                '@odata.id': f'/redfish/v1/Systems/{vm_name}',
                'Id': vm_name,
                'Name': vm_name,
                'Description': f'VMware virtual machine {vm_name}',
                'SystemType': 'Virtual',
                'AssetTag': 'VMware-Bridge',
                'IndicatorLED': 'Off',
                'Status': {
                    'State': 'Enabled',
                    'Health': 'OK'
                },
                'PowerState': power_state,
                'BiosVersion': 'Virtual BIOS',
                'Manufacturer': 'VMware',
                'Model': 'Virtual Machine',
                'SKU': 'VMware VM',
                'SerialNumber': f'VMware-{vm_name}',
                'PartNumber': 'VMware-System',
                'UUID': uuid,
                'HostName': guest_hostname,
                'Boot': {
                    'BootSourceOverrideEnabled': 'Disabled',
                    'BootSourceOverrideTarget': 'None',
                    'BootSourceOverrideTarget@Redfish.AllowableValues': [
                        'None', 'Pxe', 'Cd', 'Usb', 'Hdd', 'BiosSetup'
                    ]
                },
                'Bios': {
                    '@odata.id': f'/redfish/v1/Systems/{vm_name}/Bios'
                },
                'SecureBoot': {
                    '@odata.id': f'/redfish/v1/Systems/{vm_name}/SecureBoot'
                },
                'Storage': {
                    '@odata.id': f'/redfish/v1/Systems/{vm_name}/Storage'
                },
                'EthernetInterfaces': {
                    '@odata.id': f'/redfish/v1/Systems/{vm_name}/EthernetInterfaces'
                },
                'Processors': {
                    '@odata.id': f'/redfish/v1/Systems/{vm_name}/Processors'
                },
                'Memory': {
                    '@odata.id': f'/redfish/v1/Systems/{vm_name}/Memory'
                },
                'NetworkInterfaces': {
                    '@odata.id': f'/redfish/v1/Systems/{vm_name}/NetworkInterfaces'
                },
                'ProcessorSummary': {
                    'Count': cpu_count,
                    'Model': 'Virtual CPU',
                    'Status': {
                        'State': 'Enabled',
                        'Health': 'OK'
                    }
                },
                'MemorySummary': {
                    'TotalSystemMemoryGiB': memory_gib,
                    'Status': {
                        'State': 'Enabled',
                        'Health': 'OK'
                    }
                },
                'MemoryDomains': [
                    {
                        'Name': 'System Memory',
                        'MemoryType': 'DRAM',
                        'CapacityMiB': max(1024, memory_mb)
                    }
                ],
                'TrustedModules': [
                    {
                        'FirmwareVersion': '1.0.0',
                        'InterfaceType': 'TPM1_2',
                        'Status': {
                            'State': 'Enabled',
                            'Health': 'OK'
                        }
                    }
                ],
                'Actions': {
                    '#ComputerSystem.Reset': {
                        'target': f'/redfish/v1/Systems/{vm_name}/Actions/ComputerSystem.Reset',
                        'ResetType@Redfish.AllowableValues': [
                            'On', 'ForceOff', 'GracefulShutdown', 'GracefulRestart', 'ForceRestart'
                        ]
                    }
                },
                'Links': {
                    'Chassis': [
                        {
                            '@odata.id': f'/redfish/v1/Chassis/{vm_name}-chassis'
                        }
                    ],
                    'ManagedBy': [
                        {
                            '@odata.id': f'/redfish/v1/Managers/{vm_name}-bmc'
                        }
                    ],
                    'Processors': [
                        {
                            '@odata.id': f'/redfish/v1/Systems/{vm_name}/Processors'
                        }
                    ],
                    'Memory': [
                        {
                            '@odata.id': f'/redfish/v1/Systems/{vm_name}/Memory'
                        }
                    ],
                    'NetworkInterfaces': [
                        {
                            '@odata.id': f'/redfish/v1/Systems/{vm_name}/NetworkInterfaces'
                        }
                    ],
                    'EthernetInterfaces': [
                        {
                            '@odata.id': f'/redfish/v1/Systems/{vm_name}/EthernetInterfaces'
                        }
                    ],
                    'ComputerSystems': []
                },
                'Oem': {
                    'VMware': {
                        'VMName': vm_name,
                        'GuestOS': vm_info.get('guest_os', 'Unknown'),
                        'ToolsStatus': vm_info.get('tools_status', 'toolsNotInstalled')
                    }
                }
            }
        except Exception as e:
            logger.error(f"❌ Error getting system info for {vm_name}: {e}")
            raise
    
    def _handle_bios_get(self, request_handler, vm_name: str, path: str):
        """Handle BIOS GET requests"""
        if path.endswith('/Bios'):
            data = {
                '@odata.type': '#Bios.v1_1_0.Bios',
                '@odata.id': f'/redfish/v1/Systems/{vm_name}/Bios',
                'Id': 'BIOS',
                'Name': 'BIOS Configuration',
                'Description': f'BIOS Configuration for {vm_name}',
                'BiosVersion': '2.0.0',
                'Attributes': {
                    'SecureBootEnable': True,
                    'TpmSecurity': 'On',
                    'BootMode': 'UEFI'
                },
                'Actions': {
                    '#Bios.ResetBios': {
                        'target': f'/redfish/v1/Systems/{vm_name}/Bios/Actions/Bios.ResetBios'
                    },
                    '#Bios.ChangePassword': {
                        'target': f'/redfish/v1/Systems/{vm_name}/Bios/Actions/Bios.ChangePassword'
                    }
                }
            }
            self._send_json_response(request_handler, 200, data)
        else:
            self._send_error_response(request_handler, 404, "Not Found")
    
    def _handle_storage_get(self, request_handler, vm_name: str, path: str):
        """Handle Storage GET requests"""
        if path.endswith('/Storage'):
            data = {
                '@odata.type': '#StorageCollection.StorageCollection',
                '@odata.id': f'/redfish/v1/Systems/{vm_name}/Storage',
                'Name': 'Storage Collection',
                'Description': f'Storage Collection for {vm_name}',
                'Members@odata.count': 1,
                'Members': [
                    {
                        '@odata.id': f'/redfish/v1/Systems/{vm_name}/Storage/1'
                    }
                ]
            }
            self._send_json_response(request_handler, 200, data)
            return

        storage_prefix = f'/redfish/v1/Systems/{vm_name}/Storage/1'
        if path.startswith(f'{storage_prefix}/Drives/'):
            drive_id = path.split('/')[-1]
            disks = self._get_vm_disks(vm_name)
            for index, disk in enumerate(disks):
                if f'disk-{index}' == drive_id:
                    data = self._build_drive_payload(vm_name, '1', drive_id, disk, index)
                    self._send_json_response(request_handler, 200, data)
                    return
            self._send_error_response(request_handler, 404, "Drive not found")
            return

        if path == storage_prefix:
            disks = self._get_vm_disks(vm_name)
            drives = [
                {
                    '@odata.id': f'/redfish/v1/Systems/{vm_name}/Storage/1/Drives/disk-{index}'
                }
                for index in range(len(disks))
            ]
            data = {
                '@odata.type': '#Storage.v1_8_0.Storage',
                '@odata.id': storage_prefix,
                'Id': '1',
                'Name': 'Storage Controller',
                'Description': f'Storage Controller 1 for {vm_name}',
                'Status': {
                    'State': 'Enabled',
                    'Health': 'OK'
                },
                'StorageControllers': [
                    {
                        'MemberId': 'controller0',
                        'Name': 'VMware SCSI Controller',
                        'Manufacturer': 'VMware',
                        'Model': 'Virtual SCSI',
                        'Status': {
                            'State': 'Enabled',
                            'Health': 'OK'
                        },
                        'SupportedRAIDTypes': ['RAID0', 'RAID1'],
                        'SpeedGbps': 6.0
                    }
                ],
                'Drives': drives,
            }
            self._send_json_response(request_handler, 200, data)
            return

        self._send_error_response(request_handler, 404, "Not Found")
    
    def _handle_processors_get(self, request_handler, vm_name: str, path: str):
        """Handle Processors GET requests"""
        self._handle_related_collection_get(
            request_handler,
            vm_name,
            path,
            'Processors',
            'Processor',
            'Processors Collection',
            'Processor',
            'CPU Processor',
        )

    def _handle_memory_get(self, request_handler, vm_name: str, path: str):
        """Handle Memory GET requests"""
        self._handle_related_collection_get(
            request_handler,
            vm_name,
            path,
            'Memory',
            'Memory',
            'Memory Collection',
            'Memory',
            'System Memory',
        )

    def _handle_network_interfaces_get(self, request_handler, vm_name: str, path: str):
        """Handle NetworkInterfaces GET requests"""
        self._handle_related_collection_get(
            request_handler,
            vm_name,
            path,
            'NetworkInterfaces',
            'NetworkInterface',
            'Network Interfaces Collection',
            'NetworkInterface',
            'Virtual Network Interface',
        )

    def _handle_ethernet_interfaces_get(self, request_handler, vm_name: str, path: str):
        """Handle EthernetInterfaces GET requests with real VMware NIC metadata."""
        collection_path = f'/redfish/v1/Systems/{vm_name}/EthernetInterfaces'
        if path == collection_path:
            nics = self._get_vm_nics(vm_name)
            data = {
                '@odata.type': '#EthernetInterfaceCollection.EthernetInterfaceCollection',
                '@odata.id': collection_path,
                'Name': 'Ethernet Interfaces Collection',
                'Description': f'Ethernet Interfaces collection for {vm_name}',
                'Members@odata.count': len(nics),
                'Members': [
                    {
                        '@odata.id': f'{collection_path}/{index + 1}'
                    }
                    for index in range(len(nics))
                ],
            }
            self._send_json_response(request_handler, 200, data)
            return

        if path.startswith(f'{collection_path}/'):
            interface_id = path.split('/')[-1]
            nics = self._get_vm_nics(vm_name)
            if interface_id.isdigit():
                index = int(interface_id) - 1
                if 0 <= index < len(nics):
                    data = self._build_ethernet_interface_payload(vm_name, interface_id, nics[index])
                    self._send_json_response(request_handler, 200, data)
                    return

            self._send_error_response(request_handler, 404, "Interface not found")
            return

        self._send_error_response(request_handler, 404, "Not Found")

    def _handle_related_collection_get(self, request_handler, vm_name: str, path: str, collection_name: str, member_type: str, collection_label: str, member_schema: str, member_description: str):
        """Serve Redfish collection and member resources for related system subpaths."""
        if path.endswith(f'/{collection_name}'):
            data = {
                '@odata.type': '#Collection.Collection',
                '@odata.id': f'/redfish/v1/Systems/{vm_name}/{collection_name}',
                'Id': collection_name,
                'Name': f'{collection_name} Collection',
                'Description': f'{collection_name} collection for {vm_name}',
                'Members@odata.count': 1,
                'Members': [
                    {
                        '@odata.id': f'/redfish/v1/Systems/{vm_name}/{collection_name}/1'
                    }
                ]
            }
            self._send_json_response(request_handler, 200, data)
            return

        if '/' in path and path.split('/')[-1].isdigit():
            member_id = path.split('/')[-1]
            data = {
                '@odata.type': f'#{member_schema}.v1_0_0.{member_schema}',
                '@odata.id': path,
                'Id': member_id,
                'Name': f'{member_type} {member_id}',
                'Description': f'{member_description} {member_id} for {vm_name}',
                'Status': {
                    'State': 'Enabled',
                    'Health': 'OK'
                }
            }
            self._send_json_response(request_handler, 200, data)
            return

        self._send_error_response(request_handler, 404, "Not Found")

    def _handle_secure_boot_get(self, request_handler, vm_name: str, path: str):
        """Handle SecureBoot GET requests"""
        if path.endswith('/SecureBoot'):
            data = {
                '@odata.type': '#SecureBoot.v1_1_0.SecureBoot',
                '@odata.id': f'/redfish/v1/Systems/{vm_name}/SecureBoot',
                'Id': 'SecureBoot',
                'Name': 'Secure Boot',
                'Description': f'Secure Boot for {vm_name}',
                'SecureBootEnable': True,
                'SecureBootCurrentBoot': 'Enabled',
                'SecureBootMode': 'UserMode',
                'Actions': {
                    '#SecureBoot.ResetKeys': {
                        'target': f'/redfish/v1/Systems/{vm_name}/SecureBoot/Actions/SecureBoot.ResetKeys'
                    }
                }
            }
            self._send_json_response(request_handler, 200, data)
        else:
            self._send_error_response(request_handler, 404, "Not Found")
    
    def _handle_system_action(self, request_handler, vm_name: str, path: str):
        """Handle system actions like power operations"""
        try:
            content_length = int(request_handler.headers.get('Content-Length', 0))
            if content_length > 0:
                post_data = request_handler.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                if 'ComputerSystem.Reset' in path:
                    reset_type = data.get('ResetType', 'On')
                    self._handle_power_action(request_handler, vm_name, reset_type)
                else:
                    self._send_error_response(request_handler, 400, "Unsupported action")
            else:
                self._send_error_response(request_handler, 400, "Missing action data")
        except Exception as e:
            logger.error(f"❌ Error handling system action for {vm_name}: {e}")
            self._send_error_response(request_handler, 500, "Internal Server Error")
    
    def _handle_power_action(self, request_handler, vm_name: str, reset_type: str):
        """Handle power management actions"""
        try:
            vmware_client = self.vmware_clients.get(vm_name)
            if not vmware_client:
                self._send_error_response(request_handler, 503, "VMware client not available")
                return
            
            logger.info(f"🔌 Power action for {vm_name}: {reset_type}")
            
            # Create task for the operation
            task_id = self.task_manager.create_task(
                'PowerOperation',
                f'Power {reset_type} for {vm_name}',
                f'Performing {reset_type} operation on {vm_name}'
            )
            
            # Perform the power operation
            success = False
            if reset_type == 'On':
                success = vmware_client.power_on_vm(vm_name)
            elif reset_type == 'ForceOff':
                success = vmware_client.power_off_vm(vm_name)
            elif reset_type == 'GracefulShutdown':
                success = vmware_client.shutdown_vm(vm_name)
            elif reset_type == 'GracefulRestart':
                success = vmware_client.restart_vm(vm_name)
            elif reset_type == 'ForceRestart':
                success = vmware_client.reset_vm(vm_name)
            
            # Update task based on result
            if success:
                self.task_manager.complete_task(task_id, f'Power operation {reset_type} completed successfully')
                request_handler.send_response(204)  # No Content
                request_handler.end_headers()
            else:
                self.task_manager.complete_task(task_id, f'Power operation {reset_type} failed', success=False)
                self._send_error_response(request_handler, 500, "Power operation failed")
                
        except Exception as e:
            logger.error(f"❌ Power action error for {vm_name}: {e}")
            self._send_error_response(request_handler, 500, "Internal Server Error")
    
    # Redfish BootSourceOverrideTarget -> VMware boot-order device names
    _BOOT_TARGET_MAP = {
        'Cd':       ['cdrom', 'disk', 'network'],
        'Pxe':      ['network', 'disk', 'cdrom'],
        'Hdd':      ['disk', 'cdrom', 'network'],
        'Usb':      ['disk', 'cdrom', 'network'],
        'BiosSetup': ['disk', 'cdrom', 'network'],
        'None':     ['disk', 'cdrom', 'network'],
    }

    def _handle_system_patch(self, request_handler, vm_name: str, path: str):
        """Handle system PATCH requests — applies boot-order changes via VMware."""
        try:
            content_length = int(request_handler.headers.get('Content-Length', 0))
            if not content_length:
                self._send_error_response(request_handler, 400, "Missing patch data")
                return

            patch_data = request_handler.rfile.read(content_length)
            data = json.loads(patch_data.decode('utf-8'))

            if 'Boot' not in data:
                self._send_error_response(request_handler, 400, "No supported properties to patch")
                return

            boot_config = data['Boot']
            logger.info(f"🥾 Boot configuration change for {vm_name}: {boot_config}")

            target = boot_config.get('BootSourceOverrideTarget')
            enabled = boot_config.get('BootSourceOverrideEnabled', 'Once')

            if target and target != 'None':
                boot_order = self._BOOT_TARGET_MAP.get(target, ['disk', 'cdrom', 'network'])
                vmware_client = self.vmware_clients.get(vm_name)
                if vmware_client:
                    success = vmware_client.set_vm_boot_order(vm_name, boot_order)
                    if not success:
                        logger.warning(f"⚠️  VMware boot order change failed for {vm_name}, continuing")
                else:
                    logger.warning(f"⚠️  No VMware client available for {vm_name}; boot order not applied")

            # Return the updated system object so Metal3 can verify the change
            updated = self._get_system_info(vm_name)
            updated['Boot']['BootSourceOverrideTarget'] = target or 'None'
            updated['Boot']['BootSourceOverrideEnabled'] = enabled
            self._send_json_response(request_handler, 200, updated)

        except json.JSONDecodeError as e:
            self._send_error_response(request_handler, 400, f"Invalid JSON: {e}")
        except Exception as e:
            logger.error(f"❌ System PATCH error for {vm_name}: {e}")
            self._send_error_response(request_handler, 500, "Internal Server Error")

    def _handle_bios_patch(self, request_handler, vm_name: str, path: str):
        """Handle BIOS PATCH requests.

        VMware does not expose BIOS attribute configuration through the vSphere API.
        Return 501 so clients know the operation is not supported rather than
        silently pretending the change was applied.
        """
        logger.info(f"🔧 BIOS PATCH requested for {vm_name} — not supported on VMware")
        self._send_error_response(
            request_handler, 501,
            "BIOS attribute configuration is not supported on VMware virtual machines"
        )

    def _handle_secure_boot_patch(self, request_handler, vm_name: str, path: str):
        """Handle SecureBoot PATCH requests.

        VMware SecureBoot state is part of the VM firmware configuration and
        cannot be changed while the VM is running. Changing it also requires
        a VM power cycle which is disruptive and is not performed automatically.
        Return 501 so clients know this is not supported.
        """
        logger.info(f"🔒 SecureBoot PATCH requested for {vm_name} — not supported on VMware")
        self._send_error_response(
            request_handler, 501,
            "SecureBoot configuration changes are not supported on VMware virtual machines"
        )
