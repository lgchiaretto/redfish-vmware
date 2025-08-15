#!/bin/bash

# Script to download real IPA images from OpenShift release
# This replaces the placeholder images with actual Ironic Python Agent files

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

TFTP_ROOT="/var/lib/tftpboot"
HTTP_ROOT="/var/www/html"
IPA_IMAGE="quay.io/openshift-release-dev/ocp-v4.0-art-dev@sha256:863a1f518d2cb222a9c46919abb9a00d61afe34258b3fc4e814090d99f140f1d"

echo -e "${BLUE}=== Downloading Real IPA Images from OpenShift Release ===${NC}"
echo -e "${YELLOW}This will replace placeholder images with actual Ironic Python Agent files${NC}"
echo

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root${NC}"
   exit 1
fi

# Function to extract IPA images from container
extract_ipa_images() {
    echo -e "${BLUE}Extracting IPA images from OpenShift container...${NC}"
    
    # Create temporary directory
    TEMP_DIR=$(mktemp -d)
    cd ${TEMP_DIR}
    
    echo -e "${YELLOW}Pulling IPA container image...${NC}"
    podman pull ${IPA_IMAGE}
    
    echo -e "${YELLOW}Creating container from image...${NC}"
    CONTAINER_ID=$(podman create ${IPA_IMAGE})
    
    echo -e "${YELLOW}Extracting files from container...${NC}"
    podman export ${CONTAINER_ID} | tar -x
    
    echo -e "${YELLOW}Looking for IPA kernel and initramfs...${NC}"
    
    # Find the actual IPA files - they might be in different locations
    IPA_KERNEL=$(find . -name "*ironic*kernel*" -o -name "*ipa*kernel*" -o -name "vmlinuz*" | head -1)
    IPA_INITRAMFS=$(find . -name "*ironic*initramfs*" -o -name "*ipa*initramfs*" -o -name "initramfs*" | head -1)
    
    if [[ -z "${IPA_KERNEL}" ]]; then
        echo -e "${YELLOW}Kernel not found with standard names, searching in /usr/share...${NC}"
        IPA_KERNEL=$(find ./usr/share -name "*kernel*" -o -name "vmlinuz*" 2>/dev/null | head -1)
    fi
    
    if [[ -z "${IPA_INITRAMFS}" ]]; then
        echo -e "${YELLOW}Initramfs not found with standard names, searching in /usr/share...${NC}"
        IPA_INITRAMFS=$(find ./usr/share -name "*initramfs*" -o -name "*initrd*" 2>/dev/null | head -1)
    fi
    
    if [[ -n "${IPA_KERNEL}" && -n "${IPA_INITRAMFS}" ]]; then
        echo -e "${GREEN}Found IPA files:${NC}"
        echo -e "${YELLOW}Kernel: ${IPA_KERNEL}${NC}"
        echo -e "${YELLOW}Initramfs: ${IPA_INITRAMFS}${NC}"
        
        # Copy to TFTP and HTTP directories
        echo -e "${BLUE}Copying to TFTP and HTTP directories...${NC}"
        cp "${IPA_KERNEL}" ${TFTP_ROOT}/images/ironic-python-agent.kernel
        cp "${IPA_INITRAMFS}" ${TFTP_ROOT}/images/ironic-python-agent.initramfs
        cp "${IPA_KERNEL}" ${HTTP_ROOT}/images/ironic-python-agent.kernel
        cp "${IPA_INITRAMFS}" ${HTTP_ROOT}/images/ironic-python-agent.initramfs
        
        # Set permissions
        chmod 644 ${TFTP_ROOT}/images/ironic-python-agent.*
        chmod 644 ${HTTP_ROOT}/images/ironic-python-agent.*
        chown root:root ${TFTP_ROOT}/images/ironic-python-agent.*
        chown apache:apache ${HTTP_ROOT}/images/ironic-python-agent.*
        
        echo -e "${GREEN}✓ IPA images successfully extracted and deployed${NC}"
    else
        echo -e "${RED}✗ Could not find IPA kernel or initramfs in container${NC}"
        echo -e "${YELLOW}Available files in container:${NC}"
        find . -type f -name "*kernel*" -o -name "*initramfs*" -o -name "*vmlinuz*" -o -name "*initrd*" | head -20
        
        echo -e "${YELLOW}Trying alternative approach - copying all potential files...${NC}"
        mkdir -p /tmp/ipa-files
        find . -type f \( -name "*kernel*" -o -name "*initramfs*" -o -name "*vmlinuz*" -o -name "*initrd*" \) -exec cp {} /tmp/ipa-files/ \;
        ls -la /tmp/ipa-files/
        
        cleanup_and_exit 1
    fi
    
    # Cleanup
    echo -e "${BLUE}Cleaning up...${NC}"
    podman rm ${CONTAINER_ID}
    cd /
    rm -rf ${TEMP_DIR}
    
    echo -e "${GREEN}IPA images extraction completed successfully!${NC}"
}

