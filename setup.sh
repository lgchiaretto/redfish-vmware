#!/bin/bash

# IPMI VMware Bridge - Complete Setup Script
# This script configures the entire IPMI bridge with SystemD integration

set -e  # Exit on any error

# Colors for better output
RED='\033[0;31mm'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

echo -e "${BLUE}🚀 IPMI VMware Bridge - Complete Setup${NC}"
echo -e "${BLUE}=====================================${NC}"
echo ""

# Check if running as root for SystemD operations
if [[ $EUID -eq 0 ]]; then
    echo -e "${GREEN}✅ Running as root - Can configure SystemD service${NC}"
    SYSTEMD_SETUP=true
else
    echo -e "${YELLOW}⚠️ Not running as root - SystemD setup will require sudo${NC}"
    SYSTEMD_SETUP=false
fi

# Function to run command with sudo if needed
run_sudo() {
    if [[ $EUID -eq 0 ]]; then
        "$@"
    else
        sudo "$@"
    fi
}

echo -e "${BLUE}📂 Project Structure:${NC}"
echo "   📁 Source Code: $PROJECT_ROOT/src/"
echo "   📁 Configuration: $PROJECT_ROOT/config/"
echo "   📁 Tests: $PROJECT_ROOT/tests/"
echo "   📁 Documentation: $PROJECT_ROOT/docs/"
echo ""

# 1. Check Python dependencies
echo -e "${BLUE}🐍 Checking Python Dependencies...${NC}"
python3 -c "import pyghmi, pyvmomi" 2>/dev/null || {
    echo -e "${YELLOW}📦 Installing required Python packages...${NC}"
    pip3 install pyghmi pyvmomi
}
echo -e "${GREEN}✅ Python dependencies OK${NC}"

# 2. Validate configuration
echo -e "${BLUE}🔧 Validating Configuration...${NC}"
if [[ ! -f "$PROJECT_ROOT/config/config.json" ]]; then
    echo -e "${RED}❌ Configuration file not found: $PROJECT_ROOT/config/config.json${NC}"
    exit 1
fi

# Test configuration syntax
python3 -c "import json; json.load(open('$PROJECT_ROOT/config/config.json'))" || {
    echo -e "${RED}❌ Invalid JSON in configuration file${NC}"
    exit 1
}
echo -e "${GREEN}✅ Configuration file is valid${NC}"

# 3. Set up logging directory
echo -e "${BLUE}📝 Setting up logging...${NC}"
run_sudo mkdir -p /var/log
run_sudo touch /var/log/ipmi-vmware-bridge.log
run_sudo chmod 644 /var/log/ipmi-vmware-bridge.log
echo -e "${GREEN}✅ Log file created: /var/log/ipmi-vmware-bridge.log${NC}"

# 4. Stop existing service if running
echo -e "${BLUE}🛑 Checking existing service...${NC}"
if run_sudo systemctl is-active --quiet ipmi-vmware-bridge 2>/dev/null; then
    echo -e "${YELLOW}🔄 Stopping existing service...${NC}"
    run_sudo systemctl stop ipmi-vmware-bridge
    echo -e "${GREEN}✅ Service stopped${NC}"
else
    echo -e "${GREEN}✅ No existing service running${NC}"
fi

# 5. Install SystemD service
echo -e "${BLUE}⚙️ Installing SystemD service...${NC}"

# Remove old service file if exists
if [[ -f /etc/systemd/system/ipmi-vmware-bridge.service ]]; then
    echo -e "${YELLOW}🗑️ Removing old service file...${NC}"
    run_sudo rm /etc/systemd/system/ipmi-vmware-bridge.service
fi

# Copy new service file
echo -e "${YELLOW}📋 Installing new service configuration...${NC}"
run_sudo cp "$PROJECT_ROOT/config/ipmi-vmware-bridge.service" /etc/systemd/system/

# Update service file with current project path
echo -e "${YELLOW}🔧 Updating service paths...${NC}"
run_sudo sed -i "s|/home/lchiaret/git/ipmi-vmware|$PROJECT_ROOT|g" /etc/systemd/system/ipmi-vmware-bridge.service

# Reload SystemD
echo -e "${YELLOW}🔄 Reloading SystemD daemon...${NC}"
run_sudo systemctl daemon-reload

echo -e "${GREEN}✅ SystemD service installed${NC}"

