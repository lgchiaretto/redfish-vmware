#!/usr/bin/env python3
"""
Systems Handler
Handles Redfish Computer Systems endpoints for VM management.
"""

import json
import logging
from typing import Dict, Optional

from models.redfish_schemas import RedfishModels

logger = logging.getLogger(__name__)


class SystemsHandler:
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
    
    def _get_system_info(self, vm_name: str) -> Dict:
        """Get system information for a VM"""
        try:
            # Get VM power state
            vmware_client = self.vmware_clients.get(vm_name)
            if vmware_client:
                vm_info = vmware_client.get_vm_info(vm_name)
                power_state = RedfishModels.get_power_state_mapping().get(
                    vm_info.get('power_state', 'poweredOff'), 'Off'
                )
            else:
                power_state = 'Off'
            
            return {
                '@odata.type': '#ComputerSystem.v1_13_0.ComputerSystem',
                '@odata.id': f'/redfish/v1/Systems/{vm_name}',
                'Id': vm_name,
                'Name': f'System {vm_name}',
                'Description': f'VMware VM {vm_name}',
                'Status': {
                    'State': 'Enabled',
                    'Health': 'OK'
                },
                'PowerState': power_state,
                'BiosVersion': '2.0.0',
                'Manufacturer': 'VMware',
                'Model': 'Virtual Machine',
                'SKU': 'VMware VM',
                'SerialNumber': f'VMware-{vm_name}',
                'PartNumber': 'VMware-System',
                'UUID': f'424d4f4e-{vm_name[-8:].ljust(8, "0")}-{vm_name[-4:].ljust(4, "0")}-{vm_name[-4:].ljust(4, "0")}-{vm_name[-12:].ljust(12, "0")}',
                'HostName': f'{vm_name}.local',
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
                    ]
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
            # Storage collection
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
        elif '/Storage/' in path and path.split('/')[-1].isdigit():
            # Individual storage controller
            storage_id = path.split('/')[-1]
            data = {
                '@odata.type': '#Storage.v1_8_0.Storage',
                '@odata.id': f'/redfish/v1/Systems/{vm_name}/Storage/{storage_id}',
                'Id': storage_id,
                'Name': 'Storage Controller',
                'Description': f'Storage Controller {storage_id} for {vm_name}',
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
                'Drives': []
            }
            self._send_json_response(request_handler, 200, data)
        else:
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
    
    def _handle_system_patch(self, request_handler, vm_name: str, path: str):
        """Handle system PATCH requests"""
        try:
            content_length = int(request_handler.headers.get('Content-Length', 0))
            if content_length > 0:
                patch_data = request_handler.rfile.read(content_length)
                data = json.loads(patch_data.decode('utf-8'))
                
                # Handle boot configuration changes
                if 'Boot' in data:
                    boot_config = data['Boot']
                    logger.info(f"🥾 Boot configuration change for {vm_name}: {boot_config}")
                    
                    # For now, just acknowledge the change
                    request_handler.send_response(200)
                    request_handler.send_header('Content-Type', 'application/json')
                    request_handler.end_headers()
                    
                    response = {
                        '@odata.type': '#ComputerSystem.v1_13_0.ComputerSystem',
                        'Id': vm_name,
                        'Boot': boot_config
                    }
                    request_handler.wfile.write(json.dumps(response).encode('utf-8'))
                else:
                    self._send_error_response(request_handler, 400, "No supported properties to patch")
            else:
                self._send_error_response(request_handler, 400, "Missing patch data")
        except Exception as e:
            logger.error(f"❌ System PATCH error for {vm_name}: {e}")
            self._send_error_response(request_handler, 500, "Internal Server Error")
    
    def _handle_bios_patch(self, request_handler, vm_name: str, path: str):
        """Handle BIOS PATCH requests"""
        try:
            content_length = int(request_handler.headers.get('Content-Length', 0))
            if content_length > 0:
                patch_data = request_handler.rfile.read(content_length)
                data = json.loads(patch_data.decode('utf-8'))
                
                logger.info(f"🔧 BIOS configuration change for {vm_name}: {data}")
                
                # For now, just acknowledge the change
                request_handler.send_response(200)
                request_handler.send_header('Content-Type', 'application/json')
                request_handler.end_headers()
                
                response = {
                    '@odata.type': '#Bios.v1_1_0.Bios',
                    'Id': 'BIOS',
                    'Attributes': data.get('Attributes', {})
                }
                request_handler.wfile.write(json.dumps(response).encode('utf-8'))
            else:
                self._send_error_response(request_handler, 400, "Missing patch data")
        except Exception as e:
            logger.error(f"❌ BIOS PATCH error for {vm_name}: {e}")
            self._send_error_response(request_handler, 500, "Internal Server Error")
    
    def _handle_secure_boot_patch(self, request_handler, vm_name: str, path: str):
        """Handle SecureBoot PATCH requests"""
        try:
            content_length = int(request_handler.headers.get('Content-Length', 0))
            if content_length > 0:
                patch_data = request_handler.rfile.read(content_length)
                data = json.loads(patch_data.decode('utf-8'))
                
                logger.info(f"🔒 SecureBoot configuration change for {vm_name}: {data}")
                
                # For now, just acknowledge the change
                request_handler.send_response(200)
                request_handler.send_header('Content-Type', 'application/json')
                request_handler.end_headers()
                
                response = {
                    '@odata.type': '#SecureBoot.v1_1_0.SecureBoot',
                    'Id': 'SecureBoot',
                    'SecureBootEnable': data.get('SecureBootEnable', True)
                }
                request_handler.wfile.write(json.dumps(response).encode('utf-8'))
            else:
                self._send_error_response(request_handler, 400, "Missing patch data")
        except Exception as e:
            logger.error(f"❌ SecureBoot PATCH error for {vm_name}: {e}")
            self._send_error_response(request_handler, 500, "Internal Server Error")
    
    def _send_json_response(self, request_handler, status_code: int, data: Dict):
        """Send JSON response"""
        json_data = json.dumps(data, indent=2)
        request_handler.send_response(status_code)
        request_handler.send_header('Content-Type', 'application/json')
        request_handler.send_header('Content-Length', str(len(json_data)))
        request_handler.end_headers()
        request_handler.wfile.write(json_data.encode('utf-8'))
    
    def _send_error_response(self, request_handler, status_code: int, message: str):
        """Send error response"""
        error_data = {
            "error": {
                "code": f"Base.1.0.{status_code}",
                "message": message
            }
        }
        self._send_json_response(request_handler, status_code, error_data)
