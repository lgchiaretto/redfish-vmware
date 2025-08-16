#!/bin/bash

# Redfish VMware Server - Complete Setup Script
# This script configures the entire Redfish server with SystemD integration
# Updated: 2025-08-16 - Added Metal3/Ironic compatibility with UpdateService, TaskService, BIOS, SecureBoot, and RAID endpoints

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

echo -e "${BLUE}🚀 Redfish VMware Server - Complete Setup (Metal3 Compatible)${NC}"
echo -e "${BLUE}=============================================================${NC}"
echo ""

# Check if running as root for SystemD operations
if [[ $EUID -eq 0 ]]; then
    echo -e "${GREEN}✅ Running as root - Can configure SystemD service${NC}"
    SYSTEMD_SETUP=true
else
    echo -e "${YELLOW}⚠️ Not running as root - SystemD setup will require sudo${NC}"
    SYSTEMD_SETUP=false
fi

# Check for debug mode - Default to disabled for cleaner production logs
DEBUG_MODE=${REDFISH_DEBUG:-false}
if [[ "$DEBUG_MODE" == "true" ]]; then
    echo -e "${YELLOW}🐛 DEBUG MODE ENABLED - Enhanced Metal3/Ironic debugging${NC}"
    echo -e "${YELLOW}💡 All Redfish requests logged with detailed Metal3 failure analysis${NC}"
    echo -e "${YELLOW}🔍 Critical endpoints monitored: UpdateService, FirmwareInventory, TaskService${NC}"
    echo -e "${YELLOW}⚠️  Special BIOS firmware component logging enabled${NC}"
else
    echo -e "${BLUE}📋 PRODUCTION MODE - Clean logging (SSL/TLS noise filtered)${NC}"
    echo -e "${YELLOW}💡 Set REDFISH_DEBUG=true for detailed Metal3 failure debugging${NC}"
    echo -e "${GREEN}🛡️ Binary SSL/TLS requests filtered from logs for cleaner output${NC}"
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

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to detect OS
detect_os() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        OS=$ID
        VERSION=$VERSION_ID
    else
        print_error "Cannot detect OS"
        exit 1
    fi
    
    print_info "Detected OS: $OS $VERSION"
}

# Function to install system dependencies
install_system_dependencies() {
    print_info "Installing system dependencies..."
    
    # Check if openssl is installed
    if ! command_exists openssl; then
        print_info "Installing OpenSSL for SSL certificate generation..."
        
        if command_exists apt-get; then
            # Ubuntu/Debian
            run_sudo apt-get update
            run_sudo apt-get install -y openssl
        elif command_exists yum; then
            # RHEL/CentOS 7
            run_sudo yum install -y openssl
        elif command_exists dnf; then
            # RHEL/CentOS 8+/Fedora
            run_sudo dnf install -y openssl
        else
            print_warning "Could not determine package manager. Please install openssl manually."
        fi
        
        if command_exists openssl; then
            print_success "OpenSSL installed successfully"
        else
            print_warning "OpenSSL installation may have failed. HTTPS support will be limited."
        fi
    else
        print_success "OpenSSL already installed"
    fi
}

