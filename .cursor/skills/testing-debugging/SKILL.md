---
name: testing-debugging
description: Complete guide for testing and debugging the Redfish-VMware bridge. Use when the user wants to test endpoints, debug issues, troubleshoot Metal3 integration, check logs, or diagnose problems.
---

# Testing and Debugging

## Manual Testing with curl

### Basic Connectivity

```bash
# Service root (public, no auth)
curl -s http://localhost:8443/redfish/v1/ | python3 -m json.tool

# Health check
curl -s http://localhost:8443/redfish/v1/health | python3 -m json.tool
```

### Authenticated Endpoints

```bash
# List all systems
curl -s -u admin:password http://localhost:8443/redfish/v1/Systems | python3 -m json.tool

# Get specific system info
curl -s -u admin:password http://localhost:8443/redfish/v1/Systems/VM_NAME | python3 -m json.tool

# Managers
curl -s -u admin:password http://localhost:8443/redfish/v1/Managers | python3 -m json.tool

# Chassis
curl -s -u admin:password http://localhost:8443/redfish/v1/Chassis | python3 -m json.tool

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

# Graceful Shutdown
curl -s -u admin:password -X POST -H "Content-Type: application/json" \
  -d '{"ResetType": "GracefulShutdown"}' \
  http://localhost:8443/redfish/v1/Systems/VM_NAME/Actions/ComputerSystem.Reset

# Force Restart
curl -s -u admin:password -X POST -H "Content-Type: application/json" \
  -d '{"ResetType": "ForceRestart"}' \
  http://localhost:8443/redfish/v1/Systems/VM_NAME/Actions/ComputerSystem.Reset
```

### Boot Configuration

```bash
# Set boot from CD (ISO)
curl -s -u admin:password -X PATCH -H "Content-Type: application/json" \
  -d '{"Boot": {"BootSourceOverrideTarget": "Cd", "BootSourceOverrideEnabled": "Once"}}' \
  http://localhost:8443/redfish/v1/Systems/VM_NAME

# Set boot from PXE
curl -s -u admin:password -X PATCH -H "Content-Type: application/json" \
  -d '{"Boot": {"BootSourceOverrideTarget": "Pxe", "BootSourceOverrideEnabled": "Once"}}' \
  http://localhost:8443/redfish/v1/Systems/VM_NAME
```

### Virtual Media (ISO Mount)

```bash
# Mount ISO
curl -s -u admin:password -X POST -H "Content-Type: application/json" \
  -d '{"Image": "http://server/image.iso", "Inserted": true}' \
  http://localhost:8443/redfish/v1/Managers/VM_NAME-bmc/VirtualMedia/Cd/Actions/VirtualMedia.InsertMedia

# Unmount ISO
curl -s -u admin:password -X POST \
  http://localhost:8443/redfish/v1/Managers/VM_NAME-bmc/VirtualMedia/Cd/Actions/VirtualMedia.EjectMedia
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

# Filter for Metal3 requests
sudo journalctl -u redfish-vmware-server -f | grep "Metal3\|Ironic\|🤖"

# Filter for specific VM
sudo journalctl -u redfish-vmware-server -f | grep "vm-name"

# Last 100 lines
sudo journalctl -u redfish-vmware-server -n 100
```

## Common Issues and Solutions

### 1. VMware Connection Failed

**Symptom**: `❌ Failed to initialize VMware client`

**Check**:
```bash
python3 -c "
from pyVim.connect import SmartConnect
import ssl
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
si = SmartConnect(host='VCENTER_HOST', user='USER', pwd='PASS', sslContext=ctx)
print('Connected:', si.content.about.fullName)
"
```

**Common causes**: wrong credentials, network issue, vCenter down, DNS resolution failure.

### 2. Metal3 Inspection Failures

**Symptom**: BMH stuck in `inspecting` state

**Check these endpoints return 200**:
```bash
curl -s -o /dev/null -w "%{http_code}" -u admin:password http://HOST:PORT/redfish/v1/UpdateService
curl -s -o /dev/null -w "%{http_code}" -u admin:password http://HOST:PORT/redfish/v1/Systems/VM_NAME/Storage
curl -s -o /dev/null -w "%{http_code}" -u admin:password http://HOST:PORT/redfish/v1/TaskService/Tasks
```

**OpenShift side**:
```bash
oc get bmh -n openshift-machine-api
oc describe bmh VM_NAME -n openshift-machine-api
oc logs -n openshift-machine-api -l app=metal3 -c ironic --tail=50
```

### 3. Port Conflicts

**Symptom**: `Address already in use`

```bash
# Check what's using the port
sudo ss -tlnp | grep 8443
# Kill if needed
sudo kill $(sudo lsof -t -i:8443)
```

### 4. SSL Issues

**Symptom**: SSL handshake errors or certificate warnings

**Solution**: Use `"disable_ssl": true` in `config.json` for development. For BMH files, use `http://` instead of `redfish://`.

### 5. Service Won't Start

```bash
sudo systemctl status redfish-vmware-server
sudo journalctl -u redfish-vmware-server -n 50 --no-pager

# Check config is valid JSON
python3 -c "import json; json.load(open('config/config.json'))"

# Check Python path
python3 -c "import sys; print(sys.path)"
```

## Comprehensive Endpoint Test Script

```bash
#!/bin/bash
HOST="localhost"
PORT="8443"
VM="vm-name"
AUTH="admin:password"
BASE="http://${HOST}:${PORT}/redfish/v1"

echo "=== Testing Redfish Endpoints ==="

for endpoint in \
  "/" \
  "/Systems" \
  "/Systems/${VM}" \
  "/Systems/${VM}/Bios" \
  "/Systems/${VM}/Storage" \
  "/Systems/${VM}/SecureBoot" \
  "/Managers" \
  "/Managers/${VM}-bmc" \
  "/Managers/${VM}-bmc/VirtualMedia" \
  "/Chassis" \
  "/Chassis/${VM}-chassis" \
  "/UpdateService" \
  "/UpdateService/FirmwareInventory" \
  "/UpdateService/SoftwareInventory" \
  "/TaskService/Tasks" \
  "/SessionService"
do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" -u ${AUTH} "${BASE}${endpoint}")
  if [ "$STATUS" == "200" ]; then
    echo "  OK  ${endpoint}"
  else
    echo "  FAIL ${endpoint} (HTTP ${STATUS})"
  fi
done
```

## OpenShift/Metal3 Integration Testing

See `openshift/README.md` for the full BMH testing guide, including:
- BareMetalHost YAML examples
- Port mapping per VM
- BMH state machine flow
- Troubleshooting stuck inspections
