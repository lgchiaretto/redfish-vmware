# OpenShift Bare Metal Dynamic Node Addition Guide

## Overview
This guide provides a complete solution for adding new bare metal nodes to your OpenShift cluster in a lab environment after installation.

## Current Status
- ✅ IPMI Bridge: Working with 4 nodes (skinner-master-0/1/2, skinner-worker-1)
- ✅ Metal3/Ironic: Running and operational
- ⚠️ **Issue**: skinner-worker-1 stuck in "inspecting" state due to missing PXE infrastructure

## Root Cause Analysis
The node inspection fails because:
1. **No PXE/DHCP Server**: VMs cannot network boot for hardware inspection
2. **Missing TFTP Server**: No boot images available for Ironic Python Agent (IPA)
3. **VM Network Configuration**: VMs not configured for PXE boot access

## Complete Solution

### 1. PXE Infrastructure Setup
Run the automated setup script:
```bash
sudo chmod +x scripts/setup-pxe-infrastructure.sh
sudo ./scripts/setup-pxe-infrastructure.sh
```

This script will:
- Install dnsmasq (DHCP/TFTP server)
- Configure Apache HTTP server
- Download Ironic Python Agent images
- Create network bridge for PXE
- Configure firewall rules

### 2. VMware Network Configuration
Configure your VMs to access the PXE network:

#### Option A: Add Second Network Interface
```bash
# Add a second network interface to skinner-worker-1
# Connected to the same network as OpenShift cluster (192.168.110.x)
# Set boot order: Network -> Hard Disk
```

#### Option B: Temporary Network Switch
```bash
# Temporarily connect VM to PXE network during inspection
# Switch back to production network after inspection completes
```

### 3. Update BareMetalHost Configuration
Ensure the BareMetalHost can access the boot image:

```yaml
apiVersion: metal3.io/v1alpha1
kind: BareMetalHost
metadata:
  name: skinner-worker-1
  namespace: openshift-machine-api
spec:
  bmc:
    address: ipmi://192.168.1.100:626
    credentialsName: skinner-worker-1-bmc-secret
  bootMACAddress: "00:50:56:XX:XX:XX"  # VM's PXE network MAC
  online: true
```

### 4. Monitor Inspection Progress

Check the inspection status:
```bash
# Monitor BareMetalHost status
oc get baremetalhosts -n openshift-machine-api -w

# Check Metal3 operator logs
oc logs -n openshift-machine-api deployment/metal3-baremetal-operator -f

# Verify DHCP leases
sudo cat /var/lib/dhcp/dhcpd.leases

# Check TFTP access
curl http://192.168.110.71/images/
```

## Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   OpenShift     │    │   PXE Server     │    │   VMware        │
│   Metal3/Ironic │◄──►│   DHCP/TFTP      │◄──►│   VMs           │
│                 │    │   HTTP           │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌──────────────────┐            │
         └──────────────►│   IPMI Bridge    │◄───────────┘
                        │   4 BMC Instances│
                        └──────────────────┘
```

## Network Flow for Node Addition

1. **Create BareMetalHost**: Define new node in OpenShift
2. **Metal3 Triggers Inspection**: Ironic initiates hardware discovery
3. **IPMI Power Control**: Bridge powers on VM via VMware API
4. **PXE Boot**: VM boots from network using DHCP/TFTP
5. **IPA Download**: Ironic Python Agent loads and runs inspection
6. **Hardware Discovery**: IPA reports hardware details to Ironic
7. **Ready State**: Node becomes available for provisioning

## Troubleshooting Common Issues

### Issue: VM Not Getting DHCP
```bash
# Check dnsmasq status
sudo systemctl status dnsmasq

# Verify DHCP configuration
sudo dnsmasq --test

# Monitor DHCP requests
sudo journalctl -f -u dnsmasq
```

### Issue: TFTP Boot Fails
```bash
# Test TFTP access
tftp 192.168.110.71 -c get pxelinux.0

# Check TFTP permissions
ls -la /var/lib/tftpboot/

# Verify firewall
sudo firewall-cmd --list-all
```

### Issue: Inspection Timeout
```bash
# Increase inspection timeout in Metal3
oc patch provisioning provisioning-configuration \
  --type merge -p '{"spec":{"watchAllNamespaces":true,"inspectTimeout":"60m"}}'
```

## Advanced Configuration

### Custom Boot Parameters
Modify `/var/lib/tftpboot/pxelinux.cfg/default` to add custom parameters:
```
APPEND initrd=images/ironic-python-agent.initramfs ip=dhcp \
       boot_option=netboot systemd.journald.forward_to_console=yes \
       ironic_callback_url=http://metal3.openshift-machine-api.svc.cluster.local:6385
```

### Multiple Node Provisioning
For adding multiple nodes simultaneously:
1. Ensure sufficient DHCP pool size
2. Monitor Metal3 pod resources
3. Stagger node additions to avoid resource contention

### Production Considerations
- Use dedicated VLAN for provisioning network
- Implement DHCP reservations for predictable IPs
- Configure redundant PXE servers for high availability
- Use external image registry for faster downloads

## Success Criteria
After successful setup, you should see:
- ✅ skinner-worker-1 transitions from "inspecting" to "available"
- ✅ Hardware profile populated with VM specs
- ✅ Node ready for MachineSet scaling or manual provisioning
- ✅ Additional nodes can be added using the same process

## Next Steps: Adding More Nodes
Once infrastructure is working:
1. Create new VM in VMware
2. Add to IPMI bridge configuration
3. Create BareMetalHost resource
4. Node will automatically go through inspection and become available

This setup provides a complete lab environment for dynamic bare metal node provisioning in OpenShift.
