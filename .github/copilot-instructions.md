# Redfish VMware Bridge - AI Agent Instructions

## Project Overview
This is a **Redfish-to-VMware vSphere bridge** that translates standard Redfish REST API calls into VMware vSphere operations. Built specifically for **OpenShift Metal3/Ironic** integration to manage VMware VMs as if they were bare metal hosts.

**Critical Context**: This is an AI-generated codebase (v1.0) designed for production Metal3 deployments. The architecture prioritizes Metal3 compatibility over generic Redfish compliance.

## Architecture Deep Dive

### Multi-Server Design Pattern
- **One Redfish server instance per VM** - Each VM gets its own dedicated HTTPS/HTTP endpoint
- Server instances run on different ports (8440-8444+) defined in `config/config.json`
- All servers share a single `RedfishHandler` instance to coordinate operations
- This design allows Metal3 to treat each VM as an independent bare metal host

**Example**: `skinner-master-1` runs on port 8441, accessible at `http://bastion.chiaret.to:8441/redfish/v1/Systems/skinner-master-1`

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
      "redfish_port": 8443,           // Unique port per VM
      "redfish_user": "admin",        // Fixed: admin/password
      "redfish_password": "password",
      "disable_ssl": true             // HTTP vs HTTPS toggle
    }
  ],
  "ssl": {  /* Optional: Let's Encrypt cert paths */ }
}
```

### SystemD Service Pattern
Production deployment uses `config/redfish-vmware-server.service`:
- Runs as dedicated user (created by `setup.sh`)
- Auto-restart on failure
- Logs to journald: `sudo journalctl -u redfish-vmware-server -f`
- Debug control via environment: `Environment=REDFISH_DEBUG=true` in service override

**Critical**: Use `setup.sh` for installation - it configures Python env, systemd, firewall, and validates VMware connectivity.

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