# Function to generate SSL certificates
generate_ssl_certificates() {
    print_info "Setting up SSL certificates..."
    
    local ssl_dir="$PROJECT_ROOT/config/ssl"
    
    # Create SSL directory if it doesn't exist
    if [[ ! -d "$ssl_dir" ]]; then
        mkdir -p "$ssl_dir"
        print_info "Created SSL directory: $ssl_dir"
    fi
    
    # Check if certificate generation script exists
    local cert_script="$ssl_dir/generate_certs.sh"
    if [[ -f "$cert_script" ]]; then
        # Check if certificates already exist
        local need_certs=false
        local vm_names=$(python3 -c "
import json
with open('$PROJECT_ROOT/config/config.json', 'r') as f:
    config = json.load(f)
for vm in config['vms']:
    print(vm['name'])
")
        
        for vm_name in $vm_names; do
            if [[ ! -f "$ssl_dir/${vm_name}.crt" ]] || [[ ! -f "$ssl_dir/${vm_name}.key" ]]; then
                need_certs=true
                break
            fi
        done
        
        if [[ "$need_certs" == "true" ]]; then
            print_info "Generating SSL certificates..."
            chmod +x "$cert_script"
            cd "$ssl_dir"
            ./"$(basename "$cert_script")"
            cd "$PROJECT_ROOT"
            print_success "SSL certificates generated successfully"
        else
            print_success "SSL certificates already exist"
        fi
    else
        print_warning "SSL certificate generation script not found. HTTPS may not work."
    fi
}

# Function to install Python dependencies
install_dependencies() {
    print_info "Installing Python dependencies..."
    
    # Check if pip3 exists
    if ! command_exists pip3; then
        print_error "pip3 not found. Please install Python 3 and pip first."
        exit 1
    fi
    
    # Install requirements
    if [[ -f "$PROJECT_ROOT/requirements.txt" ]]; then
        pip3 install -r "$PROJECT_ROOT/requirements.txt"
        print_success "Python dependencies installed"
    else
        print_warning "requirements.txt not found, skipping dependency installation"
    fi
}

# Function to configure systemd service
configure_systemd() {
    print_info "Configuring SystemD service..."
    
    local service_file="$PROJECT_ROOT/config/redfish-vmware-server.service"
    local systemd_file="/etc/systemd/system/redfish-vmware-server.service"
    
    if [[ ! -f "$service_file" ]]; then
        print_error "Service file not found: $service_file"
        return 1
    fi
    
    # Copy service file
    run_sudo cp "$service_file" "$systemd_file"
    print_success "Service file copied to $systemd_file"
    
    # Reload systemd
    run_sudo systemctl daemon-reload
    print_success "SystemD daemon reloaded"
    
    # Enable service
    run_sudo systemctl enable redfish-vmware-server
    print_success "Redfish VMware Server service enabled"
    
    return 0
}

# Function to validate configuration
validate_config() {
    print_info "Validating configuration..."
    
    local config_file="$PROJECT_ROOT/config/config.json"
    
    if [[ ! -f "$config_file" ]]; then
        print_error "Configuration file not found: $config_file"
        print_info "Please create the configuration file based on config.json.example"
        return 1
    fi
    
    # Basic JSON syntax check
    if ! python3 -m json.tool "$config_file" > /dev/null 2>&1; then
        print_error "Invalid JSON in configuration file: $config_file"
        return 1
    fi
    
    print_success "Configuration file is valid JSON"
    
    # Check for required fields
    local required_fields=("vmware" "vms")
    for field in "${required_fields[@]}"; do
        if ! python3 -c "import json; config=json.load(open('$config_file')); exit(0 if '$field' in config else 1)" 2>/dev/null; then
            print_error "Missing required field '$field' in configuration"
            return 1
        fi
    done
    
    print_success "Configuration validation passed"
    return 0
}

# Function to test VMware connectivity
test_vmware_connection() {
    print_info "Testing VMware connectivity..."
    
    # Create a simple test script
    cat > /tmp/test_vmware_redfish.py << 'EOF'
#!/usr/bin/env python3
import sys
import json
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))

try:
    from vmware_client import VMwareClient
    
    # Load config
    config_file = sys.argv[1]
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    # Test connection with first VM config
    vm_config = config['vms'][0]
    client = VMwareClient(
        vm_config['vcenter_host'],
        vm_config['vcenter_user'],
        vm_config['vcenter_password'],
        disable_ssl=vm_config.get('disable_ssl', True)
    )
    
    # List VMs to test connection
    vms = client.list_vms()
    print(f"✅ Successfully connected to VMware. Found {len(vms)} VMs.")
    
    # Test specific VM
    vm_name = vm_config['name']
    vm_info = client.get_vm_info(vm_name)
    if vm_info:
        print(f"✅ VM '{vm_name}' found. Power state: {vm_info['power_state']}")
    else:
        print(f"⚠️ VM '{vm_name}' not found in vCenter")
    
    client.disconnect()
    
except Exception as e:
    print(f"❌ VMware connection test failed: {e}")
    sys.exit(1)
EOF
    
    if python3 /tmp/test_vmware_redfish.py "$PROJECT_ROOT/config/config.json"; then
        print_success "VMware connectivity test passed"
    else
        print_error "VMware connectivity test failed"
        print_info "Please check your VMware credentials and network connectivity"
        return 1
    fi
    
    # Cleanup
    rm -f /tmp/test_vmware_redfish.py
    return 0
}

