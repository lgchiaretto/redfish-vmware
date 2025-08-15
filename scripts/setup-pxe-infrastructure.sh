#!/bin/bash

# Setup PXE Infrastructure for OpenShift Bare Metal Lab
# This script creates a complete PXE/DHCP environment for dynamic node provisioning

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PXE_NETWORK="192.168.110.0/24"
PXE_GATEWAY="192.168.110.1"
PXE_DNS="8.8.8.8"
DHCP_RANGE_START="192.168.110.100"
DHCP_RANGE_END="192.168.110.200"
PXE_SERVER_IP="192.168.110.71"
PXE_INTERFACE="ens35"
TFTP_ROOT="/var/lib/tftpboot"
HTTP_ROOT="/var/www/html"

echo -e "${BLUE}=== OpenShift Bare Metal PXE Infrastructure Setup ===${NC}"
echo -e "${YELLOW}This will create a complete PXE environment for dynamic node provisioning${NC}"
echo

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root${NC}"
   exit 1
fi

# Check if PXE interface has the required IP
check_network_prerequisites() {
    echo -e "${BLUE}Checking network prerequisites...${NC}"
    
    if ! ip addr show ${PXE_INTERFACE} | grep -q "${PXE_SERVER_IP}"; then
        echo -e "${YELLOW}Interface ${PXE_INTERFACE} does not have IP ${PXE_SERVER_IP}${NC}"
        echo -e "${BLUE}Please run the network setup first:${NC}"
        echo -e "${YELLOW}sudo ./scripts/setup-persistent-network.sh${NC}"
        echo
        read -p "Do you want to continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        echo -e "${GREEN}✓ Interface ${PXE_INTERFACE} has IP ${PXE_SERVER_IP}${NC}"
    fi
}

# Function to install packages
install_packages() {
    echo -e "${BLUE}Installing required packages...${NC}"
    dnf install -y dnsmasq httpd tftp-server syslinux wget curl
    systemctl enable dnsmasq httpd tftp
}

# Function to configure dnsmasq for DHCP/TFTP
configure_dnsmasq() {
    echo -e "${BLUE}Configuring dnsmasq for DHCP/TFTP...${NC}"
    
    cat > /etc/dnsmasq.conf << EOF
# DHCP Configuration for Bare Metal Provisioning
interface=${PXE_INTERFACE}
dhcp-range=${DHCP_RANGE_START},${DHCP_RANGE_END},12h
dhcp-option=3,${PXE_GATEWAY}  # Gateway
dhcp-option=6,${PXE_DNS}      # DNS

# PXE Boot Configuration
enable-tftp
tftp-root=${TFTP_ROOT}
dhcp-boot=pxelinux.0,${PXE_SERVER_IP}

# Logging
log-dhcp
log-queries

# Disable DNS to avoid conflicts
port=0
EOF
}

# Function to setup TFTP structure
setup_tftp() {
    echo -e "${BLUE}Setting up TFTP structure...${NC}"
    
    mkdir -p ${TFTP_ROOT}/{pxelinux.cfg,images}
    
    # Copy PXE boot files
    cp /usr/share/syslinux/pxelinux.0 ${TFTP_ROOT}/
    cp /usr/share/syslinux/menu.c32 ${TFTP_ROOT}/
    cp /usr/share/syslinux/ldlinux.c32 ${TFTP_ROOT}/
    
    # Create default PXE configuration
    cat > ${TFTP_ROOT}/pxelinux.cfg/default << EOF
DEFAULT menu.c32
PROMPT 0
TIMEOUT 300
ONTIMEOUT ironic-python-agent

MENU TITLE OpenShift Bare Metal Provisioning
MENU AUTOBOOT Starting Ironic Python Agent in # seconds

LABEL ironic-python-agent
    MENU LABEL Ironic Python Agent (IPA)
    KERNEL images/ironic-python-agent.kernel
    APPEND initrd=images/ironic-python-agent.initramfs ip=dhcp boot_option=netboot systemd.journald.forward_to_console=yes
EOF
    
    # Set permissions
    chmod -R 755 ${TFTP_ROOT}
    chown -R root:root ${TFTP_ROOT}
}

