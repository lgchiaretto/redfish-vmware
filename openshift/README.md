# OpenShift BareMetalHost Testing Guide

This guide documents how to test the Redfish server integration with OpenShift BareMetalHost.

## Prerequisites

1. ✅ Redfish server installed and running
2. ✅ Test VMs configured (all 5 VMs: 3 masters + 2 workers)
3. ✅ Network connectivity between OpenShift and Redfish server
4. 🔄 OpenShift cluster with Metal3 operator installed

## ⚠️ IMPORTANT: HTTP Configuration 

**CRITICAL**: To avoid SSL errors, all BMH files have been updated to use `http://` instead of `redfish://`:

```yaml
bmc:
  address: 'http://bastion.chiaret.to:8441/redfish/v1/Systems/skinner-master-1'
  credentialsName: skinner-master-1-bmc-secret
  disableCertificateVerification: true
```

**Fixed Error**: 
- ❌ Before: SSL: WRONG_VERSION_NUMBER - HTTPS on HTTP port
- ✅ Now: Pure HTTP working perfectly

## Test Structure

### 1. Basic Connectivity Tests

```bash
# Test Redfish endpoints for all VMs
curl http://bastion.chiaret.to:8440/redfish/v1/
curl -u admin:password http://bastion.chiaret.to:8440/redfish/v1/Systems/skinner-master-0
curl -u admin:password http://bastion.chiaret.to:8441/redfish/v1/Systems/skinner-master-1  
curl -u admin:password http://bastion.chiaret.to:8442/redfish/v1/Systems/skinner-master-2
curl -u admin:password http://bastion.chiaret.to:8443/redfish/v1/Systems/skinner-worker-1
curl -u admin:password http://bastion.chiaret.to:8444/redfish/v1/Systems/skinner-worker-2
```

### 2. Power Management Tests

```bash
# Run automated test script
./tests/test_power_management.sh
```

### 3. BareMetalHost Application

```bash
# Apply ALL BMH configurations (masters + workers)
oc apply -f openshift/skinner-master-0-bmh.yaml
oc apply -f openshift/skinner-master-1-bmh.yaml
oc apply -f openshift/skinner-master-2-bmh.yaml  
oc apply -f openshift/skinner-worker-1-bmh.yaml
oc apply -f openshift/skinner-worker-2-bmh.yaml
```

## BareMetalHost Configurations

### Authentication Credentials
- **Username**: `admin`
- **Password**: `password`
- **Type**: Basic Authentication

### Port Mapping
- **skinner-master-0**: http://bastion.chiaret.to:8440
- **skinner-master-1**: http://bastion.chiaret.to:8441  
- **skinner-master-2**: http://bastion.chiaret.to:8442
- **skinner-worker-1**: http://bastion.chiaret.to:8443
- **skinner-worker-2**: http://bastion.chiaret.to:8444  
- **BMC Address**: `redfish://bastion.chiaret.to:8444/redfish/v1/Systems/skinner-worker-2`
- **Port**: 8444
- **MAC Address**: `00:50:56:84:8c:23`

## Expected BareMetalHost States

### Normal Provisioning Sequence

1. **registering** - BMH is being registered
2. **inspecting** - Hardware being inspected  
3. **available** - Host available for provisioning
4. **provisioning** - Host being provisioned
5. **provisioned** - Host successfully provisioned

### Monitoring Commands

```bash
# Check BMH status
oc get baremetalhosts -n openshift-machine-api

# View details of specific BMH
oc describe baremetalhost skinner-worker-1 -n openshift-machine-api

# Monitor metal3 operator logs
oc logs -f deployment/metal3-baremetal-operator -n openshift-machine-api

# Check related events
oc get events -n openshift-machine-api --sort-by='.lastTimestamp'
```

## Troubleshooting

### 1. BMH stuck in "registering" state

```bash
# Check network connectivity
curl -v -u admin:password http://bastion.chiaret.to:8443/redfish/v1/Systems/skinner-worker-1

# Check operator logs
oc logs deployment/metal3-baremetal-operator -n openshift-machine-api
```

### 2. BMH fails inspection

```bash
# Check if VMs are powered on
curl -u admin:password http://bastion.chiaret.to:8443/redfish/v1/Systems/skinner-worker-1 | jq '.PowerState'

# Check MAC address configuration
oc get bmh skinner-worker-1 -o yaml | grep bootMACAddress
```

### 3. Authentication issues

```bash
# Check if secret was created correctly
oc get secret skinner-worker-1-bmc-secret -n openshift-machine-api -o yaml
```

## Success Validation

The test will be considered successful when:

1. ✅ BareMetalHosts exit "registering" state 
2. ✅ Successfully complete inspection ("inspecting" → "available" state)
3. ✅ Can be provisioned ("provisioning" → "provisioned" state)
4. ✅ OpenShift can control VM power management via Redfish

## Useful Commands

### Clean and recreate BMHs
```bash
# Delete existing BMHs
oc delete bmh skinner-worker-1 skinner-worker-2 -n openshift-machine-api

# Recreate
oc apply -f openshift/skinner-worker-1-bmh.yaml
oc apply -f openshift/skinner-worker-2-bmh.yaml
```

### Force re-inspection
```bash
# Add annotation to force re-inspection
oc annotate bmh skinner-worker-1 -n openshift-machine-api reboot.metal3.io/capz-remediation-
```

### Debug Redfish server
```bash
# Enable debug mode
export REDFISH_DEBUG=true
sudo systemctl restart redfish-vmware-server

# View detailed logs
sudo journalctl -u redfish-vmware-server -f
```

## Next Steps

After successfully completing these tests:

1. Document all results
2. Create templates for other OpenShift clusters
3. Implement automated monitoring
4. Develop maintenance scripts
