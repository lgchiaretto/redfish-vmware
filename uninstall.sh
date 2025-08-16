#!/bin/bash

# Redfish VMware Server - Uninstall Script
# This script completely removes the Redfish VMware Server

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

echo -e "${RED}🗑️  Redfish VMware Server - Uninstall${NC}"
echo -e "${RED}====================================${NC}"
echo ""

# Check if running as root for SystemD operations
if [[ $EUID -eq 0 ]]; then
    echo -e "${GREEN}✅ Running as root - Can remove SystemD service${NC}"
    SYSTEMD_SETUP=true
else
    echo -e "${YELLOW}⚠️ Not running as root - SystemD removal will require sudo${NC}"
    SYSTEMD_SETUP=false
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

# Function to confirm uninstall
confirm_uninstall() {
    echo -e "${YELLOW}⚠️ WARNING: This will completely remove the Redfish VMware Server${NC}"
    echo ""
    echo "This will:"
    echo "  - Stop the redfish-vmware-server service"
    echo "  - Disable the service"
    echo "  - Remove the systemd service file"
    echo "  - Remove firewall rules"
    echo "  - Clean up log files"
    echo ""
    
    read -p "Are you sure you want to continue? (yes/no): " confirm
    if [[ "$confirm" != "yes" ]]; then
        print_info "Uninstall cancelled"
        exit 0
    fi
}

# Function to stop and remove systemd service
remove_systemd_service() {
    print_info "Removing SystemD service..."
    
    local service_name="redfish-vmware-server"
    local systemd_file="/etc/systemd/system/${service_name}.service"
    
    # Stop service if running
    if systemctl is-active "$service_name" >/dev/null 2>&1; then
        print_info "Stopping service: $service_name"
        run_sudo systemctl stop "$service_name"
        print_success "Service stopped"
    else
        print_info "Service is not running"
    fi
    
    # Disable service if enabled
    if systemctl is-enabled "$service_name" >/dev/null 2>&1; then
        print_info "Disabling service: $service_name"
        run_sudo systemctl disable "$service_name"
        print_success "Service disabled"
    else
        print_info "Service is not enabled"
    fi
    
    # Remove service file
    if [[ -f "$systemd_file" ]]; then
        print_info "Removing service file: $systemd_file"
        run_sudo rm -f "$systemd_file"
        print_success "Service file removed"
    else
        print_info "Service file does not exist"
    fi
    
    # Reload systemd
    run_sudo systemctl daemon-reload
    print_success "SystemD daemon reloaded"
    
    return 0
}