# Function to setup HTTP server
setup_http() {
    echo -e "${BLUE}Setting up HTTP server...${NC}"
    
    mkdir -p ${HTTP_ROOT}/images
    
    # Create simple index page
    cat > ${HTTP_ROOT}/index.html << EOF
<!DOCTYPE html>
<html>
<head>
    <title>OpenShift Bare Metal Provisioning Server</title>
</head>
<body>
    <h1>OpenShift Bare Metal Provisioning Server</h1>
    <p>This server provides PXE boot images for OpenShift bare metal node provisioning.</p>
    <ul>
        <li><a href="/images/">Boot Images</a></li>
    </ul>
</body>
</html>
EOF
    
    # Set permissions
    chmod -R 755 ${HTTP_ROOT}
    chown -R apache:apache ${HTTP_ROOT}
}

# Function to download Ironic Python Agent
download_ipa() {
    echo -e "${BLUE}Setting up placeholder IPA images...${NC}"
    
    # Create placeholder files for now - you can replace with actual IPA images later
    cd ${TFTP_ROOT}/images
    
    echo -e "${YELLOW}Creating placeholder kernel...${NC}"
    echo "placeholder-kernel" > ironic-python-agent.kernel
    
    echo -e "${YELLOW}Creating placeholder initramfs...${NC}"
    echo "placeholder-initramfs" > ironic-python-agent.initramfs
    
    # Also copy to HTTP root for direct access
    cp ironic-python-agent.* ${HTTP_ROOT}/images/
    
    echo -e "${YELLOW}IPA placeholder images created. Replace with actual images later.${NC}"
    echo -e "${BLUE}To get actual IPA images, download from your OpenShift installation or mirror.${NC}"
}

# Function to configure firewall
configure_firewall() {
    echo -e "${BLUE}Configuring firewall...${NC}"
    
    # Open required ports
    firewall-cmd --permanent --add-service=dhcp
    firewall-cmd --permanent --add-service=tftp
    firewall-cmd --permanent --add-service=http
    firewall-cmd --permanent --add-port=4011/udp  # PXE
    firewall-cmd --reload
}

# Function to verify network interface
verify_network_interface() {
    echo -e "${BLUE}Verifying network interface ${PXE_INTERFACE}...${NC}"
    
    if ip addr show ${PXE_INTERFACE} | grep -q "${PXE_SERVER_IP}"; then
        echo -e "${GREEN}✓ Interface ${PXE_INTERFACE} has IP ${PXE_SERVER_IP}${NC}"
    else
        echo -e "${RED}✗ Interface ${PXE_INTERFACE} does not have IP ${PXE_SERVER_IP}${NC}"
        echo -e "${YELLOW}Current configuration:${NC}"
        ip addr show ${PXE_INTERFACE}
        exit 1
    fi
}

# Function to start services
start_services() {
    echo -e "${BLUE}Starting services...${NC}"
    
    systemctl start dnsmasq
    systemctl start httpd
    systemctl start tftp
    
    echo -e "${GREEN}All services started successfully${NC}"
}

# Function to show status
show_status() {
    echo -e "${BLUE}=== Service Status ===${NC}"
    systemctl status dnsmasq --no-pager -l
    systemctl status httpd --no-pager -l
    systemctl status tftp --no-pager -l
    
    echo -e "${BLUE}=== Network Configuration ===${NC}"
    ip addr show ${PXE_INTERFACE}
    
    echo -e "${BLUE}=== DHCP Leases ===${NC}"
    cat /var/lib/dhcp/dhcpd.leases 2>/dev/null || echo "No leases yet"
    
    echo -e "${GREEN}=== PXE Infrastructure Ready ===${NC}"
    echo -e "${YELLOW}DHCP Range: ${DHCP_RANGE_START} - ${DHCP_RANGE_END}${NC}"
    echo -e "${YELLOW}PXE Server: ${PXE_SERVER_IP}${NC}"
    echo -e "${YELLOW}TFTP Root: ${TFTP_ROOT}${NC}"
    echo -e "${YELLOW}HTTP Root: ${HTTP_ROOT}${NC}"
}

# Main execution
main() {
    echo -e "${YELLOW}Starting PXE infrastructure setup...${NC}"
    
    check_network_prerequisites
    install_packages
    configure_dnsmasq
    setup_tftp
    setup_http
    download_ipa
    configure_firewall
    verify_network_interface
    start_services
    show_status
    
    echo -e "${GREEN}PXE infrastructure setup completed!${NC}"
    echo -e "${YELLOW}Next steps:${NC}"
    echo -e "1. Configure your VMs to use the virbr1 network for PXE boot"
    echo -e "2. Set the VM boot order to Network first"
    echo -e "3. The BareMetalHost should now complete inspection automatically"
}

# Run main function
main "$@"
