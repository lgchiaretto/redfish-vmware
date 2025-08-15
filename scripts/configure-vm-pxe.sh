#!/bin/bash

# Quick VMware VM Network Configuration for PXE Boot
# This script helps configure VMware VMs for PXE boot access

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
VCENTER_HOST="${VCENTER_HOST:-}"
VCENTER_USER="${VCENTER_USER:-}"
VCENTER_PASS="${VCENTER_PASS:-}"
VM_NAME="${1:-}"

usage() {
    echo "Usage: $0 <VM_NAME>"
    echo "Environment variables:"
    echo "  VCENTER_HOST - vCenter hostname or IP"
    echo "  VCENTER_USER - vCenter username"
    echo "  VCENTER_PASS - vCenter password"
    echo
    echo "Example:"
    echo "  VCENTER_HOST=vcenter.lab.com VCENTER_USER=admin VCENTER_PASS=password $0 skinner-worker-1"
    exit 1
}

if [[ -z "$VM_NAME" ]]; then
    usage
fi

check_prerequisites() {
    echo -e "${BLUE}Checking prerequisites...${NC}"
    
    if ! command -v govc &> /dev/null; then
        echo -e "${RED}govc is required but not installed${NC}"
        echo "Install with: go install github.com/vmware/govmomi/govc@latest"
        exit 1
    fi
    
    if [[ -z "$VCENTER_HOST" || -z "$VCENTER_USER" || -z "$VCENTER_PASS" ]]; then
        echo -e "${RED}Missing vCenter credentials${NC}"
        usage
    fi
    
    export GOVC_URL="$VCENTER_USER:$VCENTER_PASS@$VCENTER_HOST"
    export GOVC_INSECURE=1
}

get_vm_info() {
    echo -e "${BLUE}Getting VM information...${NC}"
    
    # Get VM path
    VM_PATH=$(govc find . -type m -name "$VM_NAME" | head -1)
    if [[ -z "$VM_PATH" ]]; then
        echo -e "${RED}VM '$VM_NAME' not found${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}Found VM: $VM_PATH${NC}"
    
    # Show current network configuration
    echo -e "${YELLOW}Current network configuration:${NC}"
    govc vm.info -json "$VM_PATH" | jq -r '.VirtualMachines[0].Config.Hardware.Device[] | select(.DeviceInfo.Label | startswith("Network")) | "Interface: \(.DeviceInfo.Label), MAC: \(.MacAddress), Network: \(.Backing.DeviceName // .Backing.Network.Name)"'
}

add_pxe_network() {
    echo -e "${BLUE}Adding PXE network interface...${NC}"
    
    # Get available networks
    echo -e "${YELLOW}Available networks:${NC}"
    govc ls /*/network | head -10
    
    # You can customize this to match your environment
    PXE_NETWORK="VM Network"  # Adjust this to your PXE network name
    
    echo -e "${YELLOW}Adding network interface connected to: $PXE_NETWORK${NC}"
    
    # Add network interface
    govc vm.network.add -vm "$VM_PATH" -net "$PXE_NETWORK" -net.adapter vmxnet3
    
    echo -e "${GREEN}Network interface added${NC}"
}

configure_boot_order() {
    echo -e "${BLUE}Configuring boot order for PXE...${NC}"
    
    # Enable EFI boot and set network first
    govc vm.change -vm "$VM_PATH" -boot-delay 3000 -e="firmware=efi"
    
    # Note: Boot order configuration varies by VM version
    # This sets a reasonable delay for manual boot selection
    
    echo -e "${GREEN}Boot configuration updated${NC}"
    echo -e "${YELLOW}You may need to manually set network boot in VM BIOS/EFI${NC}"
}

show_vm_details() {
    echo -e "${BLUE}Updated VM configuration:${NC}"
    
    # Show all network interfaces
    govc vm.info -json "$VM_PATH" | jq -r '
        .VirtualMachines[0].Config.Hardware.Device[] | 
        select(.DeviceInfo.Label | startswith("Network")) | 
        "Interface: \(.DeviceInfo.Label), MAC: \(.MacAddress), Network: \(.Backing.DeviceName // .Backing.Network.Name)"
    '
    
    # Show boot configuration
    echo -e "${YELLOW}Boot delay: 3 seconds${NC}"
    echo -e "${YELLOW}Firmware: EFI${NC}"
}

create_pxe_setup_notes() {
    cat > "pxe-setup-notes-${VM_NAME}.txt" << EOF
PXE Setup Notes for ${VM_NAME}
==============================

VM Configuration:
- Added PXE network interface
- Set boot delay to 3 seconds
- Enabled EFI firmware

Manual Steps Required:
1. Power on the VM
2. During boot, press F2 to enter BIOS/EFI setup
3. Navigate to Boot tab
4. Set Network boot as first priority
5. Save and exit

Network Interfaces:
$(govc vm.info -json "$VM_PATH" | jq -r '.VirtualMachines[0].Config.Hardware.Device[] | select(.DeviceInfo.Label | startswith("Network")) | "- \(.DeviceInfo.Label): \(.MacAddress) on \(.Backing.DeviceName // .Backing.Network.Name)"')

Next Steps:
1. Ensure PXE server is running (192.168.110.71)
2. Power on VM for inspection
3. Monitor BareMetalHost status:
   oc get baremetalhosts ${VM_NAME} -n openshift-machine-api -w

EOF
    
    echo -e "${GREEN}Setup notes saved to: pxe-setup-notes-${VM_NAME}.txt${NC}"
}

main() {
    echo -e "${BLUE}=== VMware VM PXE Configuration ===${NC}"
    echo -e "${YELLOW}Configuring VM: $VM_NAME${NC}"
    echo
    
    check_prerequisites
    get_vm_info
    add_pxe_network
    configure_boot_order
    show_vm_details
    create_pxe_setup_notes
    
    echo -e "${GREEN}=== Configuration Complete ===${NC}"
    echo -e "${YELLOW}VM is now ready for PXE boot${NC}"
    echo -e "${BLUE}See pxe-setup-notes-${VM_NAME}.txt for manual steps${NC}"
}

main "$@"
