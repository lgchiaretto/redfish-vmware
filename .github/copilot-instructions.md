# Redfish VMware Bridge - AI Agent Instructions

## Project Overview
This is a **Redfish-to-VMware vSphere bridge** that translates standard Redfish REST API calls into VMware vSphere operations. Built specifically for **OpenShift Metal3/Ironic** integration to manage VMware VMs as if they were bare metal hosts.

**Critical Context**: This is an AI-generated codebase designed for production Metal3 deployments. The architecture prioritizes Metal3 compatibility over generic Redfish compliance.

## Architecture Deep Dive

### Single-Server Design Pattern
- **One Redfish server instance for all VMs** - A single HTTP(S) listener serves all Redfish endpoints.
- The server listens on a top-level `redfish_port` configured in `config/config.json` (or via `REDFISH_PORT` environment variable in the service unit).
- VM selection is done using the `{ID}` portion of the Redfish URI: `/redfish/v1/Systems/{ID}`.
- This simplifies deployment and avoids per-VM port management; clients address different VMs by changing the `{ID}` path segment.

**Example**: The server listens on port 8443; `vm-master-1` is accessible at `http://bastion.example.com:8443/redfish/v1/Systems/vm-master-1`

### Handler-Based Modular Architecture
Located in `src/handlers/`, each handler is specialized:
- `systems_handler.py` - VM power, boot, BIOS, storage, SecureBoot, Processors, Memory, NetworkInterfaces, EthernetInterfaces operations
- `managers_handler.py` - BMC management, virtual media upload/mount/eject operations
- `chassis_handler.py` - Physical chassis representation
- `update_service_handler.py` - Firmware updates and software inventory (Metal3 inspection)
- `http_handler.py` - Base HTTP request routing with authentication
- `redfish_handler.py` - Top-level router; also holds `refresh_vm_configs()` for dynamic VM updates

**Pattern**: Handlers receive `(request_handler, path)` and route to internal methods like `_handle_system_action()`, `_handle_bios_patch()`.

### VMware Operations Layer
Modularized VMware API interactions in `src/vmware/`:
- `connection.py` - Manages single vSphere connection with SSL verification toggle
- `vm_operations.py` - VM discovery, info retrieval, state management
- `power_operations.py` - All power operations (on/off/reset/graceful)
- `media_operations.py` - ISO upload, mounting, boot order, datastore file deletion

**Key Pattern**: `VMwareClient` in `vmware_client.py` aggregates these modules and exposes a unified interface. Operations return boolean success/failure.

### Task Management System
Metal3 requires asynchronous operation tracking. `src/tasks/manager.py` provides:
- Dynamic task creation with UUID generation
- Automatic task cleanup (completed tasks >1 hour old removed)
- Initial tasks created on startup for Metal3 compatibility
- Progress tracking (0-100%) with state machine: `New → Running → Completed/Exception`

**Metal3 Integration**: Update operations and RAID configuration return task URIs like `/redfish/v1/TaskService/Tasks/{task_id}`

## Configuration & Deployment

### Config Structure (`config/config.json`)
```json
{
  "vmware": { /* global vCenter connection */ },
  "vms": [
    {
      "name": "vm-name",              // VM name in vCenter
      "vcenter_host": "...",
      "vcenter_user": "...",
      "vcenter_password": "...",
      "redfish_user": "admin",        // Per-VM Redfish credentials
      "redfish_password": "password",
      "discovered": false,            // Auto-populated if from datacenter_folders
      "discovered_from": "..."        // Path if auto-discovered
    }
  ],
  "datacenter_folders": [
    {
      "datacenter": "Datacenter1",    // vCenter datacenter name
      "folder_path": "vm/prod/kubernetes"  // Folder path for VM discovery
    }
  ],
  "redfish_port": 8443,                             // Top-level port for single server
  "disable_ssl": true,                              // Top-level SSL toggle
  "datacenter_folder_refresh_interval_seconds": 300, // How often to re-scan folders (default 300)
  "virtual_media_datastore": "DatastoreName",       // Datastore for ISO uploads
  "delete_on_eject": false,                         // Auto-delete ISO from datastore on eject
  "ssl": {  /* Optional: Let's Encrypt cert paths */ }
}
```

