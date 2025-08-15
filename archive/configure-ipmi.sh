#!/bin/bash
# IPMI-VMware Bridge Configuration Script
# This script sets up the IPMI-VMware Bridge as a systemd service

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SERVICE_NAME="ipmi-vmware-bridge"
INSTALL_DIR="/opt/ipmi-vmware"
CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYSTEMD_SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

# Install Python dependencies system-wide
install_system_dependencies() {
    print_status "Installing system dependencies..."
    
    # Detect package manager and OS
    if command -v apt-get &> /dev/null; then
        # Debian/Ubuntu
        print_status "Detected Debian/Ubuntu system"
        apt-get update
        apt-get install -y python3 python3-pip python3-venv git
    elif command -v dnf &> /dev/null; then
        # Fedora/RHEL 8+
        print_status "Detected Fedora/RHEL system"
        dnf update -y
        # Note: python3-venv is not needed in Fedora, venv is included in python3
        dnf install -y python3 python3-pip git
    elif command -v yum &> /dev/null; then
        # CentOS/RHEL 7
        print_status "Detected CentOS/RHEL 7 system"
        yum update -y
        yum install -y python3 python3-pip git
    elif command -v zypper &> /dev/null; then
        # openSUSE
        print_status "Detected openSUSE system"
        zypper refresh
        zypper install -y python3 python3-pip git
    else
        print_error "Unsupported package manager. Please install python3, python3-pip, and git manually."
        exit 1
    fi
    
    print_success "System dependencies installed"
}

