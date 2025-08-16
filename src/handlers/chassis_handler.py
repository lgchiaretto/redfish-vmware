#!/usr/bin/env python3
"""
Chassis Handler
Handles Redfish Chassis endpoints for physical/virtual chassis management.
"""

import json
import logging
from typing import Dict, Optional

from models.redfish_schemas import RedfishModels

logger = logging.getLogger(__name__)


class ChassisHandler:
    """Handler for Redfish Chassis endpoints"""
    
    def __init__(self, vm_configs: Dict, vmware_clients: Dict):
        self.vm_configs = vm_configs
        self.vmware_clients = vmware_clients
        logger.info("🏗️ Chassis handler initialized")
    
    def handle_get(self, request_handler, path: str):
        """Handle GET requests for Chassis"""
        if path == '/redfish/v1/Chassis':
            # Chassis collection
            data = RedfishModels.get_chassis_collection(list(self.vm_configs.keys()))
            self._send_json_response(request_handler, 200, data)
        elif '/redfish/v1/Chassis/' in path:
            # Individual chassis
            chassis_id = self._extract_chassis_id(path)
            if chassis_id:
                vm_name = chassis_id.replace('-chassis', '') if chassis_id.endswith('-chassis') else chassis_id
                if vm_name in self.vm_configs:
                    if '/Power' in path:
                        self._handle_power_get(request_handler, chassis_id, path)
                    elif '/Thermal' in path:
                        self._handle_thermal_get(request_handler, chassis_id, path)
                    else:
                        data = self._get_chassis_info(chassis_id)
                        self._send_json_response(request_handler, 200, data)
                else:
                    self._send_error_response(request_handler, 404, "Chassis not found")
            else:
                self._send_error_response(request_handler, 404, "Chassis not found")
        else:
            self._send_error_response(request_handler, 404, "Not Found")
    
    def _extract_chassis_id(self, path: str) -> Optional[str]:
        """Extract chassis ID from path"""
        parts = path.split('/')
        if 'Chassis' in parts:
            chassis_index = parts.index('Chassis')
            if len(parts) > chassis_index + 1:
                return parts[chassis_index + 1]
        return None
    
    def _get_chassis_info(self, chassis_id: str) -> Dict:
        """Get chassis information"""
        vm_name = chassis_id.replace('-chassis', '') if chassis_id.endswith('-chassis') else chassis_id
        
        return {
            '@odata.type': '#Chassis.v1_15_0.Chassis',
            '@odata.id': f'/redfish/v1/Chassis/{chassis_id}',
            'Id': chassis_id,
            'Name': f'Chassis for {vm_name}',
            'Description': f'Virtual Chassis for VMware VM {vm_name}',
            'ChassisType': 'RackMount',
            'Manufacturer': 'VMware',
            'Model': 'Virtual Machine',
            'SKU': 'VMware VM',
            'SerialNumber': f'VMware-{vm_name}-Chassis',
            'PartNumber': 'VMware-Chassis',
            'AssetTag': f'{vm_name}-chassis',
            'Status': {
                'State': 'Enabled',
                'Health': 'OK'
            },
            'IndicatorLED': 'Off',
            'PowerState': 'On',
            'PhysicalSecurity': {
                'IntrusionSensorNumber': 1,
                'IntrusionSensor': 'Normal'
            },
            'Power': {
                '@odata.id': f'/redfish/v1/Chassis/{chassis_id}/Power'
            },
            'Thermal': {
                '@odata.id': f'/redfish/v1/Chassis/{chassis_id}/Thermal'
            },
            'Links': {
                'ComputerSystems': [
                    {
                        '@odata.id': f'/redfish/v1/Systems/{vm_name}'
                    }
                ],
                'ManagedBy': [
                    {
                        '@odata.id': f'/redfish/v1/Managers/{vm_name}-bmc'
                    }
                ]
            }
        }
    
    def _handle_power_get(self, request_handler, chassis_id: str, path: str):
        """Handle Power GET requests"""
        if path.endswith('/Power'):
            vm_name = chassis_id.replace('-chassis', '') if chassis_id.endswith('-chassis') else chassis_id
            
            data = {
                '@odata.type': '#Power.v1_6_0.Power',
                '@odata.id': f'/redfish/v1/Chassis/{chassis_id}/Power',
                'Id': 'Power',
                'Name': 'Power',
                'Description': f'Power Information for {chassis_id}',
                'PowerControl': [
                    {
                        '@odata.id': f'/redfish/v1/Chassis/{chassis_id}/Power#/PowerControl/0',
                        'MemberId': '0',
                        'Name': 'System Power Control',
                        'PowerConsumedWatts': 150,
                        'PowerRequestedWatts': 200,
                        'PowerAvailableWatts': 800,
                        'PowerCapacityWatts': 1000,
                        'PowerAllocatedWatts': 200,
                        'PowerMetrics': {
                            'IntervalInMin': 1,
                            'MinConsumedWatts': 100,
                            'MaxConsumedWatts': 300,
                            'AverageConsumedWatts': 150
                        },
                        'PowerLimit': {
                            'LimitInWatts': 500,
                            'LimitException': 'NoAction',
                            'CorrectionInMs': 1000
                        },
                        'RelatedItem': [
                            {
                                '@odata.id': f'/redfish/v1/Systems/{vm_name}'
                            },
                            {
                                '@odata.id': f'/redfish/v1/Chassis/{chassis_id}'
                            }
                        ],
                        'Status': {
                            'State': 'Enabled',
                            'Health': 'OK'
                        }
                    }
                ],
                'PowerSupplies': [
                    {
                        '@odata.id': f'/redfish/v1/Chassis/{chassis_id}/Power#/PowerSupplies/0',
                        'MemberId': '0',
                        'Name': 'Power Supply 1',
                        'Status': {
                            'State': 'Enabled',
                            'Health': 'OK'
                        },
                        'PowerSupplyType': 'AC',
                        'LineInputVoltageType': 'AC120V',
                        'LineInputVoltage': 120,
                        'PowerCapacityWatts': 1000,
                        'LastPowerOutputWatts': 150,
                        'Model': 'Virtual PSU',
                        'Manufacturer': 'VMware',
                        'FirmwareVersion': '1.0.0',
                        'SerialNumber': f'PSU-{vm_name}-001',
                        'PartNumber': 'VMware-PSU-1000W',
                        'SparePartNumber': 'VMware-PSU-1000W-SPARE',
                        'InputRanges': [
                            {
                                'InputType': 'AC',
                                'MinimumVoltage': 100,
                                'MaximumVoltage': 240,
                                'MinimumFrequencyHz': 50,
                                'MaximumFrequencyHz': 60,
                                'OutputWattage': 1000
                            }
                        ],
                        'IndicatorLED': 'Off',
                        'Redundancy': [
                            {
                                '@odata.id': f'/redfish/v1/Chassis/{chassis_id}/Power#/Redundancy/0'
                            }
                        ],
                        'RelatedItem': [
                            {
                                '@odata.id': f'/redfish/v1/Chassis/{chassis_id}'
                            }
                        ]
                    }
                ],
                'Redundancy': [
                    {
                        '@odata.id': f'/redfish/v1/Chassis/{chassis_id}/Power#/Redundancy/0',
                        'MemberId': '0',
                        'Name': 'PowerSupply Redundancy Group 1',
                        'Mode': 'N+1',
                        'Status': {
                            'State': 'Enabled',
                            'Health': 'OK'
                        },
                        'RedundancySet': [
                            {
                                '@odata.id': f'/redfish/v1/Chassis/{chassis_id}/Power#/PowerSupplies/0'
                            }
                        ],
                        'MinNumNeeded': 1,
                        'MaxNumSupported': 2
                    }
                ]
            }
            self._send_json_response(request_handler, 200, data)
        else:
            self._send_error_response(request_handler, 404, "Not Found")
    
    def _handle_thermal_get(self, request_handler, chassis_id: str, path: str):
        """Handle Thermal GET requests"""
        if path.endswith('/Thermal'):
            vm_name = chassis_id.replace('-chassis', '') if chassis_id.endswith('-chassis') else chassis_id
            
            data = {
                '@odata.type': '#Thermal.v1_6_0.Thermal',
                '@odata.id': f'/redfish/v1/Chassis/{chassis_id}/Thermal',
                'Id': 'Thermal',
                'Name': 'Thermal',
                'Description': f'Thermal Information for {chassis_id}',
                'Temperatures': [
                    {
                        '@odata.id': f'/redfish/v1/Chassis/{chassis_id}/Thermal#/Temperatures/0',
                        'MemberId': '0',
                        'Name': 'CPU Temperature',
                        'SensorNumber': 1,
                        'Status': {
                            'State': 'Enabled',
                            'Health': 'OK'
                        },
                        'ReadingCelsius': 45,
                        'UpperThresholdNonCritical': 70,
                        'UpperThresholdCritical': 85,
                        'UpperThresholdFatal': 95,
                        'LowerThresholdNonCritical': 5,
                        'LowerThresholdCritical': 0,
                        'LowerThresholdFatal': -5,
                        'MinReadingRangeTemp': -10,
                        'MaxReadingRangeTemp': 100,
                        'PhysicalContext': 'CPU',
                        'RelatedItem': [
                            {
                                '@odata.id': f'/redfish/v1/Systems/{vm_name}'
                            }
                        ]
                    },
                    {
                        '@odata.id': f'/redfish/v1/Chassis/{chassis_id}/Thermal#/Temperatures/1',
                        'MemberId': '1',
                        'Name': 'System Temperature',
                        'SensorNumber': 2,
                        'Status': {
                            'State': 'Enabled',
                            'Health': 'OK'
                        },
                        'ReadingCelsius': 35,
                        'UpperThresholdNonCritical': 60,
                        'UpperThresholdCritical': 75,
                        'UpperThresholdFatal': 85,
                        'LowerThresholdNonCritical': 5,
                        'LowerThresholdCritical': 0,
                        'LowerThresholdFatal': -5,
                        'MinReadingRangeTemp': -10,
                        'MaxReadingRangeTemp': 100,
                        'PhysicalContext': 'SystemBoard',
                        'RelatedItem': [
                            {
                                '@odata.id': f'/redfish/v1/Chassis/{chassis_id}'
                            }
                        ]
                    }
                ],
                'Fans': [
                    {
                        '@odata.id': f'/redfish/v1/Chassis/{chassis_id}/Thermal#/Fans/0',
                        'MemberId': '0',
                        'Name': 'CPU Fan',
                        'Status': {
                            'State': 'Enabled',
                            'Health': 'OK'
                        },
                        'Reading': 2500,
                        'ReadingUnits': 'RPM',
                        'UpperThresholdNonCritical': 4000,
                        'UpperThresholdCritical': 5000,
                        'UpperThresholdFatal': 6000,
                        'LowerThresholdNonCritical': 1000,
                        'LowerThresholdCritical': 500,
                        'LowerThresholdFatal': 100,
                        'MinReadingRange': 0,
                        'MaxReadingRange': 6000,
                        'PhysicalContext': 'CPU',
                        'Redundancy': [
                            {
                                '@odata.id': f'/redfish/v1/Chassis/{chassis_id}/Thermal#/Redundancy/0'
                            }
                        ],
                        'RelatedItem': [
                            {
                                '@odata.id': f'/redfish/v1/Systems/{vm_name}'
                            }
                        ]
                    },
                    {
                        '@odata.id': f'/redfish/v1/Chassis/{chassis_id}/Thermal#/Fans/1',
                        'MemberId': '1',
                        'Name': 'System Fan',
                        'Status': {
                            'State': 'Enabled',
                            'Health': 'OK'
                        },
                        'Reading': 1800,
                        'ReadingUnits': 'RPM',
                        'UpperThresholdNonCritical': 3500,
                        'UpperThresholdCritical': 4000,
                        'UpperThresholdFatal': 4500,
                        'LowerThresholdNonCritical': 800,
                        'LowerThresholdCritical': 400,
                        'LowerThresholdFatal': 100,
                        'MinReadingRange': 0,
                        'MaxReadingRange': 5000,
                        'PhysicalContext': 'SystemBoard',
                        'Redundancy': [
                            {
                                '@odata.id': f'/redfish/v1/Chassis/{chassis_id}/Thermal#/Redundancy/0'
                            }
                        ],
                        'RelatedItem': [
                            {
                                '@odata.id': f'/redfish/v1/Chassis/{chassis_id}'
                            }
                        ]
                    }
                ],
                'Redundancy': [
                    {
                        '@odata.id': f'/redfish/v1/Chassis/{chassis_id}/Thermal#/Redundancy/0',
                        'MemberId': '0',
                        'Name': 'Fan Redundancy Group 1',
                        'Mode': 'N+1',
                        'Status': {
                            'State': 'Enabled',
                            'Health': 'OK'
                        },
                        'RedundancySet': [
                            {
                                '@odata.id': f'/redfish/v1/Chassis/{chassis_id}/Thermal#/Fans/0'
                            },
                            {
                                '@odata.id': f'/redfish/v1/Chassis/{chassis_id}/Thermal#/Fans/1'
                            }
                        ],
                        'MinNumNeeded': 1,
                        'MaxNumSupported': 2
                    }
                ]
            }
            self._send_json_response(request_handler, 200, data)
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