### VM Auto-Discovery from Datacenter Folders
Automatically discover and manage VMs from vCenter datacenter folders.

**Discovery Flow**:
1. Configuration loaded from `config/config.json`
2. `_validate_config()` checks for `vms` or `datacenter_folders` (or both)
3. `_discover_vms_from_folders()` called at startup; `_refresh_discovered_vms_from_folders()` called periodically:
   - Iterates through each `datacenter_folders` entry
   - Creates temporary VMware connection using global `vmware` credentials
   - Calls `vm_operations.list_vms_in_folder(datacenter, folder_path)`
   - Recursively discovers VMs in folder hierarchy
   - Skips VMs already in manual `vms` list (name match)
   - Adds discovered VMs with `"discovered": true` and `"discovered_from"` metadata
4. On refresh, stale discovered VMs (no longer found in vCenter) are pruned via `_prune_stale_discovered_vms()`
5. After each refresh, `redfish_handler.refresh_vm_configs()` is called to update the running handler

**Periodic Refresh**:
- Controlled by `datacenter_folder_refresh_interval_seconds` in config (default: 300 seconds / 5 minutes)
- Background thread `FolderRefreshMonitor` started alongside `HealthReporter` after server startup
- Stale discovered entries are removed; new VMs are added and VMware clients initialized on demand

**Implementation Details**:
- `VMOperations.list_vms_in_folder()` - Finds folder by datacenter + path, recursively collects VMs
- `VMOperations.get_folder_by_path()` - Navigates folder hierarchy (e.g., `vm/prod/k8s`)
- `VMOperations._collect_vms_recursive()` - Traverses folder tree, adds vim.VirtualMachine objects
- `RedfishServer._prune_stale_discovered_vms(config, active_set)` - Removes discovered VMs not in active set
- `RedfishHandler.refresh_vm_configs(vm_configs, config)` - Refreshes all sub-handler VM registries and VMware clients

**Folder Path Format**:
- `vm` - All VMs in datacenter root folder
- `vm/prod` - VMs in `prod` subfolder
- `vm/prod/kubernetes` - Nested folder search (recursive)
- Path is case-sensitive and must match vCenter folder names exactly

**Error Handling**:
- Invalid datacenter/folder logs warning and skips that entry
- Missing VMware credentials falls back to manual VMs only
- No exception thrown - discovery failures are non-blocking
- Temporary connection properly disconnected after each discovery

### SystemD Service Pattern
Production deployment uses `config/redfish-vmware-server.service`:
- Runs as dedicated user (created by `setup.sh`)
- Auto-restart on failure
- Logs to journald: `sudo journalctl -u redfish-vmware-server -f`
- Debug control via environment: `Environment=REDFISH_DEBUG=true` in service override

**Critical**: Use `setup.sh` for installation - it configures Python env, systemd, firewall, and validates VMware connectivity. Ensure `config/config.json` contains a top-level `redfish_port` (or set `REDFISH_PORT` in the systemd unit) so the single Redfish server listens on the expected port.

## Development Conventions

### Logging Strategy
**Production vs Debug**: Controlled by `REDFISH_DEBUG` environment variable (default: false)
- Production: INFO level, minimal format, no request details
- Debug: DEBUG level, includes file/line numbers, full HTTP request logging
- All loggers use emoji prefixes: 🚀 startup, ✅ success, ❌ errors, 🔍 Metal3 detection

**Pattern**: Use `logger.info()` for user-visible events, `logger.debug()` for request details, `logger.warning()` for SSL/auth issues.

### Authentication Model
Credentials are validated in `src/auth/manager.py` via `_check_credentials()`:
- **Legacy fallback**: `admin:password` is always accepted for backward compatibility
- **Per-VM credentials**: Any `(redfish_user, redfish_password)` pair defined in the `vms` list is accepted
- Public endpoints: `/redfish/v1/`, `/redfish/v1/Systems` (no auth)
- All other endpoints require HTTP Basic Auth
- Session tokens (Bearer) supported but Basic Auth is primary

