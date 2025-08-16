#!/usr/bin/env python3
"""
Managers Handler
Handles Redfish Managers endpoints for BMC management.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from models.redfish_schemas import RedfishModels

logger = logging.getLogger(__name__)


class ManagersHandler:
    """Handler for Redfish Managers endpoints"""
    
    def __init__(self, vm_configs: Dict, vmware_clients: Dict):
        self.vm_configs = vm_configs
        self.vmware_clients = vmware_clients
        logger.info("🔧 Managers handler initialized")
    
    def handle_get(self, request_handler, path: str):
        """Handle GET requests for Managers"""
        if path == '/redfish/v1/Managers':
            # Managers collection
            data = RedfishModels.get_managers_collection(list(self.vm_configs.keys()))
            self._send_json_response(request_handler, 200, data)
        elif '/redfish/v1/Managers/' in path:
            # Individual manager
            manager_id = self._extract_manager_id(path)
            if manager_id:
                vm_name = manager_id.replace('-bmc', '') if manager_id.endswith('-bmc') else manager_id
                if vm_name in self.vm_configs:
                    if '/VirtualMedia' in path:
                        self._handle_virtual_media_get(request_handler, manager_id, path)
                    elif '/EthernetInterfaces' in path:
                        self._handle_ethernet_interfaces_get(request_handler, manager_id, path)
                    else:
                        data = self._get_manager_info(manager_id)
                        self._send_json_response(request_handler, 200, data)
                else:
                    self._send_error_response(request_handler, 404, "Manager not found")
            else:
                self._send_error_response(request_handler, 404, "Manager not found")
        else:
            self._send_error_response(request_handler, 404, "Not Found")
    
    def _extract_manager_id(self, path: str) -> Optional[str]:
        """Extract manager ID from path"""
        parts = path.split('/')
        if 'Managers' in parts:
            managers_index = parts.index('Managers')
            if len(parts) > managers_index + 1:
                return parts[managers_index + 1]
        return None
    
    def _get_manager_info(self, manager_id: str) -> Dict:
        """Get manager information"""
        vm_name = manager_id.replace('-bmc', '') if manager_id.endswith('-bmc') else manager_id
        
        return {
            '@odata.type': '#Manager.v1_13_0.Manager',
            '@odata.id': f'/redfish/v1/Managers/{manager_id}',
            'Id': manager_id,
            'Name': f'Manager for {vm_name}',
            'Description': f'BMC for VMware VM {vm_name}',
            'ManagerType': 'BMC',
            'UUID': f'42{vm_name[-8:].ljust(8, "0")}-2938-2342-8820-489239905424',
            'Model': 'VMware vBMC',
            'Manufacturer': 'VMware',
            'FirmwareVersion': '2.0.0',
            'Status': {
                'State': 'Enabled',
                'Health': 'OK'
            },
            'DateTime': datetime.now(timezone.utc).isoformat(),
            'DateTimeLocalOffset': '+00:00',
            'ServiceIdentification': {
                'Product': 'VMware Redfish Server',
                'Vendor': 'VMware'
            },
            'PowerState': 'On',
            'VirtualMedia': {
                '@odata.id': f'/redfish/v1/Managers/{manager_id}/VirtualMedia'
            },
            'EthernetInterfaces': {
                '@odata.id': f'/redfish/v1/Managers/{manager_id}/EthernetInterfaces'
            },
            'Actions': {
                '#Manager.Reset': {
                    'target': f'/redfish/v1/Managers/{manager_id}/Actions/Manager.Reset',
                    'ResetType@Redfish.AllowableValues': [
                        'ForceRestart', 'GracefulRestart'
                    ]
                }
            },
            'Links': {
                'ManagerForSystems': [
                    {
                        '@odata.id': f'/redfish/v1/Systems/{vm_name}'
                    }
                ],
                'ManagerForChassis': [
                    {
                        '@odata.id': f'/redfish/v1/Chassis/{vm_name}-chassis'
                    }
                ]
            }
        }
    
    def _handle_virtual_media_get(self, request_handler, manager_id: str, path: str):
        """Handle VirtualMedia GET requests"""
        if path.endswith('/VirtualMedia'):
            # VirtualMedia collection
            data = {
                '@odata.type': '#VirtualMediaCollection.VirtualMediaCollection',
                '@odata.id': f'/redfish/v1/Managers/{manager_id}/VirtualMedia',
                'Name': 'Virtual Media Services',
                'Description': f'Virtual Media Services for {manager_id}',
                'Members@odata.count': 2,
                'Members': [
                    {
                        '@odata.id': f'/redfish/v1/Managers/{manager_id}/VirtualMedia/CD'
                    },
                    {
                        '@odata.id': f'/redfish/v1/Managers/{manager_id}/VirtualMedia/Floppy'
                    }
                ]
            }
            self._send_json_response(request_handler, 200, data)
        elif '/VirtualMedia/' in path:
            # Individual virtual media
            media_id = path.split('/')[-1]
            if media_id in ['CD', 'Floppy']:
                data = {
                    '@odata.type': '#VirtualMedia.v1_3_0.VirtualMedia',
                    '@odata.id': f'/redfish/v1/Managers/{manager_id}/VirtualMedia/{media_id}',
                    'Id': media_id,
                    'Name': f'Virtual {media_id}',
                    'Description': f'Virtual {media_id} for {manager_id}',
                    'MediaTypes': ['CD', 'DVD'] if media_id == 'CD' else ['Floppy'],
                    'Connected': False,
                    'Inserted': False,
                    'WriteProtected': True,
                    'ConnectedVia': 'NotConnected',
                    'Actions': {
                        '#VirtualMedia.InsertMedia': {
                            'target': f'/redfish/v1/Managers/{manager_id}/VirtualMedia/{media_id}/Actions/VirtualMedia.InsertMedia'
                        },
                        '#VirtualMedia.EjectMedia': {
                            'target': f'/redfish/v1/Managers/{manager_id}/VirtualMedia/{media_id}/Actions/VirtualMedia.EjectMedia'
                        }
                    }
                }
                self._send_json_response(request_handler, 200, data)
            else:
                self._send_error_response(request_handler, 404, "Virtual media not found")
        else:
            self._send_error_response(request_handler, 404, "Not Found")
    
    def _handle_ethernet_interfaces_get(self, request_handler, manager_id: str, path: str):
        """Handle EthernetInterfaces GET requests"""
        if path.endswith('/EthernetInterfaces'):
            # EthernetInterfaces collection
            data = {
                '@odata.type': '#EthernetInterfaceCollection.EthernetInterfaceCollection',
                '@odata.id': f'/redfish/v1/Managers/{manager_id}/EthernetInterfaces',
                'Name': 'Ethernet Network Interface Collection',
                'Description': f'Ethernet Network Interface Collection for {manager_id}',
                'Members@odata.count': 1,
                'Members': [
                    {
                        '@odata.id': f'/redfish/v1/Managers/{manager_id}/EthernetInterfaces/eth0'
                    }
                ]
            }
            self._send_json_response(request_handler, 200, data)
        elif '/EthernetInterfaces/' in path:
            # Individual ethernet interface
            interface_id = path.split('/')[-1]
            if interface_id == 'eth0':
                data = {
                    '@odata.type': '#EthernetInterface.v1_6_0.EthernetInterface',
                    '@odata.id': f'/redfish/v1/Managers/{manager_id}/EthernetInterfaces/{interface_id}',
                    'Id': interface_id,
                    'Name': 'Management Network Interface',
                    'Description': f'Management Network Interface for {manager_id}',
                    'Status': {
                        'State': 'Enabled',
                        'Health': 'OK'
                    },
                    'InterfaceEnabled': True,
                    'PermanentMACAddress': '00:50:56:84:56:78',
                    'MACAddress': '00:50:56:84:56:78',
                    'SpeedMbps': 1000,
                    'FullDuplex': True,
                    'HostName': f'{manager_id}.local',
                    'FQDN': f'{manager_id}.local',
                    'IPv4Addresses': [
                        {
                            'Address': '192.168.1.100',
                            'SubnetMask': '255.255.255.0',
                            'AddressOrigin': 'Static',
                            'Gateway': '192.168.1.1'
                        }
                    ],
                    'IPv6AddressOriginCounts': {
                        'LinkLocal': 0,
                        'Static': 0,
                        'DHCP': 0,
                        'SLAAC': 0
                    },
                    'IPv6StaticAddresses': [],
                    'NameServers': ['8.8.8.8', '8.8.4.4']
                }
                self._send_json_response(request_handler, 200, data)
            else:
                self._send_error_response(request_handler, 404, "Interface not found")
        else:
            self._send_error_response(request_handler, 404, "Not Found")
    
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