# 6. Enable and start service
echo -e "${BLUE}🚀 Starting IPMI Bridge Service...${NC}"

# Enable service for auto-start
run_sudo systemctl enable ipmi-vmware-bridge
echo -e "${GREEN}✅ Service enabled for auto-start${NC}"

# Start service
run_sudo systemctl start ipmi-vmware-bridge
echo -e "${GREEN}✅ Service started${NC}"

# 7. Verify service status
echo -e "${BLUE}📊 Service Status:${NC}"
sleep 2  # Give service time to start

if run_sudo systemctl is-active --quiet ipmi-vmware-bridge; then
    echo -e "${GREEN}✅ Service is running${NC}"
    
    # Show service details
    echo ""
    echo -e "${BLUE}📋 Service Details:${NC}"
    run_sudo systemctl status ipmi-vmware-bridge --no-pager -l | head -15
    
    echo ""
    echo -e "${BLUE}🔌 IPMI Ports Status:${NC}"
    ss -tuln | grep -E ':(623|624|625|626)' || echo -e "${YELLOW}⚠️ IPMI ports not yet bound (service may still be starting)${NC}"
    
else
    echo -e "${RED}❌ Service failed to start${NC}"
    echo -e "${YELLOW}📝 Service logs:${NC}"
    run_sudo journalctl -u ipmi-vmware-bridge --since "1 minute ago" --no-pager
    exit 1
fi

# 8. Test IPMI connectivity
echo ""
echo -e "${BLUE}🧪 Testing IPMI Connectivity...${NC}"
sleep 3  # Give more time for ports to bind

echo -e "${YELLOW}🔍 Testing port 623 with correct password...${NC}"
timeout 10 ipmitool -I lan -H 127.0.0.1 -p 623 -U admin -P password mc info 2>/dev/null && {
    echo -e "${GREEN}✅ IPMI test successful!${NC}"
} || {
    echo -e "${YELLOW}⚠️ IPMI test failed - this is normal if service is still initializing${NC}"
    echo -e "${YELLOW}💡 Check logs: sudo journalctl -u ipmi-vmware-bridge -f${NC}"
}

# 9. Show useful commands
echo ""
echo -e "${BLUE}🎯 Management Commands:${NC}"
echo -e "${GREEN}# View service status:${NC}"
echo "   sudo systemctl status ipmi-vmware-bridge"
echo ""
echo -e "${GREEN}# View real-time logs:${NC}"
echo "   sudo journalctl -u ipmi-vmware-bridge -f"
echo ""
echo -e "${GREEN}# Restart service:${NC}"
echo "   sudo systemctl restart ipmi-vmware-bridge"
echo ""
echo -e "${GREEN}# Stop service:${NC}"
echo "   sudo systemctl stop ipmi-vmware-bridge"
echo ""
echo -e "${GREEN}# Test IPMI (use password 'password'):${NC}"
echo "   ipmitool -I lan -H 127.0.0.1 -p 623 -U admin -P password mc info"
echo ""

# 10. Show OpenShift BMH example
echo -e "${BLUE}🎯 OpenShift BareMetalHost Configuration:${NC}"
cat << 'EOF'
apiVersion: metal3.io/v1alpha1
kind: BareMetalHost
metadata:
  name: willie-master-0
spec:
  bmc:
    address: ipmi://127.0.0.1:623
    credentialsName: willie-master-0-bmc-secret
  bootMACAddress: "00:50:56:xx:xx:xx"
---
apiVersion: v1
kind: Secret
metadata:
  name: willie-master-0-bmc-secret
type: Opaque
data:
  username: YWRtaW4=  # admin
  password: cGFzc3dvcmQ=  # password
EOF

echo ""
echo -e "${GREEN}🎉 IPMI VMware Bridge setup completed successfully!${NC}"
echo -e "${BLUE}📡 Ready to receive IPMI calls from OpenShift Virtualization${NC}"
    print_info "Debug mode is ENABLED by default for OpenShift troubleshooting"
    print_info "Set IPMI_DEBUG=false to disable verbose logging"
}

# Command line options
case "${1:-}" in
    "test")
        test_config
        ;;
    "install-service")
        check_root || { print_error "Must be root to install service"; exit 1; }
        install_service 0
        ;;
    "deps")
        install_dependencies
        ;;
    *)
        main
        ;;
esac