### ComputerSystem Resource (GET /redfish/v1/Systems/{vm})
Returns a rich Redfish-compliant ComputerSystem payload including:
- Standard fields: `SystemType`, `PowerState`, `BiosVersion`, `Manufacturer`, `UUID`, `HostName`
- `ProcessorSummary`, `MemorySummary` from live VMware data
- Sub-resource links (top-level and inside `Links`): `Bios`, `SecureBoot`, `Storage`, `Processors`, `Memory`, `NetworkInterfaces`, `EthernetInterfaces`
- `Actions` for `ComputerSystem.Reset`
- `Links.Chassis`, `Links.ManagedBy`, `Links.Processors`, `Links.Memory`, `Links.NetworkInterfaces`, `Links.EthernetInterfaces`
- `Oem.VMware` block with `VMName`, `GuestOS`, `ToolsStatus`

### Sub-Resource Collection Endpoints
`SystemsHandler` serves Redfish collection payloads for:
- `/redfish/v1/Systems/{vm}/Processors`
- `/redfish/v1/Systems/{vm}/Memory`
- `/redfish/v1/Systems/{vm}/NetworkInterfaces`
- `/redfish/v1/Systems/{vm}/EthernetInterfaces`
- `/redfish/v1/Systems/{vm}/Storage` (also serves individual storage controller at `/Storage/1`)
- `/redfish/v1/Systems/{vm}/Bios`
- `/redfish/v1/Systems/{vm}/SecureBoot`

### PATCH Behaviour
- `PATCH /Systems/{vm}` with `Boot.*` - translates `BootSourceOverrideTarget` to a VMware boot order via `_BOOT_TARGET_MAP` and calls `vmware_client.set_vm_boot_order()`. Returns the updated full ComputerSystem.
- `PATCH /Systems/{vm}/Bios` - returns **501 Not Implemented** (VMware has no BIOS attribute API)
- `PATCH /Systems/{vm}/SecureBoot` - returns **501 Not Implemented** (requires firmware reconfiguration + power cycle)

### Virtual Media
Full virtual media lifecycle under `/redfish/v1/Managers/{vm}-bmc/VirtualMedia/`:

**GET** `/VirtualMedia` - collection (CD, Floppy)
**GET** `/VirtualMedia/{CD|Floppy}` - live state including `Inserted`, `Connected`, `Image`, `ConnectedVia`
**POST** `…/Actions/VirtualMedia.InsertMedia` - body `{"Image": "<url-or-datastore-path>", "WriteProtected": true}`
**POST** `…/Actions/VirtualMedia.EjectMedia` - no body required

**InsertMedia flow**:
1. Parse `Image` field from request body
2. Resolve to a vSphere datastore path using `_resolve_iso_path(image_url, datastore, vm_name)`
   - Stored filename is **prefixed with `{vm_name}_`** to prevent datastore collisions (e.g. `vm-master-0_rhcos.iso`)
   - Existing `[DS] path` values pass through unchanged
3. If `Image` is an HTTP/HTTPS URL, stream-download and upload to vSphere via the datastore browser HTTPS API (`MediaOperations.upload_iso_to_datastore`)
4. Mount the ISO to the VM's CD-ROM via `MediaOperations.mount_iso`
5. Update in-memory media state

**EjectMedia flow**:
1. Validate media is currently inserted
2. Unmount via `MediaOperations.unmount_iso`
3. If `delete_on_eject: true` in config, resolve the stored datastore path and call `MediaOperations.delete_datastore_file`
4. Clear in-memory media state

**Config options**:
- `virtual_media_datastore` - datastore name (`"DS1"`) or bracket notation (`"[DS1] isos/"`)
- `delete_on_eject` - boolean, default `false`

**Datastore upload implementation** (`MediaOperations.upload_iso_to_datastore`):
- Parses `[DatastoreName] folder/file.iso` into ds_name and file_path
- Resolves the hosting datacenter via `_get_datacenter_name_for_datastore()`
- Builds `https://<vcenter>/folder/<path>?dcPath=<dc>&dsName=<ds>` upload URL
- Authenticates with the pyVmomi SOAP session cookie (`_get_vsphere_session_cookie()`)
- Streams ISO download from source URL then PUTs to vSphere

