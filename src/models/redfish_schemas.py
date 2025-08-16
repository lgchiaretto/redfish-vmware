#!/usr/bin/env python3
"""
Redfish Data Models
Contains data structures and schemas for Redfish responses.
"""

from typing import Dict, List, Optional


class RedfishModels:
    """Static methods for generating Redfish compliant responses"""
    
    @staticmethod
    def get_service_root() -> Dict:
        """Get Redfish service root"""
        return {
            '@odata.type': '#ServiceRoot.v1_5_0.ServiceRoot',
            '@odata.id': '/redfish/v1/',
            'Id': 'RootService',
            'Name': 'Redfish VMware Server',
            'RedfishVersion': '1.8.0',
            'UUID': 'c14d91c0-8c5f-4f9b-9b1f-9c5f8f9b1f9c',
            'Description': 'VMware Redfish Server for Metal3/Ironic compatibility',
            'Product': 'VMware Redfish Bridge',
            'ProtocolFeaturesSupported': {
                'ExcerptQuery': False,
                'ExpandQuery': {
                    'ExpandAll': True,
                    'Levels': True,
                    'MaxLevels': 6,
                    'NoLinks': True
                },
                'FilterQuery': True,
                'OnlyMemberQuery': True,
                'SelectQuery': True
            },
            'Systems': {
                '@odata.id': '/redfish/v1/Systems'
            },
            'Chassis': {
                '@odata.id': '/redfish/v1/Chassis'
            },
            'Managers': {
                '@odata.id': '/redfish/v1/Managers'
            },
            'SessionService': {
                '@odata.id': '/redfish/v1/SessionService'
            },
            'TaskService': {
                '@odata.id': '/redfish/v1/TaskService'
            },
            'UpdateService': {
                '@odata.id': '/redfish/v1/UpdateService'
            },
            'Links': {
                'Sessions': {
                    '@odata.id': '/redfish/v1/SessionService/Sessions'
                }
            }
        }
    
    @staticmethod
    def get_systems_collection(vm_names: List[str]) -> Dict:
        """Get Systems collection"""
        return {
            '@odata.type': '#ComputerSystemCollection.ComputerSystemCollection',
            '@odata.id': '/redfish/v1/Systems',
            'Name': 'Computer System Collection',
            'Description': 'Collection of Computer Systems',
            'Members@odata.count': len(vm_names),
            'Members': [
                {
                    '@odata.id': f'/redfish/v1/Systems/{vm_name}'
                }
                for vm_name in vm_names
            ]
        }
    
    @staticmethod
    def get_managers_collection(vm_names: List[str]) -> Dict:
        """Get Managers collection"""
        return {
            '@odata.type': '#ManagerCollection.ManagerCollection',
            '@odata.id': '/redfish/v1/Managers',
            'Name': 'Manager Collection',
            'Description': 'Collection of Managers',
            'Members@odata.count': len(vm_names),
            'Members': [
                {
                    '@odata.id': f'/redfish/v1/Managers/{vm_name}-bmc'
                }
                for vm_name in vm_names
            ]
        }
    
    @staticmethod
    def get_chassis_collection(vm_names: List[str]) -> Dict:
        """Get Chassis collection"""
        return {
            '@odata.type': '#ChassisCollection.ChassisCollection',
            '@odata.id': '/redfish/v1/Chassis',
            'Name': 'Chassis Collection',
            'Description': 'Collection of Chassis',
            'Members@odata.count': len(vm_names),
            'Members': [
                {
                    '@odata.id': f'/redfish/v1/Chassis/{vm_name}-chassis'
                }
                for vm_name in vm_names
            ]
        }
    
    @staticmethod
    def get_session_service() -> Dict:
        """Get SessionService information"""
        return {
            '@odata.type': '#SessionService.v1_1_7.SessionService',
            '@odata.id': '/redfish/v1/SessionService',
            'Id': 'SessionService',
            'Name': 'Session Service',
            'Description': 'Session Service for Redfish VMware Server',
            'Status': {
                'State': 'Enabled',
                'Health': 'OK'
            },
            'ServiceEnabled': True,
            'SessionTimeout': 600,
            'Sessions': {
                '@odata.id': '/redfish/v1/SessionService/Sessions'
            }
        }
    
    @staticmethod
    def get_update_service() -> Dict:
        """Get UpdateService for Metal3/Ironic compatibility"""
        return {
            '@odata.type': '#UpdateService.v1_5_0.UpdateService',
            '@odata.id': '/redfish/v1/UpdateService',
            'Id': 'UpdateService',
            'Name': 'Update Service',
            'Description': 'Service for updating firmware and software',
            'Status': {
                'State': 'Enabled',
                'Health': 'OK'
            },
            'ServiceEnabled': True,
            'FirmwareInventory': {
                '@odata.id': '/redfish/v1/UpdateService/FirmwareInventory'
            },
            'SoftwareInventory': {
                '@odata.id': '/redfish/v1/UpdateService/SoftwareInventory'
            }
        }
    
    @staticmethod
    def get_firmware_inventory() -> Dict:
        """Get FirmwareInventory collection for Metal3/Ironic"""
        return {
            '@odata.type': '#SoftwareInventoryCollection.SoftwareInventoryCollection',
            '@odata.id': '/redfish/v1/UpdateService/FirmwareInventory',
            'Name': 'Firmware Inventory Collection',
            'Description': 'Collection of Firmware Components',
            'Members@odata.count': 1,
            'Members': [
                {
                    '@odata.id': '/redfish/v1/UpdateService/FirmwareInventory/BIOS'
                }
            ]
        }
    
    @staticmethod
    def get_bios_firmware() -> Dict:
        """Get BIOS firmware component for Metal3/Ironic"""
        return {
            '@odata.type': '#SoftwareInventory.v1_1_0.SoftwareInventory',
            '@odata.id': '/redfish/v1/UpdateService/FirmwareInventory/BIOS',
            'Id': 'BIOS',
            'Name': 'System BIOS',
            'Description': 'System BIOS Firmware',
            'Status': {
                'State': 'Enabled',
                'Health': 'OK'
            },
            'SoftwareId': 'BIOS',
            'Version': '2.0.0',
            'Updateable': True,
            'ReleaseDate': '2024-01-01T00:00:00Z'
        }
    
    @staticmethod
    def get_power_state_mapping() -> Dict[str, str]:
        """Get VMware to Redfish power state mapping"""
        return {
            'poweredOn': 'On',
            'poweredOff': 'Off',
            'suspended': 'PoweringOn'  # Treat suspended as transitional state
        }
