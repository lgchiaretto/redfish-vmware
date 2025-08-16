#!/usr/bin/env python3
"""
Update Service Handler
Handles Redfish UpdateService endpoints for firmware/software management.
"""

import json
import logging
from typing import Dict, Optional

from models.redfish_schemas import RedfishModels

logger = logging.getLogger(__name__)


class UpdateServiceHandler:
    """Handler for Redfish UpdateService endpoints"""
    
    def __init__(self, vm_configs: Dict, vmware_clients: Dict, task_manager):
        self.vm_configs = vm_configs
        self.vmware_clients = vmware_clients
        self.task_manager = task_manager
        logger.info("🔄 UpdateService handler initialized")
    
    def handle_get(self, request_handler, path: str):
        """Handle GET requests for UpdateService"""
        logger.warning(f"🔄 CRITICAL UpdateService GET: {path}")
        
        if path == '/redfish/v1/UpdateService':
            # UpdateService root
            data = RedfishModels.get_update_service()
            self._send_json_response(request_handler, 200, data)
        elif path == '/redfish/v1/UpdateService/FirmwareInventory':
            # FirmwareInventory collection
            data = RedfishModels.get_firmware_inventory()
            self._send_json_response(request_handler, 200, data)
        elif path == '/redfish/v1/UpdateService/FirmwareInventory/BIOS':
            # BIOS firmware component
            data = RedfishModels.get_bios_firmware()
            self._send_json_response(request_handler, 200, data)
        elif path == '/redfish/v1/UpdateService/SoftwareInventory':
            # SoftwareInventory collection
            data = self._get_software_inventory()
            self._send_json_response(request_handler, 200, data)
        else:
            self._send_error_response(request_handler, 404, "Not Found")
    
    def _get_software_inventory(self) -> Dict:
        """Get software inventory collection"""
        return {
            '@odata.type': '#SoftwareInventoryCollection.SoftwareInventoryCollection',
            '@odata.id': '/redfish/v1/UpdateService/SoftwareInventory',
            'Name': 'Software Inventory Collection',
            'Description': 'Collection of Software Components',
            'Members@odata.count': 2,
            'Members': [
                {
                    '@odata.id': '/redfish/v1/UpdateService/SoftwareInventory/BMC'
                },
                {
                    '@odata.id': '/redfish/v1/UpdateService/SoftwareInventory/RedfishServer'
                }
            ]
        }
    
    def _get_bmc_software(self) -> Dict:
        """Get BMC software component"""
        return {
            '@odata.type': '#SoftwareInventory.v1_1_0.SoftwareInventory',
            '@odata.id': '/redfish/v1/UpdateService/SoftwareInventory/BMC',
            'Id': 'BMC',
            'Name': 'BMC Firmware',
            'Description': 'Base Management Controller Firmware',
            'Status': {
                'State': 'Enabled',
                'Health': 'OK'
            },
            'SoftwareId': 'BMC',
            'Version': '2.0.0',
            'Updateable': True,
            'ReleaseDate': '2024-01-01T00:00:00Z'
        }
    
    def _get_redfish_server_software(self) -> Dict:
        """Get Redfish Server software component"""
        return {
            '@odata.type': '#SoftwareInventory.v1_1_0.SoftwareInventory',
            '@odata.id': '/redfish/v1/UpdateService/SoftwareInventory/RedfishServer',
            'Id': 'RedfishServer',
            'Name': 'Redfish Server',
            'Description': 'VMware Redfish Server Software',
            'Status': {
                'State': 'Enabled',
                'Health': 'OK'
            },
            'SoftwareId': 'RedfishServer',
            'Version': '3.0.0',
            'Updateable': True,
            'ReleaseDate': '2024-08-16T00:00:00Z'
        }
    
    def _send_json_response(self, request_handler, status_code: int, data: Dict):
        """Send JSON response"""
        json_data = json.dumps(data, indent=2)
        
        # Special logging for UpdateService responses
        logger.warning(f"🔄 UpdateService Response {status_code}: {len(json_data)} bytes")
        logger.debug(f"🔄 UpdateService Response Data: {json_data[:200]}...")
        
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