**Datastore file deletion** (`MediaOperations.delete_datastore_file`):
- Uses `ServiceContent.fileManager.DeleteFile()` API
- Resolves first available datacenter for the file manager call

### Error Handling Pattern
Handlers use consistent response methods:
```python
self._send_json_response(request_handler, 200, data)
self._send_error_response(request_handler, 404, "System not found")
```
VMware operations return `True/False` - handlers translate to HTTP status codes.

### Redfish Data Models
`src/models/redfish_schemas.py` contains static methods returning Redfish-compliant dictionaries:
- All responses include `@odata.type`, `@odata.id`, proper Redfish schema versions
- Uses `RedfishModels.get_systems_collection()`, `get_service_root()`, etc.
- Power state mapping: `poweredOn → On`, `poweredOff → Off`, `suspended → Paused`

## Metal3/OpenShift Integration

### Critical Endpoints for Metal3
Metal3 inspection heavily queries:
- `/redfish/v1/UpdateService` - Must return FirmwareInventory, SoftwareInventory
- `/redfish/v1/TaskService/Tasks` - Must persist task history (60+ tasks expected)
- `/redfish/v1/Systems/{id}/Storage` - RAID controller discovery
- `/redfish/v1/Managers/{id}/VirtualMedia` - ISO mounting for deployment

**Pattern**: Metal3 detection in logs shows as "🤖 Metal3/Ironic request detected" when User-Agent contains "python-requests" or "openshift".

### BareMetalHost Workflow
1. OpenShift creates BMH pointing to `http://bastion.example.com:{port}/redfish/v1/Systems/{vm_name}`
2. Metal3 operator performs inspection: queries processors, memory, network, storage
3. Power management: Metal3 sends `POST /Systems/{id}/Actions/ComputerSystem.Reset` with `{"ResetType": "On"}`
4. Boot configuration: `PATCH /Systems/{id}` with `Boot.BootSourceOverrideTarget: "Cd"` for ISO boot — this now calls VMware's boot order API
5. Virtual media: Metal3 mounts ISO via `POST /Managers/{id}/VirtualMedia/CD/Actions/VirtualMedia.InsertMedia` — ISO is downloaded and uploaded to vSphere datastore automatically

**See**: `openshift/README.md` for complete BMH testing guide and troubleshooting.

## Testing & Validation

### Automated Test Suite
Tests live in `tests/test_redfish_server.py` and are run with:
```bash
cd /home/markd/source/fork/redfish-vmware
PYTHONPATH=. .venv/bin/python -m unittest tests.test_redfish_server
```
Test classes:
- `RedfishServerPortTests` - server startup port resolution, datacenter folder refresh interval, stale VM pruning
- `AuthManagerTests` - per-VM credential validation
- `SystemsPatchTests` - Boot PATCH calls VMware, BIOS/SecureBoot return 501
- `SystemsHandlerPayloadTests` - system info shape and sub-resource collection routing
- `VirtualMediaHandlerTests` - ISO path resolution (including `vm_name_` prefix), InsertMedia upload+mount flow, EjectMedia with/without `delete_on_eject`

### Manual Testing Pattern
```bash
# Test connectivity (public endpoint)
curl http://localhost:8443/redfish/v1/

# Test authenticated endpoint
curl -u admin:password http://localhost:8443/redfish/v1/Systems/vm-name

# Test power operation
curl -u admin:password -X POST -H "Content-Type: application/json" \
  -d '{"ResetType": "On"}' \
  http://localhost:8443/redfish/v1/Systems/vm-name/Actions/ComputerSystem.Reset

# Test boot configuration (triggers VMware boot order change)
curl -u admin:password -X PATCH -H "Content-Type: application/json" \
  -d '{"Boot": {"BootSourceOverrideTarget": "Cd", "BootSourceOverrideEnabled": "Once"}}' \
  http://localhost:8443/redfish/v1/Systems/vm-name

# Insert virtual media (downloads ISO from URL and uploads to vSphere)
curl -u admin:password -X POST -H "Content-Type: application/json" \
  -d '{"Image": "http://bastion.example.com/images/rhcos.iso"}' \
  http://localhost:8443/redfish/v1/Managers/vm-name-bmc/VirtualMedia/CD/Actions/VirtualMedia.InsertMedia

# Eject virtual media
curl -u admin:password -X POST \
  http://localhost:8443/redfish/v1/Managers/vm-name-bmc/VirtualMedia/CD/Actions/VirtualMedia.EjectMedia
```

