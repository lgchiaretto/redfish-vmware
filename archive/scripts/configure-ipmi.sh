#!/bin/bash

# IPMI VMware Bridge Configuration Script
# This script installs and configures the IPMI VMware Bridge service

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SERVICE_NAME="ipmi-vmware-bridge"
INSTALL_DIR="/opt/${SERVICE_NAME}"
CONFIG_DIR="/etc/${SERVICE_NAME}"
LOG_DIR="/var/log"
SERVICE_USER="ipmi"
SERVICE_GROUP="ipmi"

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        exit 1
    fi
}

check_dependencies() {
    log_step "Checking system dependencies..."
    
    # Check for required commands
    local missing_deps=()
    
    for cmd in python3 pip3 systemctl; do
        if ! command -v $cmd &> /dev/null; then
            missing_deps+=("$cmd")
        fi
    done
    
    if [ ${#missing_deps[@]} -ne 0 ]; then
        log_error "Missing dependencies: ${missing_deps[*]}"
        log_info "Please install the missing dependencies and try again"
        exit 1
    fi
    
    log_info "All dependencies found"
}

create_user() {
    log_step "Creating service user and group..."
    
    # Create group if it doesn't exist
    if ! getent group $SERVICE_GROUP > /dev/null 2>&1; then
        groupadd --system $SERVICE_GROUP
        log_info "Created group: $SERVICE_GROUP"
    else
        log_info "Group $SERVICE_GROUP already exists"
    fi
    
    # Create user if it doesn't exist
    if ! getent passwd $SERVICE_USER > /dev/null 2>&1; then
        useradd --system --gid $SERVICE_GROUP --home-dir $INSTALL_DIR \
                --shell /bin/false --comment "IPMI VMware Bridge Service" $SERVICE_USER
        log_info "Created user: $SERVICE_USER"
    else
        log_info "User $SERVICE_USER already exists"
    fi
}

create_directories() {
    log_step "Creating directories..."
    
    # Create installation directory
    mkdir -p $INSTALL_DIR
    log_info "Created directory: $INSTALL_DIR"
    
    # Create configuration directory
    mkdir -p $CONFIG_DIR
    log_info "Created directory: $CONFIG_DIR"
    
    # Set permissions
    chown -R $SERVICE_USER:$SERVICE_GROUP $INSTALL_DIR
    chown -R $SERVICE_USER:$SERVICE_GROUP $CONFIG_DIR
    chmod 755 $INSTALL_DIR
    chmod 750 $CONFIG_DIR
}

install_python_packages() {
    log_step "Installing Python packages..."
    
    # Upgrade pip first
    pip3 install --upgrade pip
    
    # Install requirements
    if [ -f "requirements.txt" ]; then
        pip3 install -r requirements.txt
        log_info "Installed Python packages from requirements.txt"
    else
        log_warn "requirements.txt not found, installing packages individually"
        pip3 install pyvmomi pyghmi python-daemon psutil pyyaml
    fi
}

copy_files() {
    log_step "Copying application files..."
    
    # Copy Python scripts
    local python_files=(
        "ipmi_vmware_bridge.py"
        "vmware_client.py"
    )
    
    for file in "${python_files[@]}"; do
        if [ -f "$file" ]; then
            cp "$file" "$INSTALL_DIR/"
            chmod 755 "$INSTALL_DIR/$file"
            chown $SERVICE_USER:$SERVICE_GROUP "$INSTALL_DIR/$file"
            log_info "Copied: $file"
        else
            log_warn "File not found: $file"
        fi
    done
    
    # Copy configuration file
    if [ -f "config.json" ]; then
        cp "config.json" "$CONFIG_DIR/"
        chmod 640 "$CONFIG_DIR/config.json"
        chown $SERVICE_USER:$SERVICE_GROUP "$CONFIG_DIR/config.json"
        log_info "Copied: config.json"
    else
        log_warn "config.json not found"
    fi
    
    # Copy systemd service file
    if [ -f "${SERVICE_NAME}.service" ]; then
        cp "${SERVICE_NAME}.service" "/etc/systemd/system/"
        chmod 644 "/etc/systemd/system/${SERVICE_NAME}.service"
        log_info "Copied systemd service file"
    else
        log_warn "Service file not found: ${SERVICE_NAME}.service"
    fi
}

configure_systemd() {
    log_step "Configuring systemd service..."
    
    # Reload systemd
    systemctl daemon-reload
    log_info "Reloaded systemd daemon"
    
    # Enable service
    systemctl enable $SERVICE_NAME
    log_info "Enabled $SERVICE_NAME service"
}

configure_firewall() {
    log_step "Configuring firewall..."
    
    # Check if firewalld is running
    if systemctl is-active --quiet firewalld; then
        log_info "Configuring firewalld..."
        
        # Open IPMI ports (typically 623-630)
        for port in {623..630}; do
            firewall-cmd --permanent --add-port=${port}/udp
        done
        
        firewall-cmd --reload
        log_info "Firewall configured for IPMI ports 623-630/udp"
    elif systemctl is-active --quiet ufw; then
        log_info "Configuring ufw..."
        
        # Open IPMI ports
        for port in {623..630}; do
            ufw allow ${port}/udp
        done
        
        log_info "UFW configured for IPMI ports 623-630/udp"
    else
        log_warn "No supported firewall found (firewalld/ufw). Please manually open ports 623-630/udp"
    fi
}

test_installation() {
    log_step "Testing installation..."
    
    # Check if service file is valid
    if systemctl status $SERVICE_NAME --no-pager -l > /dev/null 2>&1; then
        log_info "Service configuration is valid"
    else
        log_warn "Service configuration may have issues"
    fi
    
    # Check if Python imports work
    if python3 -c "import sys; sys.path.insert(0, '$INSTALL_DIR'); import vmware_client" 2>/dev/null; then
        log_info "Python modules can be imported successfully"
    else
        log_warn "Python module import test failed - check dependencies"
    fi
}

show_status() {
    log_step "Installation completed!"
    echo
    log_info "Service: $SERVICE_NAME"
    log_info "Install directory: $INSTALL_DIR"
    log_info "Configuration: $CONFIG_DIR/config.json"
    log_info "Logs: /var/log/ipmi-vmware-bridge.log"
    echo
    log_info "Next steps:"
    echo "  1. Edit the configuration file: $CONFIG_DIR/config.json"
    echo "  2. Update VM names and IPMI settings"
    echo "  3. Start the service: systemctl start $SERVICE_NAME"
    echo "  4. Check status: systemctl status $SERVICE_NAME"
    echo "  5. View logs: journalctl -u $SERVICE_NAME -f"
    echo
}

# Command line options
FORCE_INSTALL=false
SKIP_FIREWALL=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --force)
            FORCE_INSTALL=true
            shift
            ;;
        --skip-firewall)
            SKIP_FIREWALL=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo
            echo "Options:"
            echo "  --force           Force installation even if service exists"
            echo "  --skip-firewall   Skip firewall configuration"
            echo "  --help, -h        Show this help message"
            echo
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Main execution
main() {
    log_info "Starting IPMI VMware Bridge installation..."
    echo
    
    check_root
    check_dependencies
    
    # Check if service already exists
    if systemctl list-unit-files | grep -q "$SERVICE_NAME" && [ "$FORCE_INSTALL" = false ]; then
        log_warn "Service $SERVICE_NAME already exists. Use --force to reinstall."
        exit 1
    fi
    
    # Stop service if running
    if systemctl is-active --quiet $SERVICE_NAME; then
        log_info "Stopping existing service..."
        systemctl stop $SERVICE_NAME
    fi
    
    create_user
    create_directories
    install_python_packages
    copy_files
    configure_systemd
    
    if [ "$SKIP_FIREWALL" = false ]; then
        configure_firewall
    fi
    
    test_installation
    show_status
}

# Run if called directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