# Function to setup firewall rules
setup_firewall() {
    print_info "Setting up firewall rules..."
    
    # Extract ports from config
    local config_file="$PROJECT_ROOT/config/config.json"
    local ports=$(python3 -c "
import json
config = json.load(open('$config_file'))
ports = [str(vm.get('redfish_port', 8443)) for vm in config['vms']]
print(' '.join(ports))
" 2>/dev/null)
    
    if [[ -z "$ports" ]]; then
        print_warning "Could not extract ports from config, using default range 8443-8450"
        ports="8443 8444 8445 8446 8447 8448 8449 8450"
    fi
    
    # Check if firewalld is active
    if command_exists firewall-cmd && systemctl is-active firewalld >/dev/null 2>&1; then
        print_info "Configuring firewalld rules..."
        for port in $ports; do
            if run_sudo firewall-cmd --permanent --add-port="${port}/tcp" 2>/dev/null; then
                print_success "Added firewall rule for port $port/tcp"
            else
                print_warning "Failed to add firewall rule for port $port/tcp"
            fi
        done
        run_sudo firewall-cmd --reload 2>/dev/null || true
        
    # Check if ufw is active
    elif command_exists ufw && ufw status | grep -q "Status: active"; then
        print_info "Configuring ufw rules..."
        for port in $ports; do
            if run_sudo ufw allow "${port}/tcp" 2>/dev/null; then
                print_success "Added ufw rule for port $port/tcp"
            else
                print_warning "Failed to add ufw rule for port $port/tcp"
            fi
        done
        
    # Check if iptables exists
    elif command_exists iptables; then
        print_info "Configuring iptables rules..."
        for port in $ports; do
            if run_sudo iptables -I INPUT -p tcp --dport "$port" -j ACCEPT 2>/dev/null; then
                print_success "Added iptables rule for port $port/tcp"
            else
                print_warning "Failed to add iptables rule for port $port/tcp"
            fi
        done
        
        # Try to save iptables rules
        if command_exists iptables-save; then
            run_sudo iptables-save > /etc/iptables/rules.v4 2>/dev/null || true
        fi
        
    else
        print_warning "No supported firewall found. Please manually open ports: $ports"
    fi
}

# Function to start and test service
start_and_test_service() {
    print_info "Starting Redfish VMware Server service..."
    
    # Start the service
    if run_sudo systemctl start redfish-vmware-server; then
        print_success "Service started successfully"
    else
        print_error "Failed to start service"
        print_info "Check logs with: sudo journalctl -u redfish-vmware-server -f"
        return 1
    fi
    
    # Wait a moment for service to initialize
    sleep 3
    
    # Check service status
    if run_sudo systemctl is-active redfish-vmware-server >/dev/null 2>&1; then
        print_success "Service is running"
    else
        print_error "Service is not running"
        print_info "Check logs with: sudo journalctl -u redfish-vmware-server -f"
        return 1
    fi
    
    # Test basic connectivity
    print_info "Testing Redfish endpoints..."
    
    local config_file="$PROJECT_ROOT/config/config.json"
    local first_port=$(python3 -c "
import json
config = json.load(open('$config_file'))
if config['vms']:
    print(config['vms'][0].get('redfish_port', 8443))
else:
    print(8443)
" 2>/dev/null)
    
    # Test service root endpoint
    if command_exists curl; then
        local test_url="http://localhost:${first_port}/redfish/v1/"
        if curl -s -o /dev/null -w "%{http_code}" "$test_url" | grep -q "200"; then
            print_success "Redfish service root endpoint responding"
        else
            print_warning "Redfish service root endpoint not responding on port $first_port"
        fi
    else
        print_warning "curl not available for endpoint testing"
    fi
    
    return 0
}

# Function to show usage examples
show_usage_examples() {
    echo ""
    echo -e "${BLUE}📖 Usage Examples${NC}"
    echo -e "${BLUE}=================${NC}"
    echo ""
    
    local config_file="$PROJECT_ROOT/config/config.json"
    local vm_info=$(python3 -c "
import json
config = json.load(open('$config_file'))
if config['vms']:
    vm = config['vms'][0]
    print(f\"{vm['name']}:{vm.get('redfish_port', 8443)}\")
else:
    print('vm-name:8443')
" 2>/dev/null)
    
    local vm_name=$(echo "$vm_info" | cut -d: -f1)
    local port=$(echo "$vm_info" | cut -d: -f2)
    
    echo -e "${YELLOW}🔧 Basic Redfish Operations (HTTPS):${NC}"
    echo ""
    echo "# Get service root"
    echo "curl -k https://localhost:${port}/redfish/v1/"
    echo ""
    echo "# Get systems collection"
    echo "curl -k https://localhost:${port}/redfish/v1/Systems"
    echo ""
    echo "# Get specific system info (requires authentication)"
    echo "curl -k -u admin:password https://localhost:${port}/redfish/v1/Systems/${vm_name}"
    echo ""
    echo "# Power on system"
    echo "curl -k -u admin:password -X POST -H \"Content-Type: application/json\" \\"
    echo "     -d '{\"ResetType\": \"On\"}' \\"
    echo "     https://localhost:${port}/redfish/v1/Systems/${vm_name}/Actions/ComputerSystem.Reset"
    echo ""
    echo "# Power off system"
    echo "curl -k -u admin:password -X POST -H \"Content-Type: application/json\" \\"
    echo "     -d '{\"ResetType\": \"ForceOff\"}' \\"
    echo "     https://localhost:${port}/redfish/v1/Systems/${vm_name}/Actions/ComputerSystem.Reset"
    echo ""
    echo "# Graceful shutdown"
    echo "curl -k -u admin:password -X POST -H \"Content-Type: application/json\" \\"
    echo "     -d '{\"ResetType\": \"GracefulShutdown\"}' \\"
    echo "     https://localhost:${port}/redfish/v1/Systems/${vm_name}/Actions/ComputerSystem.Reset"
    echo ""
    echo -e "${YELLOW}� Metal3/Ironic Integration Endpoints (HTTPS):${NC}"
    echo ""
    echo "# UpdateService (for firmware updates)"
    echo "curl -k https://localhost:${port}/redfish/v1/UpdateService"
    echo ""
    echo "# Software Inventory"
    echo "curl -k https://localhost:${port}/redfish/v1/UpdateService/SoftwareInventory"
    echo ""
    echo "# TaskService (for async operations)"
    echo "curl -k https://localhost:${port}/redfish/v1/TaskService"
    echo ""
    echo "# BIOS settings"
    echo "curl -k -u admin:password https://localhost:${port}/redfish/v1/Systems/${vm_name}/Bios"
    echo ""
    echo "# SecureBoot configuration"
    echo "curl -k -u admin:password https://localhost:${port}/redfish/v1/Systems/${vm_name}/SecureBoot"
    echo ""
    echo "# Storage Controllers (RAID support)"
    echo "curl -k -u admin:password https://localhost:${port}/redfish/v1/Systems/${vm_name}/Storage/1/StorageControllers/1"
    echo ""
    echo -e "${YELLOW}�🔒 Authentication & SSL:${NC}"
    echo "   Username: admin"
    echo "   Password: password"
    echo "   Note: Use -k flag to ignore self-signed certificates"
    echo ""
    
    echo -e "${YELLOW}🔧 Service Management:${NC}"
    echo ""
    echo "# Check service status"
    echo "sudo systemctl status redfish-vmware-server"
    echo ""
    echo "# View service logs"
    echo "sudo journalctl -u redfish-vmware-server -f"
    echo ""
    echo "# Restart service"
    echo "sudo systemctl restart redfish-vmware-server"
    echo ""
    echo "# Stop service"
    echo "sudo systemctl stop redfish-vmware-server"
    echo ""
    
    echo -e "${YELLOW}🔧 Debug Mode:${NC}"
    echo ""
    echo "# Enable debug logging"
    echo "export REDFISH_DEBUG=true"
    echo "sudo systemctl restart redfish-vmware-server"
    echo ""
}

# Main setup function
main() {
    echo -e "${BLUE}🔍 Starting Redfish VMware Server setup...${NC}"
    echo ""
    
    # Detect OS
    detect_os
    
    # Validate configuration
    if ! validate_config; then
        print_error "Configuration validation failed"
        exit 1
    fi
    
    # Install system dependencies
    install_system_dependencies
    
    # Install dependencies
    install_dependencies
    
    # Generate SSL certificates
    generate_ssl_certificates
    
    # Test VMware connectivity
    if ! test_vmware_connection; then
        print_error "VMware connectivity test failed"
        exit 1
    fi
    
    # Configure SystemD service
    if ! configure_systemd; then
        print_error "SystemD configuration failed"
        exit 1
    fi
    
    # Setup firewall
    setup_firewall
    
    # Start and test service
    if ! start_and_test_service; then
        print_error "Service startup failed"
        exit 1
    fi
    
    # Show success message
    echo ""
    echo -e "${GREEN}🎉 Setup completed successfully!${NC}"
    echo ""
    print_success "Redfish VMware Server is now running"
    print_info "Service name: redfish-vmware-server"
    
    # Show usage examples
    show_usage_examples
    
    echo ""
    echo -e "${GREEN}✅ All done! Your Redfish VMware Server is ready to use.${NC}"
}

# Handle command line arguments
case "${1:-}" in
    --help|-h)
        echo "Redfish VMware Server Setup Script"
        echo ""
        echo "Usage: $0 [options]"
        echo ""
        echo "Options:"
        echo "  --help, -h          Show this help message"
        echo "  --config-only       Only configure SystemD, don't start service"
        echo "  --test-only         Only test VMware connectivity"
        echo ""
        echo "Environment variables:"
        echo "  REDFISH_DEBUG=true  Enable debug logging"
        echo ""
        exit 0
        ;;
    --config-only)
        print_info "Configuration-only mode"
        validate_config
        configure_systemd
        print_success "Configuration completed"
        ;;
    --test-only)
        print_info "Test-only mode"
        validate_config
        test_vmware_connection
        print_success "Tests completed"
        ;;
    "")
        main
        ;;
    *)
        print_error "Unknown option: $1"
        print_info "Use --help for usage information"
        exit 1
        ;;
esac