### Common Debugging Commands
```bash
# Service status
sudo systemctl status redfish-vmware-server

# Enable debug logging (persistent)
sudo systemctl edit redfish-vmware-server
# Add: Environment=REDFISH_DEBUG=true
sudo systemctl restart redfish-vmware-server

# View logs with grep filtering
sudo journalctl -u redfish-vmware-server -f | grep "Metal3\|ERROR\|WARNING"

# Check VMware connectivity
python3 -c "from src.vmware_client import VMwareClient; client = VMwareClient('vcenter.host', 'user', 'pass'); print(client.list_vms())"
```

## Code Modification Guidelines

### Adding New Redfish Endpoints
1. Add route handling in `src/handlers/redfish_handler.py` → `_route_get_request()` / `_route_post_request()` / `_route_patch_request()`
2. Create handler method in appropriate specialized handler (systems, managers, etc.)
3. Add data model in `src/models/redfish_schemas.py` if needed
4. Add regression tests in `tests/test_redfish_server.py`
5. Test against Metal3 operator behavior - check OpenShift logs for failures

### Extending VMware Operations
1. Add method to appropriate module in `src/vmware/` (e.g., new power operation → `power_operations.py`)
2. Expose via `VMwareClient` facade in `src/vmware_client.py`
3. Follow pattern: log intent, perform operation, log result, return bool
4. Handle VMware exceptions gracefully - Metal3 retries failed operations

### Task Management Changes
Tasks auto-complete after 60 seconds if not updated. For long-running operations:
1. Create task: `task_id = self.task_manager.create_task(type, name, description)`
2. Update progress: `self.task_manager.update_task(task_id, progress=50, message="In progress")`
3. Complete: `self.task_manager.complete_task(task_id, "Success message")`

### SSL/TLS Configuration
- Production: Uses Let's Encrypt certs from `/etc/letsencrypt/live/<hostname>/`
- Development: Set `"disable_ssl": true` in VM config for HTTP-only
- **Critical**: OpenShift BMH files must use `http://` when `disable_ssl: true`, not `redfish://`

### Keeping This File Up to Date
**This file must be updated whenever the following change**:
- New config keys added to `config/config.json` or `config/config.json.example`
- New Redfish endpoints added or existing ones materially changed
- New VMware operations added to `src/vmware/` or `vmware_client.py`
- Authentication behaviour changes
- New test classes or significant new test coverage added
- Background threads or lifecycle behaviour added to `redfish_server.py`

## File Organization Quick Reference
```
src/
  redfish_server.py          # Entry point, config load, folder refresh loop, startup
  vmware_client.py           # Unified VMware API facade
  handlers/
    redfish_handler.py       # Top-level router + refresh_vm_configs()
    systems_handler.py       # ComputerSystem, sub-resources, boot/BIOS/SecureBoot PATCH
    managers_handler.py      # Managers, VirtualMedia insert/eject/upload, delete_on_eject
    chassis_handler.py       # Chassis representation
    update_service_handler.py # Firmware/software inventory
    http_handler.py          # Raw HTTP dispatch
  vmware/
    connection.py            # vSphere connection and session management
    vm_operations.py         # VM discovery and info
    power_operations.py      # Power on/off/reset/shutdown
    media_operations.py      # ISO upload, mount, unmount, boot order, datastore delete
  auth/
    manager.py               # Basic auth + session tokens; validates per-VM credentials
  tasks/
    manager.py               # Async task tracking for Metal3
  models/
    redfish_schemas.py       # Redfish-compliant response generators
  utils/
    logging_config.py        # Logging setup and helpers

config/
  config.json                # VM definitions, vCenter credentials, feature flags
  config.json.example        # Reference configuration with all supported keys
  redfish-vmware-server.service  # SystemD unit file

tests/
  test_redfish_server.py     # Automated regression suite (24 tests)

openshift/                   # BareMetalHost YAML examples and testing guide
```

