#!/bin/bash

# Script to download RHCOS live images for IPA (alternative approach)
# These images are compatible with OpenShift 4.18 and work for inspection

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

TFTP_ROOT="/var/lib/tftpboot"
HTTP_ROOT="/var/www/html"
RHCOS_VERSION="4.18.1"
RHCOS_BASE_URL="https://mirror.openshift.com/pub/openshift-v4/x86_64/dependencies/rhcos/4.18/latest"

echo -e "${BLUE}=== Downloading RHCOS Live Images for IPA ===${NC}"
echo -e "${YELLOW}Using RHCOS ${RHCOS_VERSION} compatible with OpenShift 4.18${NC}"
echo

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root${NC}"
   exit 1
fi

# Function to download RHCOS live images
download_rhcos_live() {
    echo -e "${BLUE}Downloading RHCOS live kernel and initramfs...${NC}"
    
    cd /tmp
    
    echo -e "${YELLOW}Downloading live kernel...${NC}"
    if wget -O rhcos-live-kernel "${RHCOS_BASE_URL}/rhcos-${RHCOS_VERSION}-x86_64-live-kernel-x86_64"; then
        echo -e "${GREEN}✓ Kernel downloaded successfully${NC}"
    else
        echo -e "${RED}✗ Failed to download kernel${NC}"
        return 1
    fi
    
    echo -e "${YELLOW}Downloading live initramfs...${NC}"
    if wget -O rhcos-live-initramfs "${RHCOS_BASE_URL}/rhcos-${RHCOS_VERSION}-x86_64-live-initramfs.x86_64.img"; then
        echo -e "${GREEN}✓ Initramfs downloaded successfully${NC}"
    else
        echo -e "${RED}✗ Failed to download initramfs${NC}"
        return 1
    fi
    
    # Copy to TFTP and HTTP directories
    echo -e "${BLUE}Deploying to TFTP and HTTP directories...${NC}"
    cp rhcos-live-kernel ${TFTP_ROOT}/images/ironic-python-agent.kernel
    cp rhcos-live-initramfs ${TFTP_ROOT}/images/ironic-python-agent.initramfs
    cp rhcos-live-kernel ${HTTP_ROOT}/images/ironic-python-agent.kernel
    cp rhcos-live-initramfs ${HTTP_ROOT}/images/ironic-python-agent.initramfs
    
    # Set permissions
    chmod 644 ${TFTP_ROOT}/images/ironic-python-agent.*
    chmod 644 ${HTTP_ROOT}/images/ironic-python-agent.*
    chown root:root ${TFTP_ROOT}/images/ironic-python-agent.*
    chown apache:apache ${HTTP_ROOT}/images/ironic-python-agent.*
    
    # Cleanup temp files
    rm -f rhcos-live-kernel rhcos-live-initramfs
    
    echo -e "${GREEN}✓ RHCOS live images deployed successfully${NC}"
}

# Function to update PXE configuration for RHCOS live
update_pxe_config() {
    echo -e "${BLUE}Updating PXE configuration for RHCOS live boot...${NC}"
    
    # Update PXE config with proper live boot parameters
    cat > ${TFTP_ROOT}/pxelinux.cfg/default << 'EOF'
DEFAULT ironic-python-agent
PROMPT 0
TIMEOUT 30
ONTIMEOUT ironic-python-agent

LABEL ironic-python-agent
    KERNEL images/ironic-python-agent.kernel
    APPEND initrd=images/ironic-python-agent.initramfs ip=dhcp boot_option=netboot systemd.journald.forward_to_console=yes ipa-inspection-callback-url=http://192.168.110.50:6388/v1/continue ipa-api-url=http://192.168.110.50:6388 coreos.live.rootfs_url=http://192.168.110.71/images/ironic-python-agent.initramfs
EOF

    # Update GRUB config for UEFI boot
    cat > ${TFTP_ROOT}/grub.cfg << 'EOF'
set default="0"
set timeout=30

menuentry 'Ironic Python Agent (RHCOS Live)' {
    linuxefi images/ironic-python-agent.kernel ip=dhcp boot_option=netboot systemd.journald.forward_to_console=yes ipa-inspection-callback-url=http://192.168.110.50:6388/v1/continue ipa-api-url=http://192.168.110.50:6388 coreos.live.rootfs_url=http://192.168.110.71/images/ironic-python-agent.initramfs
    initrdefi images/ironic-python-agent.initramfs
}
EOF

    # Copy GRUB config to EFI directory too
    cp ${TFTP_ROOT}/grub.cfg ${TFTP_ROOT}/efi64/
    
    echo -e "${GREEN}✓ PXE configuration updated${NC}"
}

# Function to verify downloaded files
verify_files() {
    echo -e "${BLUE}Verifying downloaded files...${NC}"
    
    if [[ -f "${TFTP_ROOT}/images/ironic-python-agent.kernel" && -f "${TFTP_ROOT}/images/ironic-python-agent.initramfs" ]]; then
        echo -e "${GREEN}✓ Files exist in TFTP directory${NC}"
        
        kernel_size=$(du -h ${TFTP_ROOT}/images/ironic-python-agent.kernel | cut -f1)
        initramfs_size=$(du -h ${TFTP_ROOT}/images/ironic-python-agent.initramfs | cut -f1)
        
        echo -e "${YELLOW}Kernel size: ${kernel_size}${NC}"
        echo -e "${YELLOW}Initramfs size: ${initramfs_size}${NC}"
        
        # Verify they are not small placeholder files
        kernel_bytes=$(stat -f%z ${TFTP_ROOT}/images/ironic-python-agent.kernel 2>/dev/null || stat -c%s ${TFTP_ROOT}/images/ironic-python-agent.kernel)
        initramfs_bytes=$(stat -f%z ${TFTP_ROOT}/images/ironic-python-agent.initramfs 2>/dev/null || stat -c%s ${TFTP_ROOT}/images/ironic-python-agent.initramfs)
        
        if [[ ${kernel_bytes} -gt 1000000 ]]; then  # > 1MB
            echo -e "${GREEN}✓ Kernel appears to be a valid boot image${NC}"
        else
            echo -e "${RED}✗ Kernel file seems too small${NC}"
            return 1
        fi
        
        if [[ ${initramfs_bytes} -gt 10000000 ]]; then  # > 10MB
            echo -e "${GREEN}✓ Initramfs appears to be a valid boot image${NC}"
        else
            echo -e "${RED}✗ Initramfs file seems too small${NC}"
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

# Main execution
main() {
    echo -e "${YELLOW}Starting RHCOS live images download...${NC}"
    
    download_rhcos_live
    update_pxe_config
    verify_files
    restart_services
    
    echo -e "${GREEN}RHCOS live images deployment completed!${NC}"
    echo -e "${YELLOW}Next steps:${NC}"
    echo -e "1. Test PXE boot with: ipmitool -I lanplus -H 192.168.110.71 -p 626 -U admin -P password power reset"
    echo -e "2. Monitor with: sudo journalctl -u dnsmasq -f"
    echo -e "3. Check BareMetalHost status: oc get baremetalhosts skinner-worker-1 -n openshift-machine-api"
}

# Run main function
main "$@"
