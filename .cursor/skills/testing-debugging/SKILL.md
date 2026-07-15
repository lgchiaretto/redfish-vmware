---
name: testing-debugging
description: Complete guide for testing and debugging the Redfish-VMware bridge. Use when the user wants to test endpoints, debug issues, troubleshoot Metal3 integration, check logs, or diagnose problems.
---

# Testing and Debugging

## Automated Test Suite

Tests live in `tests/test_redfish_server.py`:

```bash
PYTHONPATH=. python3 -m unittest tests.test_redfish_server
```

Test classes:
- `RedfishServerPortTests` - server startup port resolution, datacenter folder refresh interval, stale VM pruning
- `AuthManagerTests` - per-VM credential validation
- `SystemsPatchTests` - Boot PATCH calls VMware, BIOS/SecureBoot return 501
- `SystemsHandlerPayloadTests` - system info shape and sub-resource collection routing
- `VirtualMediaHandlerTests` - ISO path resolution (`vm_name_` prefix), InsertMedia upload+mount, EjectMedia with/without `delete_on_eject`
- `ManagersPostRoutingTests` - InsertMedia POST routes correctly (not 404)
- `SSLCertificateGenerationTests` - certificate generation, permissions, directory creation, SSL context

Add regression tests when adding new endpoints or changing behaviour.

## Manual Testing with curl

### Basic Connectivity

```bash
# Service root (public, no auth)
curl -s http://localhost:8443/redfish/v1/ | python3 -m json.tool

# Health check
curl -s http://localhost:8443/redfish/v1/health | python3 -m json.tool
```

### Authenticated Endpoints

All VMs share port 8443 (or configured `redfish_port`); select VM via path:

```bash
# List all systems
curl -s -u admin:password http://localhost:8443/redfish/v1/Systems | python3 -m json.tool

# Get specific system info
curl -s -u admin:password http://localhost:8443/redfish/v1/Systems/VM_NAME | python3 -m json.tool

# Sub-resources (Metal3 inspection)
curl -s -u admin:password http://localhost:8443/redfish/v1/Systems/VM_NAME/Processors | python3 -m json.tool
curl -s -u admin:password http://localhost:8443/redfish/v1/Systems/VM_NAME/Memory | python3 -m json.tool
curl -s -u admin:password http://localhost:8443/redfish/v1/Systems/VM_NAME/Storage | python3 -m json.tool

# UpdateService (critical for Metal3 inspection)
curl -s -u admin:password http://localhost:8443/redfish/v1/UpdateService | python3 -m json.tool

# Tasks
curl -s -u admin:password http://localhost:8443/redfish/v1/TaskService/Tasks | python3 -m json.tool
```

### Power Operations

```bash
# Power On
curl -s -u admin:password -X POST -H "Content-Type: application/json" \
  -d '{"ResetType": "On"}' \
  http://localhost:8443/redfish/v1/Systems/VM_NAME/Actions/ComputerSystem.Reset

# Power Off (hard)
curl -s -u admin:password -X POST -H "Content-Type: application/json" \
  -d '{"ResetType": "ForceOff"}' \
  http://localhost:8443/redfish/v1/Systems/VM_NAME/Actions/ComputerSystem.Reset
```

### Boot Configuration

```bash
# Set boot from CD (ISO) — triggers VMware boot order change
curl -s -u admin:password -X PATCH -H "Content-Type: application/json" \
  -d '{"Boot": {"BootSourceOverrideTarget": "Cd", "BootSourceOverrideEnabled": "Once"}}' \
  http://localhost:8443/redfish/v1/Systems/VM_NAME
```

### Virtual Media (ISO Mount)

