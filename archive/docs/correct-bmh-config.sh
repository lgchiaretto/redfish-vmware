#!/bin/bash
# OpenShift BareMetalHost Configuration for IPMI-VMware Bridge

cat << 'EOF'
# BareMetalHost configuration for OpenShift
# The BMC address should point to the IPMI server, not the node itself

apiVersion: metal3.io/v1alpha1
kind: BareMetalHost
metadata:
  name: willie-master-0
  namespace: openshift-machine-api
spec:
  online: true
  bmc:
    # IMPORTANT: Point to the IPMI server IP, not the node IP
    address: ipmi://192.168.86.168:623
    credentialsName: willie-master-0-bmc-secret
  # The actual node will be at 192.168.110.50, but BMC is at 192.168.86.168
  bootMACAddress: "00:50:56:XX:XX:XX"  # Replace with actual MAC
  # Custom userdata, image, etc. as needed
---
apiVersion: v1
kind: Secret
metadata:
  name: willie-master-0-bmc-secret
  namespace: openshift-machine-api
type: Opaque
data:
  username: YWRtaW4=  # base64 of 'admin'
  password: YWRtaW4=  # base64 of 'admin'
EOF

echo ""
echo "Configuration Notes:"
echo "==================="
echo "1. BMC Address: ipmi://192.168.86.168:623 (IPMI server)"
echo "2. Node IP will be: 192.168.110.50 (OpenShift node)"
echo "3. VM mapping: 192.168.110.50 -> willie-master-0"
echo ""
echo "The key insight is that:"
echo "- BMC address = Where the IPMI server is running (192.168.86.168)"
echo "- Node IP = Where the actual VM/node will be (192.168.110.50)"
echo "- VM mapping maps the node IP to the VM name for control"