**Key Files to Understand**:
- `src/handlers/redfish_handler.py` - Main request router and VM config refresh
- `src/handlers/systems_handler.py` - Core VM operations and ComputerSystem payload
- `src/handlers/managers_handler.py` - Virtual media lifecycle including ISO upload
- `src/vmware/media_operations.py` - vSphere ISO upload, mount, delete
- `src/tasks/manager.py` - Task lifecycle management
- `openshift/README.md` - Metal3 integration testing procedures


## Architecture Deep Dive

### Single-Server Design Pattern
- **One Redfish server instance for all VMs** - A single HTTP(S) listener serves all Redfish endpoints.
- The server listens on a top-level `redfish_port` configured in `config/config.json` (or via `REDFISH_PORT` environment variable in the service unit).
- VM selection is done using the `{ID}` portion of the Redfish URI: `/redfish/v1/Systems/{ID}`.
- This simplifies deployment and avoids per-VM port management; clients address different VMs by changing the `{ID}` path segment.

**Example**: The server listens on port 8443; `skinner-master-1` is accessible at `http://bastion.chiaret.to:8443/redfish/v1/Systems/skinner-master-1`

### Handler-Based Modular Architecture
Located in `src/handlers/`, each handler is specialized:
- `systems_handler.py` - VM power, boot, BIOS, storage, SecureBoot operations
- `managers_handler.py` - BMC management, virtual media operations
- `chassis_handler.py` - Physical chassis representation
- `update_service_handler.py` - Firmware updates and software inventory (Metal3 inspection)
- `http_handler.py` - Base HTTP request routing with authentication

**Pattern**: Handlers receive `(request_handler, path)` and route to internal methods like `_handle_system_action()`, `_handle_bios_patch()`.

### VMware Operations Layer
Modularized VMware API interactions in `src/vmware/`:
- `connection.py` - Manages single vSphere connection with SSL verification toggle
- `vm_operations.py` - VM discovery, info retrieval, state management
- `power_operations.py` - All power operations (on/off/reset/graceful)
- `media_operations.py` - ISO mounting, boot order configuration

**Key Pattern**: `VMwareClient` in `vmware_client.py` aggregates these modules and exposes a unified interface. Operations return boolean success/failure.

### Task Management System
Metal3 requires asynchronous operation tracking. `src/tasks/manager.py` provides:
- Dynamic task creation with UUID generation
- Automatic task cleanup (completed tasks >1 hour old removed)
- Initial tasks created on startup for Metal3 compatibility
- Progress tracking (0-100%) with state machine: `New → Running → Completed/Exception`

**Metal3 Integration**: Update operations and RAID configuration return task URIs like `/redfish/v1/TaskService/Tasks/{task_id}`

## Configuration & Deployment

### Config Structure (`config/config.json`)
```json
{
  "vmware": { /* global vCenter connection */ },
  "vms": [
    {
      "name": "vm-name",              // VM name in vCenter
      "vcenter_host": "...",
      "vcenter_user": "...",
      "vcenter_password": "...",
      "redfish_user": "admin",        // Fixed: admin/password
      "redfish_password": "password",
      "discovered": false,            // Auto-populated if from datacenter_folders
      "discovered_from": "..."        // Path if auto-discovered
    }
  ],
  "datacenter_folders": [
    {
      "datacenter": "Datacenter1",    // vCenter datacenter name
      "folder_path": "vm/prod/kubernetes"  // Folder path for VM discovery
    }
  ],
  "redfish_port": 8443,               // Top-level port for single server
  "disable_ssl": true,                // Top-level SSL toggle
  "ssl": {  /* Optional: Let's Encrypt cert paths */ }
}
```

### VM Auto-Discovery from Datacenter Folders
**NEW FEATURE**: Automatically discover and manage VMs from vCenter datacenter folders.

