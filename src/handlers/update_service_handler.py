#!/usr/bin/env python3
"""
Update Service Handler
Handles Redfish UpdateService endpoints for firmware/software management.
"""

import logging
from typing import Dict

from models.redfish_schemas import RedfishModels
from handlers.response_utils import RedfishResponseMixin

logger = logging.getLogger(__name__)


class UpdateServiceHandler(RedfishResponseMixin):
    """Handler for Redfish UpdateService endpoints"""
    
    def __init__(self):
        logger.info("🔄 UpdateService handler initialized")
    
    def handle_get(self, request_handler, path: str):
        """Handle GET requests for UpdateService"""
        logger.debug(f"🔄 UpdateService GET: {path}")
        
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
        elif path == '/redfish/v1/UpdateService/SoftwareInventory/BMC':
            data = self._get_bmc_software()
            self._send_json_response(request_handler, 200, data)
        elif path == '/redfish/v1/UpdateService/SoftwareInventory/RedfishServer':
            data = self._get_redfish_server_software()
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