# Function to remove firewall rules
remove_firewall_rules() {
    print_info "Removing firewall rules..."
    
    # Extract ports from config
    local config_file="$PROJECT_ROOT/config/config.json"
    local ports=""
    
    if [[ -f "$config_file" ]]; then
        ports=$(python3 -c "
import json
try:
    config = json.load(open('$config_file'))
    ports = [str(vm.get('redfish_port', 8443)) for vm in config['vms']]
    print(' '.join(ports))
except:
    print('8443 8444')
" 2>/dev/null)
    else
        ports="8443 8444"
    fi
    
    if [[ -z "$ports" ]]; then
        ports="8443 8444"
    fi
    
    print_info "Removing firewall rules for ports: $ports"
    
    # Check if firewalld is active
    if command_exists firewall-cmd && systemctl is-active firewalld >/dev/null 2>&1; then
        print_info "Removing firewalld rules..."
        for port in $ports; do
            if run_sudo firewall-cmd --permanent --remove-port="${port}/tcp" 2>/dev/null; then
                print_success "Removed firewall rule for port $port/tcp"
            else
                print_warning "Failed to remove firewall rule for port $port/tcp (may not exist)"
            fi
        done
        run_sudo firewall-cmd --reload 2>/dev/null || true
        
    # Check if ufw is active
    elif command_exists ufw && ufw status | grep -q "Status: active"; then
        print_info "Removing ufw rules..."
        for port in $ports; do
            if run_sudo ufw delete allow "${port}/tcp" 2>/dev/null; then
                print_success "Removed ufw rule for port $port/tcp"
            else
                print_warning "Failed to remove ufw rule for port $port/tcp (may not exist)"
            fi
        done
        
    # Check if iptables exists
    elif command_exists iptables; then
        print_info "Removing iptables rules..."
        for port in $ports; do
            if run_sudo iptables -D INPUT -p tcp --dport "$port" -j ACCEPT 2>/dev/null; then
                print_success "Removed iptables rule for port $port/tcp"
            else
                print_warning "Failed to remove iptables rule for port $port/tcp (may not exist)"
            fi
        done
        
        # Try to save iptables rules
        if command_exists iptables-save; then
            run_sudo iptables-save > /etc/iptables/rules.v4 2>/dev/null || true
        fi
        
    else
        print_warning "No supported firewall found"
    fi
}

# Function to clean up log files
cleanup_logs() {
    print_info "Cleaning up log files..."
    
    local log_files=(
        "/var/log/redfish-vmware-server.log"
        "/home/lchiaret/redfish-vmware-server.log"
        "./redfish-vmware-server.log"
    )
    
    for log_file in "${log_files[@]}"; do
        if [[ -f "$log_file" ]]; then
            if run_sudo rm -f "$log_file" 2>/dev/null; then
                print_success "Removed log file: $log_file"
            else
                print_warning "Failed to remove log file: $log_file"
            fi
        fi
    done
    
    # Clean up journal logs
    if command_exists journalctl; then
        print_info "Cleaning up systemd journal logs for redfish-vmware-server"
        run_sudo journalctl --vacuum-time=1s --unit=redfish-vmware-server 2>/dev/null || true
    fi
}

# Function to remove Python cache files
cleanup_python_cache() {
    print_info "Cleaning up Python cache files..."
    
    if [[ -d "$PROJECT_ROOT/src/__pycache__" ]]; then
        rm -rf "$PROJECT_ROOT/src/__pycache__"
        print_success "Removed Python cache files"
    fi
    
    # Remove any .pyc files
    find "$PROJECT_ROOT" -name "*.pyc" -delete 2>/dev/null || true
}

# Function to show cleanup status
show_cleanup_status() {
    echo ""
    echo -e "${BLUE}📊 Cleanup Status${NC}"
    echo -e "${BLUE}=================${NC}"
    
    # Check if service still exists
    if systemctl list-unit-files | grep -q "redfish-vmware-server"; then
        print_warning "SystemD service still exists"
    else
        print_success "SystemD service removed"
    fi
    
    # Check if service file exists
    if [[ -f "/etc/systemd/system/redfish-vmware-server.service" ]]; then
        print_warning "Service file still exists"
    else
        print_success "Service file removed"
    fi
    
    # Check for running processes
    local running_processes
    running_processes=$(pgrep -f "redfish_server.py" | wc -l)
    if [[ "$running_processes" -gt 0 ]]; then
        print_warning "$running_processes Redfish server processes still running"
        print_info "You may need to manually kill them: sudo pkill -f redfish_server.py"
    else
        print_success "No Redfish server processes running"
    fi
    
    # Check for listening ports
    local listening_ports=""
    if command_exists netstat; then
        listening_ports=$(netstat -tlnp 2>/dev/null | grep ":844" | wc -l)
    elif command_exists ss; then
        listening_ports=$(ss -tlnp 2>/dev/null | grep ":844" | wc -l)
    fi
    
    if [[ "$listening_ports" -gt 0 ]]; then
        print_warning "$listening_ports Redfish ports still listening"
    else
        print_success "No Redfish ports listening"
    fi
}

# Function to show post-uninstall info
show_post_uninstall_info() {
    echo ""
    echo -e "${BLUE}📋 Post-Uninstall Information${NC}"
    echo -e "${BLUE}=============================${NC}"
    echo ""
    echo "The following items were NOT removed (manual cleanup required):"
    echo "  ✅ Project files in: $PROJECT_ROOT"
    echo "  ✅ Python dependencies (pyvmomi, etc.)"
    echo "  ✅ Configuration files in: $PROJECT_ROOT/config/"
    echo ""
    echo "To completely remove the project:"
    echo "  rm -rf $PROJECT_ROOT"
    echo ""
    echo "To reinstall:"
    echo "  cd $PROJECT_ROOT"
    echo "  sudo ./setup.sh"
    echo ""
}

# Main uninstall function
main() {
    print_info "Starting Redfish VMware Server uninstall..."
    
    # Confirm uninstall
    confirm_uninstall
    
    echo ""
    print_info "Proceeding with uninstall..."
    
    # Remove systemd service
    remove_systemd_service
    
    # Remove firewall rules
    remove_firewall_rules
    
    # Clean up logs
    cleanup_logs
    
    # Clean up Python cache
    cleanup_python_cache
    
    # Show cleanup status
    show_cleanup_status
    
    # Show post-uninstall info
    show_post_uninstall_info
    
    echo ""
    print_success "Redfish VMware Server uninstall completed!"
    print_info "The service has been completely removed from the system"
}

# Handle command line arguments
case "${1:-}" in
    --help|-h)
        echo "Redfish VMware Server Uninstall Script"
        echo ""
        echo "Usage: $0 [options]"
        echo ""
        echo "Options:"
        echo "  --help, -h          Show this help message"
        echo "  --force             Skip confirmation prompt"
        echo ""
        exit 0
        ;;
    --force)
        print_warning "Force mode enabled - skipping confirmation"
        main
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
