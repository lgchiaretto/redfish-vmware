#!/bin/bash

# IPMI VMware Bridge - Installation and Setup Script
# Organizes the project and sets up the service

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

echo "🚀 IPMI VMware Bridge - Setup Script"
echo "📁 Project root: $PROJECT_ROOT"

# Function to print colored output
print_status() {
    echo -e "\033[1;32m✅ $1\033[0m"
}

print_info() {
    echo -e "\033[1;34mℹ️  $1\033[0m"
}

print_warning() {
    echo -e "\033[1;33m⚠️  $1\033[0m"
}

print_error() {
    echo -e "\033[1;31m❌ $1\033[0m"
}

# Check if running as root for systemd operations
check_root() {
    if [[ $EUID -eq 0 ]]; then
        print_warning "Running as root - systemd service installation will be available"
        return 0
    else
        print_info "Not running as root - systemd service installation will be skipped"
        return 1
    fi
}

# Install Python dependencies
install_dependencies() {
    print_info "Installing Python dependencies..."
    
    if [[ -f "$PROJECT_ROOT/requirements.txt" ]]; then
        pip3 install -r "$PROJECT_ROOT/requirements.txt"
        print_status "Python dependencies installed"
    else
        print_warning "requirements.txt not found, installing basic dependencies"
        pip3 install pyghmi pyVmomi
    fi
}

# Setup configuration
setup_config() {
    print_info "Setting up configuration..."
    
    if [[ ! -f "$PROJECT_ROOT/config/config.json" ]]; then
        if [[ -f "$PROJECT_ROOT/config/config_fixed.json" ]]; then
            cp "$PROJECT_ROOT/config/config_fixed.json" "$PROJECT_ROOT/config/config.json"
            print_status "Copied config_fixed.json to config.json"
        else
            print_error "No configuration file found!"
            print_info "Please create config/config.json with your VMware and VM settings"
            return 1
        fi
    else
        print_status "Configuration file already exists"
    fi
}

# Install systemd service
install_service() {
    local is_root=$1
    
    if [[ $is_root -eq 0 ]]; then
        print_info "Installing systemd service..."
        
        # Copy service file
        cp "$PROJECT_ROOT/config/ipmi-vmware-bridge.service" /etc/systemd/system/
        
        # Reload systemd
        systemctl daemon-reload
        
        # Enable service
        systemctl enable ipmi-vmware-bridge
        
        print_status "Systemd service installed and enabled"
        print_info "Use 'sudo systemctl start ipmi-vmware-bridge' to start the service"
    else
        print_info "Skipping systemd service installation (not root)"
    fi
}

# Create log directory
setup_logging() {
    print_info "Setting up logging..."
    
    # Create log directory if it doesn't exist
    if [[ ! -d "/var/log" ]]; then
        print_warning "/var/log directory does not exist"
    else
        # Make sure we can write to log file
        touch /var/log/ipmi-vmware-bridge.log 2>/dev/null || print_warning "Cannot create log file in /var/log (will use local logging)"
        print_status "Logging configured"
    fi
}

# Test configuration
test_config() {
    print_info "Testing configuration..."
    
    cd "$PROJECT_ROOT"
    
    # Test Python imports
    python3 -c "
import sys
sys.path.insert(0, 'src')
try:
    from ipmi_bridge import load_config
    config = load_config()
    if config:
        print('✅ Configuration loaded successfully')
        vm_count = len(config.get('vms', []))
        print(f'✅ Found {vm_count} VMs configured')
    else:
        print('❌ Configuration loading failed')
        sys.exit(1)
except ImportError as e:
    print(f'❌ Import error: {e}')
    sys.exit(1)
except Exception as e:
    print(f'❌ Error: {e}')
    sys.exit(1)
" || {
        print_error "Configuration test failed"
        return 1
    }
    
    print_status "Configuration test passed"
}

# Main installation
main() {
    echo
    print_info "Starting IPMI VMware Bridge setup..."
    echo
    
    # Check if we're root
    local is_root
    check_root && is_root=0 || is_root=1
    
    # Install dependencies
    install_dependencies
    echo
    
    # Setup configuration
    setup_config
    echo
    
    # Setup logging
    setup_logging
    echo
    
    # Test configuration
    test_config
    echo
    
    # Install systemd service if root
    install_service $is_root
    echo
    
    print_status "Setup completed successfully!"
    echo
    print_info "Next steps:"
    print_info "1. Edit config/config.json with your VMware credentials"
    print_info "2. Run './ipmi-bridge' to start in development mode"
    print_info "3. Or use 'sudo systemctl start ipmi-vmware-bridge' for service mode"
    print_info "4. Monitor logs with 'tail -f /var/log/ipmi-vmware-bridge.log'"
    echo
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