```bash
# Insert media (downloads URL, uploads to vSphere datastore, mounts ISO)
curl -s -u admin:password -X POST -H "Content-Type: application/json" \
  -d '{"Image": "http://server/images/rhcos.iso", "WriteProtected": true}' \
  http://localhost:8443/redfish/v1/Managers/VM_NAME-bmc/VirtualMedia/CD/Actions/VirtualMedia.InsertMedia

# Eject media (force eject with runtime question handling)
curl -s -u admin:password -X POST \
  http://localhost:8443/redfish/v1/Managers/VM_NAME-bmc/VirtualMedia/CD/Actions/VirtualMedia.EjectMedia
```

## Debug Mode

### Enable Debug Logging

```bash
# One-time run with debug
REDFISH_DEBUG=true python3 src/redfish_server.py --config config/config.json

# Persistent via systemd override
sudo systemctl edit redfish-vmware-server
# Add under [Service]:
#   Environment=REDFISH_DEBUG=true
sudo systemctl restart redfish-vmware-server

# Additional debug flags
REDFISH_PERF_DEBUG=true     # Performance metrics
REDFISH_VMWARE_DEBUG=true   # VMware operation details
```

### Reading Logs

```bash
# Follow live logs
sudo journalctl -u redfish-vmware-server -f

# Filter for errors
sudo journalctl -u redfish-vmware-server --since "5 minutes ago" | grep -E "ERROR|WARNING|❌"

# Filter for Metal3 requests (User-Agent contains python-requests or openshift)
sudo journalctl -u redfish-vmware-server -f | grep "Metal3\|Ironic\|🤖"

# Filter for folder discovery refresh
sudo journalctl -u redfish-vmware-server -f | grep "FolderRefresh\|discovered"
```

## Common Issues and Solutions

### 1. VMware Connection Failed

**Symptom**: `❌ Failed to initialize VMware client`

**Check**:
```bash
python3 -c "
from src.vmware_client import VMwareClient
client = VMwareClient('vcenter.host', 'user', 'pass')
print(client.list_vms())
"
```

### 2. Metal3 Inspection Failures

**Symptom**: BMH stuck in `inspecting` state

**Check these endpoints return 200**:
```bash
curl -s -o /dev/null -w "%{http_code}" -u admin:password http://HOST:8443/redfish/v1/UpdateService
curl -s -o /dev/null -w "%{http_code}" -u admin:password http://HOST:8443/redfish/v1/Systems/VM_NAME/Storage
curl -s -o /dev/null -w "%{http_code}" -u admin:password http://HOST:8443/redfish/v1/TaskService/Tasks
```

**OpenShift side**:
```bash
oc get bmh -n openshift-machine-api
oc describe bmh VM_NAME -n openshift-machine-api
oc logs -n openshift-machine-api -l app=metal3 -c ironic --tail=50
```

### 3. Port Conflicts

**Symptom**: `Address already in use` on `redfish_port`

```bash
sudo ss -tlnp | grep 8443
sudo kill $(sudo lsof -t -i:8443)
```

### 4. SSL Issues

Use `"disable_ssl": true` in config for development. BMH files must use `http://` not `redfish://`.

### 5. VM Not Found After Discovery

Check `datacenter_folders` path is correct (case-sensitive). Review logs for discovery warnings. Verify VM name matches vCenter exactly.

## Comprehensive Endpoint Test Script

```bash
#!/bin/bash
HOST="localhost"
PORT="8443"
VM="vm-name"
AUTH="admin:password"
BASE="http://${HOST}:${PORT}/redfish/v1"

for endpoint in \
  "/" "/Systems" "/Systems/${VM}" "/Systems/${VM}/Bios" \
  "/Systems/${VM}/Storage" "/Systems/${VM}/Processors" "/Systems/${VM}/Memory" \
  "/Managers" "/Managers/${VM}-bmc/VirtualMedia" \
  "/Chassis" "/UpdateService" "/TaskService/Tasks"
do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" -u ${AUTH} "${BASE}${endpoint}")
  echo "  ${STATUS}  ${endpoint}"
done
```

## OpenShift/Metal3 Integration Testing

See `openshift/README.md` for the full BMH testing guide.

BMH address format: `http://host:8443/redfish/v1/Systems/{vm_name}`
