#!/usr/bin/env python3
"""
Managers Handler
Handles Redfish Managers endpoints for BMC management.
"""

import json
import logging
from datetime import datetime, timezone
from threading import Lock
from typing import Dict, Optional

from models.redfish_schemas import RedfishModels

logger = logging.getLogger(__name__)


class ManagersHandler:
    """Handler for Redfish Managers endpoints"""
    
    def __init__(self, vm_configs: Dict, vmware_clients: Dict, config: Dict = None):
        self.vm_configs = vm_configs
        self.vmware_clients = vmware_clients
        self.config = config or {}
        # In-memory virtual media state: { vm_name: { 'CD': {inserted, image, write_protected} } }
        self._media_state: Dict[str, Dict] = {}
        self._media_lock = Lock()
        logger.info("🔧 Managers handler initialized")

    def _get_media_state(self, vm_name: str, media_id: str = 'CD') -> Dict:
        """Return the current in-memory state for a virtual media slot, seeded from VMware if available."""
        with self._media_lock:
            if vm_name not in self._media_state:
                self._media_state[vm_name] = {}
            if media_id not in self._media_state[vm_name]:
                # Attempt to seed state from VMware
                state = {'inserted': False, 'image': None, 'write_protected': True, 'connected': False}
                client = self.vmware_clients.get(vm_name)
                if client and media_id == 'CD':
                    try:
                        iso_status = client.get_iso_status(vm_name)
                        if iso_status:
                            state['inserted'] = iso_status.get('inserted', False)
                            state['image'] = iso_status.get('image')
                            state['connected'] = iso_status.get('connected', False)
                    except Exception as e:
                        logger.debug(f"Could not seed ISO status for {vm_name}: {e}")
                self._media_state[vm_name][media_id] = state
            return dict(self._media_state[vm_name][media_id])

    def _set_media_state(self, vm_name: str, media_id: str, **kwargs):
        """Update in-memory state for a virtual media slot."""
        with self._media_lock:
            if vm_name not in self._media_state:
                self._media_state[vm_name] = {}
            if media_id not in self._media_state[vm_name]:
                self._media_state[vm_name][media_id] = {'inserted': False, 'image': None, 'write_protected': True, 'connected': False}
            self._media_state[vm_name][media_id].update(kwargs)

    def _get_virtual_media_datastore(self) -> Optional[str]:
        """Return the configured virtual_media_datastore, if any."""
        return self.config.get('virtual_media_datastore')

    def _delete_on_eject_enabled(self) -> bool:
        """Return True when the delete_on_eject option is enabled in config."""
        return bool(self.config.get('delete_on_eject', False))

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

    def handle_post(self, request_handler, path: str):
        """Handle POST requests for Managers (VirtualMedia actions)"""
        manager_id = self._extract_manager_id(path)
        if not manager_id:
            self._send_error_response(request_handler, 404, "Manager not found")
            return

        vm_name = manager_id.replace('-bmc', '') if manager_id.endswith('-bmc') else manager_id
        if vm_name not in self.vm_configs:
            self._send_error_response(request_handler, 404, "Manager not found")
            return

        if '/VirtualMedia/' in path and '/Actions/' in path:
            parts = path.split('/')
            try:
                media_id = parts[parts.index('VirtualMedia') + 1]
                action = parts[-1]
            except (ValueError, IndexError):
                self._send_error_response(request_handler, 404, "Not Found")
                return

            if action == 'VirtualMedia.InsertMedia':
                self._handle_insert_media(request_handler, vm_name, manager_id, media_id)
            elif action == 'VirtualMedia.EjectMedia':
                self._handle_eject_media(request_handler, vm_name, manager_id, media_id)
            else:
                self._send_error_response(request_handler, 405, "Unknown action")
        else:
            self._send_error_response(request_handler, 405, "Method not allowed")
    
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
        vm_name = manager_id.replace('-bmc', '') if manager_id.endswith('-bmc') else manager_id

        if path.endswith('/VirtualMedia'):
            # VirtualMedia collection
            data = {
                '@odata.type': '#VirtualMediaCollection.VirtualMediaCollection',
                '@odata.id': f'/redfish/v1/Managers/{manager_id}/VirtualMedia',
                'Name': 'Virtual Media Services',
                'Description': f'Virtual Media Services for {manager_id}',
                'Members@odata.count': 2,
                'Members': [
                    {'@odata.id': f'/redfish/v1/Managers/{manager_id}/VirtualMedia/CD'},
                    {'@odata.id': f'/redfish/v1/Managers/{manager_id}/VirtualMedia/Floppy'}
                ]
            }
            self._send_json_response(request_handler, 200, data)
        elif '/VirtualMedia/' in path:
            media_id = path.split('/')[-1]
            if media_id in ('CD', 'Floppy'):
                state = self._get_media_state(vm_name, media_id)
                image_uri = state.get('image') or ''
                data = {
                    '@odata.type': '#VirtualMedia.v1_3_0.VirtualMedia',
                    '@odata.id': f'/redfish/v1/Managers/{manager_id}/VirtualMedia/{media_id}',
                    'Id': media_id,
                    'Name': f'Virtual {media_id}',
                    'Description': f'Virtual {media_id} for {manager_id}',
                    'MediaTypes': ['CD', 'DVD'] if media_id == 'CD' else ['Floppy'],
                    'Image': image_uri,
                    'Inserted': state.get('inserted', False),
                    'Connected': state.get('connected', False),
                    'WriteProtected': state.get('write_protected', True),
                    'ConnectedVia': 'URI' if state.get('inserted') else 'NotConnected',
                    'TransferProtocolType': 'HTTP' if image_uri.startswith('http') else 'OEM',
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

    def _handle_insert_media(self, request_handler, vm_name: str, manager_id: str, media_id: str):
        """Handle VirtualMedia.InsertMedia POST action"""
        if media_id not in ('CD', 'Floppy'):
            self._send_error_response(request_handler, 404, "Virtual media not found")
            return

        try:
            content_length = int(request_handler.headers.get('Content-Length', 0))
            if not content_length:
                self._send_error_response(request_handler, 400, "Missing request body")
                return
            post_data = request_handler.rfile.read(content_length)
            body = json.loads(post_data.decode('utf-8'))
        except (json.JSONDecodeError, ValueError) as e:
            self._send_error_response(request_handler, 400, f"Invalid JSON: {e}")
            return

        image_url = body.get('Image') or body.get('image')
        if not image_url:
            self._send_error_response(request_handler, 400, "Missing required field: Image")
            return

        write_protected = body.get('WriteProtected', True)
        transferred = body.get('TransferProtocolType', 'HTTP')

        # Build the datastore path for vSphere from the Image URL / filename
        datastore = self._get_virtual_media_datastore()
        iso_path = self._resolve_iso_path(image_url, datastore, vm_name)
        if not iso_path:
            self._send_error_response(request_handler, 400, "Cannot resolve ISO path: configure virtual_media_datastore or provide a datastore path")
            return

        vmware_client = self.vmware_clients.get(vm_name)
        if not vmware_client:
            self._send_error_response(request_handler, 503, "VMware client not available")
            return

        logger.info(f"💿 Inserting virtual media for {vm_name}: {iso_path}")

        # If the Image is a remote URL, download and upload to the datastore first.
        # Skip this step when the caller already provided a datastore path.
        if image_url.lower().startswith(('http://', 'https://')):
            logger.info(f"☁️  Uploading ISO from {image_url} to {iso_path}")
            upload_ok = vmware_client.upload_iso_to_datastore(image_url, iso_path)
            if not upload_ok:
                self._send_error_response(request_handler, 500, "Failed to upload ISO to datastore")
                return

        success = vmware_client.mount_iso(vm_name, iso_path)
        if not success:
            self._send_error_response(request_handler, 500, "Failed to mount ISO")
            return

        self._set_media_state(vm_name, media_id, inserted=True, image=image_url, write_protected=write_protected, connected=True)
        logger.info(f"✅ Virtual media inserted for {vm_name}: {image_url}")
        request_handler.send_response(204)
        request_handler.end_headers()

    def _handle_eject_media(self, request_handler, vm_name: str, manager_id: str, media_id: str):
        """Handle VirtualMedia.EjectMedia POST action"""
        if media_id not in ('CD', 'Floppy'):
            self._send_error_response(request_handler, 404, "Virtual media not found")
            return

        state = self._get_media_state(vm_name, media_id)
        if not state.get('inserted'):
            self._send_error_response(request_handler, 400, "No media inserted")
            return

        vmware_client = self.vmware_clients.get(vm_name)
        if not vmware_client:
            self._send_error_response(request_handler, 503, "VMware client not available")
            return

        logger.info(f"⏏️  Ejecting virtual media for {vm_name} (force mode)")
        
        # Always use force eject to bypass OS locks
        success = vmware_client.unmount_iso(vm_name, force=True)
        
        if not success:
            self._send_error_response(request_handler, 500, "Failed to eject media")
            return

        self._set_media_state(vm_name, media_id, inserted=False, image=None, write_protected=True, connected=False)
        logger.info(f"✅ Virtual media ejected for {vm_name}")
        if self._delete_on_eject_enabled():
            iso_path = state.get('image')
            # Resolve to a datastore path if we only stored the original HTTP URL
            if iso_path and not (iso_path.startswith('[') and ']' in iso_path):
                datastore = self._get_virtual_media_datastore()
                iso_path = self._resolve_iso_path(iso_path, datastore, vm_name)
            if iso_path:
                if vmware_client.datastore_file_exists(iso_path):
                    logger.info(f"\U0001f5d1\ufe0f  delete_on_eject: removing {iso_path} from datastore")
                    deleted = vmware_client.delete_datastore_file(iso_path)
                    if not deleted:
                        logger.warning(f"\u26a0\ufe0f  delete_on_eject: failed to delete {iso_path}")
                else:
                    logger.info(
                        f"\U0001f5d1\ufe0f  delete_on_eject: skipping delete — file not found on datastore: {iso_path}"
                    )
            else:
                logger.warning("\u26a0\ufe0f  delete_on_eject: could not resolve datastore path; file not deleted")
        request_handler.send_response(204)
        request_handler.end_headers()

    def _resolve_iso_path(self, image_url: str, datastore: Optional[str], vm_name: str = '') -> Optional[str]:
        """
        Resolve an Image URL or filename to a vSphere datastore path.

        When *vm_name* is provided the stored filename is prefixed with
        ``<vm_name>_`` so that the same ISO mounted on different VMs never
        collides on the datastore.

        Accepts:
          - A full vSphere datastore path:  [DS] folder/file.iso
          - An HTTP/HTTPS URL:              https://host/path/file.iso
          - A plain filename:               file.iso  (requires virtual_media_datastore in config)
        """
        # Already a datastore path — return as-is (caller controls uniqueness)
        if image_url.startswith('[') and ']' in image_url:
            return image_url

        # Derive filename from URL or use as-is
        filename = image_url
        if '/' in image_url:
            filename = image_url.rstrip('/').split('/')[-1]

        if not filename.lower().endswith('.iso'):
            logger.warning(f"⚠️  Image does not appear to be an ISO file: {filename}")

        # Prefix with vm_name to guarantee uniqueness per VM
        if vm_name:
            filename = f"{vm_name}_{filename}"

        if not datastore:
            logger.warning("⚠️  virtual_media_datastore not configured; cannot resolve datastore path")
            return None

        # Strip trailing slash from datastore config value
        datastore = datastore.rstrip('/')

        # If datastore is already in bracket notation: [DatastoreName] folder
        if datastore.startswith('['):
            return f"{datastore}/{filename}"

        # Otherwise treat as plain datastore name
        return f"[{datastore}] {filename}"

    
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