# Function to verify extracted files
verify_files() {
    echo -e "${BLUE}Verifying extracted files...${NC}"
    
    if [[ -f "${TFTP_ROOT}/images/ironic-python-agent.kernel" && -f "${TFTP_ROOT}/images/ironic-python-agent.initramfs" ]]; then
        echo -e "${GREEN}✓ Files exist in TFTP directory${NC}"
        echo -e "${YELLOW}Kernel size: $(du -h ${TFTP_ROOT}/images/ironic-python-agent.kernel | cut -f1)${NC}"
        echo -e "${YELLOW}Initramfs size: $(du -h ${TFTP_ROOT}/images/ironic-python-agent.initramfs | cut -f1)${NC}"
        
        # Verify they are not the placeholder files
        if ! grep -q "placeholder" ${TFTP_ROOT}/images/ironic-python-agent.kernel; then
            echo -e "${GREEN}✓ Kernel is not a placeholder file${NC}"
        else
            echo -e "${RED}✗ Kernel is still a placeholder file${NC}"
            return 1
        fi
        
        if ! grep -q "placeholder" ${TFTP_ROOT}/images/ironic-python-agent.initramfs; then
            echo -e "${GREEN}✓ Initramfs is not a placeholder file${NC}"
        else
            echo -e "${RED}✗ Initramfs is still a placeholder file${NC}"
            return 1
        fi
    else
        echo -e "${RED}✗ Files not found in TFTP directory${NC}"
        return 1
    fi
    
    echo -e "${GREEN}File verification completed successfully!${NC}"
}

# Function to restart services
restart_services() {
    echo -e "${BLUE}Restarting PXE services...${NC}"
    systemctl restart dnsmasq
    systemctl restart httpd
    echo -e "${GREEN}✓ Services restarted${NC}"
}

# Function for cleanup on exit
cleanup_and_exit() {
    local exit_code=${1:-0}
    if [[ -n "${CONTAINER_ID:-}" ]]; then
        podman rm ${CONTAINER_ID} 2>/dev/null || true
    fi
    if [[ -n "${TEMP_DIR:-}" ]]; then
        rm -rf ${TEMP_DIR} 2>/dev/null || true
    fi
    exit ${exit_code}
}

# Main execution
main() {
    echo -e "${YELLOW}Starting IPA images download...${NC}"
    
    extract_ipa_images
    verify_files
    restart_services
    
    echo -e "${GREEN}Real IPA images deployment completed!${NC}"
    echo -e "${YELLOW}Next steps:${NC}"
    echo -e "1. Test PXE boot with: ipmitool -I lanplus -H 192.168.110.71 -p 626 -U admin -P password power reset"
    echo -e "2. Monitor with: sudo journalctl -u dnsmasq -f"
    echo -e "3. Check BareMetalHost status: oc get baremetalhosts willie-worker-1 -n openshift-machine-api"
}

# Set trap for cleanup
trap cleanup_and_exit EXIT

# Run main function
main "$@"