**Discovery Flow**:
1. Configuration loaded from `config/config.json`
2. `_validate_config()` checks for `vms` or `datacenter_folders` (or both)
3. `_discover_vms_from_folders()` called after validation:
   - Iterates through each `datacenter_folders` entry
   - Creates temporary VMware connection using global `vmware` credentials
   - Calls `vm_operations.list_vms_in_folder(datacenter, folder_path)`
   - Recursively discovers VMs in folder hierarchy
   - Skips VMs already in manual `vms` list (name match)
   - Adds discovered VMs with `"discovered": true` and `"discovered_from"` metadata
4. Final config has merged list of manual + discovered VMs

**Implementation Details**:
- `VMOperations.list_vms_in_folder()` - Finds folder by datacenter + path, recursively collects VMs
- `VMOperations.get_folder_by_path()` - Navigates folder hierarchy (e.g., `vm/prod/k8s`)
- `VMOperations._collect_vms_recursive()` - Traverses folder tree, adds vim.VirtualMachine objects
- `VMOperations.list_datacenters()` - Lists available datacenters for validation
- Discovered VMs get default credentials: `redfish_user=admin`, `redfish_password=password`

**Folder Path Format**:
- `vm` - All VMs in datacenter root folder
- `vm/prod` - VMs in `prod` subfolder  
- `vm/prod/kubernetes` - Nested folder search (recursive)
- Path is case-sensitive and must match vCenter folder names exactly

**Error Handling**:
- Invalid datacenter/folder logs warning and skips that entry
- Missing VMware credentials falls back to manual VMs only
- No exception thrown - discovery failures are non-blocking
- Temporary connection properly disconnected after each discovery

### SystemD Service Pattern
Production deployment uses `config/redfish-vmware-server.service`:
- Runs as dedicated user (created by `setup.sh`)
- Auto-restart on failure
- Logs to journald: `sudo journalctl -u redfish-vmware-server -f`
- Debug control via environment: `Environment=REDFISH_DEBUG=true` in service override

**Critical**: Use `setup.sh` for installation - it configures Python env, systemd, firewall, and validates VMware connectivity. Ensure `config/config.json` contains a top-level `redfish_port` (or set `REDFISH_PORT` in the systemd unit) so the single Redfish server listens on the expected port.

## Development Conventions

### Logging Strategy
**Production vs Debug**: Controlled by `REDFISH_DEBUG` environment variable (default: false)
- Production: INFO level, minimal format, no request details
- Debug: DEBUG level, includes file/line numbers, full HTTP request logging
- All loggers use emoji prefixes: 🚀 startup, ✅ success, ❌ errors, 🔍 Metal3 detection

**Pattern**: Use `logger.info()` for user-visible events, `logger.debug()` for request details, `logger.warning()` for SSL/auth issues.

### Authentication Model
Fixed credentials: `admin:password` (defined in `src/auth/manager.py`)
- Public endpoints: `/redfish/v1/`, `/redfish/v1/Systems` (no auth)
- All other endpoints require HTTP Basic Auth
- Session tokens supported but Basic Auth is primary

### Error Handling Pattern
Handlers use consistent response methods:
```python
self._send_json_response(request_handler, 200, data)
self._send_error_response(request_handler, 404, "System not found")
```
VMware operations return `True/False` - handlers translate to HTTP status codes.

### Redfish Data Models
`src/models/redfish_schemas.py` contains static methods returning Redfish-compliant dictionaries:
- All responses include `@odata.type`, `@odata.id`, proper Redfish schema versions
- Uses `RedfishModels.get_systems_collection()`, `get_service_root()`, etc.
- Power state mapping: `poweredOn → On`, `poweredOff → Off`, `suspended → Paused`

## Metal3/OpenShift Integration

### Critical Endpoints for Metal3
Metal3 inspection heavily queries:
- `/redfish/v1/UpdateService` - Must return FirmwareInventory, SoftwareInventory
- `/redfish/v1/TaskService/Tasks` - Must persist task history (60+ tasks expected)
- `/redfish/v1/Systems/{id}/Storage` - RAID controller discovery
- `/redfish/v1/Managers/{id}/VirtualMedia` - ISO mounting for deployment

**Pattern**: Metal3 detection in logs shows as "🤖 Metal3/Ironic request detected" when User-Agent contains "python-requests" or "openshift".