# Copy files to installation directory
install_application() {
    print_status "Installing IPMI-VMware Bridge to $INSTALL_DIR"
    
    # Create installation directory
    mkdir -p "$INSTALL_DIR"
    
    # Copy all files
    cp -r "$CURRENT_DIR"/* "$INSTALL_DIR/"
    
    # Create Python virtual environment
    print_status "Creating Python virtual environment..."
    python3 -m venv "$INSTALL_DIR/.venv"
    
    # Install Python dependencies
    print_status "Installing Python dependencies..."
    "$INSTALL_DIR/.venv/bin/pip" install --upgrade pip
    "$INSTALL_DIR/.venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"
    
    # Set proper permissions (root ownership for port 623 access)
    chown -R root:root "$INSTALL_DIR"
    chmod +x "$INSTALL_DIR/ipmi-bridge.sh"
    chmod +x "$INSTALL_DIR/configure-ipmi.sh"
    
    print_success "Application installed to $INSTALL_DIR"
}

# Create systemd service file
create_systemd_service() {
    print_status "Creating systemd service file..."
    
    cat > "$SYSTEMD_SERVICE_FILE" << EOF
[Unit]
Description=IPMI-VMware Bridge
Documentation=file://$INSTALL_DIR/README.md
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=$INSTALL_DIR
Environment=PYTHONPATH=$INSTALL_DIR
ExecStart=$INSTALL_DIR/.venv/bin/python $INSTALL_DIR/main.py --daemon
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=5
TimeoutStopSec=30
KillMode=mixed

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$SERVICE_NAME

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$INSTALL_DIR
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true

# Network - Allow binding to privileged ports
PrivateNetwork=false
AmbientCapabilities=CAP_NET_BIND_SERVICE

[Install]
WantedBy=multi-user.target
EOF

    print_success "Systemd service file created: $SYSTEMD_SERVICE_FILE"
}

# Create configuration template
create_config_template() {
    print_status "Creating configuration template..."
    
    cat > "$INSTALL_DIR/config.ini.template" << EOF
[vmware]
vcenter_host = your-vcenter.domain.com
username = administrator@vsphere.local
password = your-password
port = 443
ignore_ssl = true

[ipmi]
listen_address = 0.0.0.0
listen_port = 623
# Port 623 is the standard IPMI port and requires root privileges
# Use port > 1024 if running as non-root user

[logging]
level = INFO
file = $INSTALL_DIR/ipmi_vmware.log

[vm_mapping]
# Map IPMI client IP addresses to VMware VM names
# Format: client_ip = vm_name
# Example:
# 192.168.1.100 = production-server-1
# 192.168.1.101 = test-server-2
# 10.0.0.50 = development-vm
127.0.0.1 = test-vm
EOF

    # If config.ini doesn't exist, copy template
    if [[ ! -f "$INSTALL_DIR/config.ini" ]]; then
        cp "$INSTALL_DIR/config.ini.template" "$INSTALL_DIR/config.ini"
        print_warning "Default config created. Please edit $INSTALL_DIR/config.ini"
    fi
    
    chown "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR/config.ini"*
    chmod 600 "$INSTALL_DIR/config.ini"*
    
    print_success "Configuration template created"
}

# Create management script
create_management_script() {
    print_status "Creating management script..."
    
    cat > "/usr/local/bin/ipmi-bridge" << 'EOF'
#!/bin/bash
# IPMI-VMware Bridge Management Script

SERVICE_NAME="ipmi-vmware-bridge"
INSTALL_DIR="/opt/ipmi-vmware"

case "$1" in
    start)
        echo "Starting IPMI-VMware Bridge..."
        systemctl start "$SERVICE_NAME"
        ;;
    stop)
        echo "Stopping IPMI-VMware Bridge..."
        systemctl stop "$SERVICE_NAME"
        ;;
    restart)
        echo "Restarting IPMI-VMware Bridge..."
        systemctl restart "$SERVICE_NAME"
        ;;
    status)
        systemctl status "$SERVICE_NAME"
        ;;
    enable)
        echo "Enabling IPMI-VMware Bridge to start at boot..."
        systemctl enable "$SERVICE_NAME"
        ;;
    disable)
        echo "Disabling IPMI-VMware Bridge from starting at boot..."
        systemctl disable "$SERVICE_NAME"
        ;;
    logs)
        journalctl -u "$SERVICE_NAME" -f
        ;;
    test)
        echo "Testing VMware connection..."
        sudo -u ipmi-bridge "$INSTALL_DIR/.venv/bin/python" "$INSTALL_DIR/main.py" --test-vmware
        ;;
    config)
        echo "Opening configuration file..."
        if command -v nano >/dev/null; then
            sudo nano "$INSTALL_DIR/config.ini"
        elif command -v vi >/dev/null; then
            sudo vi "$INSTALL_DIR/config.ini"
        else
            echo "Please edit $INSTALL_DIR/config.ini manually"
        fi
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|enable|disable|logs|test|config}"
        echo ""
        echo "Commands:"
        echo "  start    - Start the service"
        echo "  stop     - Stop the service"
        echo "  restart  - Restart the service"
        echo "  status   - Show service status"
        echo "  enable   - Enable service to start at boot"
        echo "  disable  - Disable service from starting at boot"
        echo "  logs     - Show live logs"
        echo "  test     - Test VMware connection"
        echo "  config   - Edit configuration"
        exit 1
        ;;
esac
EOF

    chmod +x "/usr/local/bin/ipmi-bridge"
    print_success "Management script created: /usr/local/bin/ipmi-bridge"
}

# Configure firewall
configure_firewall() {
    print_status "Configuring firewall..."
    
    if command -v ufw >/dev/null; then
        ufw allow 623/udp comment "IPMI-VMware Bridge"
        print_success "UFW firewall rule added for port 623/udp"
    elif command -v firewall-cmd >/dev/null; then
        firewall-cmd --permanent --add-port=623/udp
        firewall-cmd --reload
        print_success "Firewalld rule added for port 623/udp"
    else
        print_warning "No recognized firewall found. Please manually open port 623/udp"
    fi
}

# Test installation
test_installation() {
    print_status "Testing installation..."
    
    # Reload systemd
    systemctl daemon-reload
    
    # Test configuration syntax
    if "$INSTALL_DIR/.venv/bin/python" -c "import configparser; c = configparser.ConfigParser(); c.read('$INSTALL_DIR/config.ini')"; then
        print_success "Configuration file syntax is valid"
    else
        print_error "Configuration file has syntax errors"
        return 1
    fi
    
    # Test Python imports
    if "$INSTALL_DIR/.venv/bin/python" -c "import sys; sys.path.insert(0, '$INSTALL_DIR'); import main, vmware_client, ipmi_server"; then
        print_success "Python modules import successfully"
    else
        print_error "Python module import failed"
        return 1
    fi
    
    print_success "Installation test completed"
}

# Main installation process
main() {
    echo "=============================================="
    echo "   IPMI-VMware Bridge Installation Script    "
    echo "=============================================="
    echo ""
    
    check_root
    
    print_status "Starting installation process..."
    
    # Installation steps
    install_system_dependencies
    install_application
    create_systemd_service
    create_config_template
    create_management_script
    configure_firewall
    test_installation
    
    echo ""
    echo "=============================================="
    print_success "Installation completed successfully!"
    echo "=============================================="
    echo ""
    echo "Next steps:"
    echo "1. Edit configuration: ipmi-bridge config"
    echo "2. Test VMware connection: ipmi-bridge test"
    echo "3. Enable service: ipmi-bridge enable"
    echo "4. Start service: ipmi-bridge start"
    echo "5. Check status: ipmi-bridge status"
    echo "6. View logs: ipmi-bridge logs"
    echo ""
    echo "Configuration file: $INSTALL_DIR/config.ini"
    echo "Service management: ipmi-bridge <command>"
    echo "Manual service control: systemctl <action> $SERVICE_NAME"
    echo ""
}

# Handle command line arguments
case "${1:-install}" in
    install)
        main
        ;;
    uninstall)
        print_status "Uninstalling IPMI-VMware Bridge..."
        systemctl stop "$SERVICE_NAME" 2>/dev/null || true
        systemctl disable "$SERVICE_NAME" 2>/dev/null || true
        rm -f "$SYSTEMD_SERVICE_FILE"
        rm -f "/usr/local/bin/ipmi-bridge"
        rm -rf "$INSTALL_DIR"
        systemctl daemon-reload
        print_success "IPMI-VMware Bridge uninstalled"
        ;;
    *)
        echo "Usage: $0 {install|uninstall}"
        exit 1
        ;;
esac
