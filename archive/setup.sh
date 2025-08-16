#!/bin/bash

# IPMI VMware Bridge - Complete Setup Script
# This script configures the entire IPMI bridge with SystemD integration

set -e  # Exit on any error

# Colors for better output
RED='\033[0;31m'
GREEN='\033[0;32m'
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

# Check for debug mode
DEBUG_MODE=${IPMI_DEBUG:-false}
if [[ "$DEBUG_MODE" == "true" ]]; then
    echo -e "${YELLOW}🐛 DEBUG MODE ENABLED - Detailed OpenShift communication logging${NC}"
else
    echo -e "${BLUE}📋 PRODUCTION MODE - Standard logging${NC}"
    echo -e "${YELLOW}💡 Set IPMI_DEBUG=true for detailed OpenShift debugging${NC}"
fi

print_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }


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

# 8. Clean up old files
echo ""
echo -e "${BLUE}🧹 Cleaning up old/unused files...${NC}"

# Remove old archive files that are not needed
echo -e "${YELLOW}🗑️ Removing unused archive files...${NC}"
if [[ -d "$PROJECT_ROOT/archive" ]]; then
    # Keep only essential files in archive for reference
    find "$PROJECT_ROOT/archive" -name "*.log" -exec rm -f {} \; 2>/dev/null || true
    find "$PROJECT_ROOT/archive" -name "*.pid" -exec rm -f {} \; 2>/dev/null || true
    find "$PROJECT_ROOT/archive/tmp" -type f -exec rm -f {} \; 2>/dev/null || true
    echo -e "${GREEN}✅ Cleaned up archive log files${NC}"
fi

# Remove test output files
find "$PROJECT_ROOT" -name "*.pyc" -exec rm -f {} \; 2>/dev/null || true
find "$PROJECT_ROOT" -name "__pycache__" -type d -exec rm -rf {} \; 2>/dev/null || true
echo -e "${GREEN}✅ Cleaned up Python cache files${NC}"

# 9. Test IPMI connectivity including OpenShift worker port
echo ""
echo -e "${BLUE}🧪 Testing IPMI Connectivity...${NC}"
sleep 3  # Give more time for ports to bind

echo -e "${YELLOW}🔍 Testing port 623 (skinner-master-0)...${NC}"
timeout 10 ipmitool -I lanplus -H 127.0.0.1 -p 623 -U admin -P password mc info 2>/dev/null && {
    echo -e "${GREEN}✅ Port 623 IPMI test successful!${NC}"
} || {
    echo -e "${YELLOW}⚠️ Port 623 test failed - service may still be initializing${NC}"
}

echo -e "${YELLOW}🔍 Testing port 627 (skinner-worker-2) for OpenShift inspection...${NC}"
timeout 10 ipmitool -I lanplus -H 127.0.0.1 -p 627 -U admin -P password chassis status 2>/dev/null && {
    echo -e "${GREEN}✅ Port 627 IPMI test successful! OpenShift worker ready${NC}"
} || {
    echo -e "${YELLOW}⚠️ Port 627 test failed - check service logs for worker-2${NC}"
}

echo -e "${BLUE}🔌 Port binding status:${NC}"
ss -tuln | grep -E ':(623|624|625|626|627)' && {
    echo -e "${GREEN}✅ All IPMI ports are bound${NC}"
} || {
    echo -e "${YELLOW}⚠️ Some IPMI ports not bound - service may still be starting${NC}"
    echo -e "${YELLOW}💡 Check logs: sudo journalctl -u ipmi-vmware-bridge -f${NC}"
}

# 10. Show useful commands
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
echo "   ipmitool -I lanplus -H 127.0.0.1 -p 623 -U admin -P password mc info"
echo ""

# 11. Show OpenShift BMH example
echo -e "${BLUE}🎯 OpenShift BareMetalHost Configuration:${NC}"
cat << 'EOF'
apiVersion: metal3.io/v1alpha1
kind: BareMetalHost
metadata:
  name: skinner-master-0
spec:
  bmc:
    address: ipmi://127.0.0.1:623
    credentialsName: skinner-master-0-bmc-secret
  bootMACAddress: "00:50:56:xx:xx:xx"
---
apiVersion: v1
kind: Secret
metadata:
  name: skinner-master-0-bmc-secret
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

echo ""
echo -e "${BLUE}🔧 Troubleshooting OpenShift Worker Inspection Issues:${NC}"
echo ""
echo -e "${YELLOW}If workers are stuck in 'inspecting' state:${NC}"
echo ""
echo -e "${GREEN}1. Check BareMetalHost status:${NC}"
echo "   oc get baremetalhosts -n openshift-machine-api"
echo ""
echo -e "${GREEN}2. Force re-inspection by toggling online state:${NC}"
echo "   oc patch baremetalhost <worker-name> -n openshift-machine-api --type='merge' -p='{\"spec\":{\"online\":false}}'"
echo "   sleep 10"
echo "   oc patch baremetalhost <worker-name> -n openshift-machine-api --type='merge' -p='{\"spec\":{\"online\":true}}'"
echo ""
echo -e "${GREEN}3. Check detailed BMH status:${NC}"
echo "   oc describe baremetalhost <worker-name> -n openshift-machine-api"
echo ""
echo -e "${GREEN}4. Verify IPMI connectivity:${NC}"
echo "   python3 /home/lchiaret/git/ipmi-vmware/test_worker_inspection.py"
echo ""
echo -e "${GREEN}5. Monitor IPMI logs:${NC}"
echo "   sudo journalctl -u ipmi-vmware-bridge -f | grep -E '(worker|INSPECTION)'"
echo ""

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
esac