### BareMetalHost Workflow
1. OpenShift creates BMH pointing to `http://bastion.chiaret.to:{port}/redfish/v1/Systems/{vm_name}`
2. Metal3 operator performs inspection: queries processors, memory, network, storage
3. Power management: Metal3 sends `POST /Systems/{id}/Actions/ComputerSystem.Reset` with `{"ResetType": "On"}`
4. Boot configuration: `PATCH /Systems/{id}` with `Boot.BootSourceOverrideTarget: "Cd"` for ISO boot
5. Virtual media: Metal3 mounts ISO via `POST /Managers/{id}/VirtualMedia/Cd/Actions/VirtualMedia.InsertMedia`

**See**: `openshift/README.md` for complete BMH testing guide and troubleshooting.

## Testing & Validation

### Manual Testing Pattern
```bash
# Test connectivity (public endpoint)
curl http://localhost:8443/redfish/v1/

# Test authenticated endpoint
curl -u admin:password http://localhost:8443/redfish/v1/Systems/vm-name

# Test power operation
curl -u admin:password -X POST -H "Content-Type: application/json" \
  -d '{"ResetType": "On"}' \
  http://localhost:8443/redfish/v1/Systems/vm-name/Actions/ComputerSystem.Reset
```

**No automated test suite exists** - testing is manual or via Metal3 integration.

### Common Debugging Commands
```bash
# Service status
sudo systemctl status redfish-vmware-server

# Enable debug logging (persistent)
sudo systemctl edit redfish-vmware-server
# Add: Environment=REDFISH_DEBUG=true
sudo systemctl restart redfish-vmware-server

# View logs with grep filtering
sudo journalctl -u redfish-vmware-server -f | grep "Metal3\|ERROR\|WARNING"

# Check VMware connectivity
python3 -c "from src.vmware_client import VMwareClient; client = VMwareClient('vcenter.host', 'user', 'pass'); print(client.list_vms())"
```

## Code Modification Guidelines

### Adding New Redfish Endpoints
1. Add route handling in `src/handlers/redfish_handler.py` → `_handle_request()` method
2. Create handler method in appropriate specialized handler (systems, managers, etc.)
3. Add data model in `src/models/redfish_schemas.py` if needed
4. Test against Metal3 operator behavior - check OpenShift logs for failures

### Extending VMware Operations
1. Add method to appropriate module in `src/vmware/` (e.g., new power operation → `power_operations.py`)
2. Expose via `VMwareClient` facade in `src/vmware_client.py`
3. Follow pattern: log intent, perform operation, log result, return bool
4. Handle VMware exceptions gracefully - Metal3 retries failed operations

### Task Management Changes
Tasks auto-complete after 60 seconds if not updated. For long-running operations:
1. Create task: `task_id = self.task_manager.create_task(type, name, description)`
2. Update progress: `self.task_manager.update_task(task_id, progress=50, message="In progress")`
3. Complete: `self.task_manager.complete_task(task_id, "Success message")`

### SSL/TLS Configuration
- Production: Uses Let's Encrypt certs from `/etc/letsencrypt/live/bastion.chiaret.to/`
- Development: Set `"disable_ssl": true` in VM config for HTTP-only
- **Critical**: OpenShift BMH files must use `http://` when `disable_ssl: true`, not `redfish://`

## File Organization Quick Reference
```
src/
  redfish_server.py          # Entry point, multi-server startup
  vmware_client.py           # Unified VMware API facade
  handlers/                  # HTTP request routing and Redfish logic
  vmware/                    # VMware vSphere API operations
  auth/                      # Authentication and session management
  tasks/                     # Async task tracking for Metal3
  models/                    # Redfish schema response generators
  utils/                     # Logging configuration

config/
  config.json                # VM definitions and vCenter credentials
  redfish-vmware-server.service  # SystemD unit file

openshift/                   # BareMetalHost YAML examples and testing guide
```

**Key Files to Understand**:
- `src/handlers/redfish_handler.py` - Main request router (~600 lines)
- `src/handlers/systems_handler.py` - Core VM operations (~420 lines)
- `src/tasks/manager.py` - Task lifecycle management
- `openshift/README.md` - Metal3 integration testing procedures
