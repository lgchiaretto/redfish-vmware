#!/bin/bash
# Test script for IPMI-VMware Bridge systemd installation

SERVICE_NAME="ipmi-vmware-bridge"
INSTALL_DIR="/opt/ipmi-vmware"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_test() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

print_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

print_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
}

print_info() {
    echo -e "${YELLOW}[INFO]${NC} $1"
}

# Test if service exists
test_service_exists() {
    print_test "Checking if systemd service exists..."
    if systemctl list-unit-files | grep -q "$SERVICE_NAME"; then
        print_pass "Service $SERVICE_NAME exists"
        return 0
    else
        print_fail "Service $SERVICE_NAME does not exist"
        return 1
    fi
}

# Test if installation directory exists
test_installation_dir() {
    print_test "Checking installation directory..."
    if [[ -d "$INSTALL_DIR" ]]; then
        print_pass "Installation directory exists: $INSTALL_DIR"
        return 0
    else
        print_fail "Installation directory missing: $INSTALL_DIR"
        return 1
    fi
}

# Test if management command exists
test_management_command() {
    print_test "Checking management command..."
    if command -v ipmi-bridge >/dev/null; then
        print_pass "Management command 'ipmi-bridge' is available"
        return 0
    else
        print_fail "Management command 'ipmi-bridge' not found"
        return 1
    fi
}

# Test configuration file
test_config_file() {
    print_test "Checking configuration file..."
    if [[ -f "$INSTALL_DIR/config.ini" ]]; then
        print_pass "Configuration file exists"
        
        # Test config syntax
        if python3 -c "import configparser; c = configparser.ConfigParser(); c.read('$INSTALL_DIR/config.ini')" 2>/dev/null; then
            print_pass "Configuration file syntax is valid"
            return 0
        else
            print_fail "Configuration file has syntax errors"
            return 1
        fi
    else
        print_fail "Configuration file missing: $INSTALL_DIR/config.ini"
        return 1
    fi
}

# Test Python environment
test_python_env() {
    print_test "Checking Python virtual environment..."
    if [[ -f "$INSTALL_DIR/.venv/bin/python" ]]; then
        print_pass "Python virtual environment exists"
        
        # Test if dependencies are installed
        if "$INSTALL_DIR/.venv/bin/python" -c "import pyvmomi, pyghmi" 2>/dev/null; then
            print_pass "Python dependencies are installed"
            return 0
        else
            print_fail "Python dependencies missing"
            return 1
        fi
    else
        print_fail "Python virtual environment missing"
        return 1
    fi
}

# Test service configuration
test_service_config() {
    print_test "Checking service configuration..."
    
    # Check if service can be loaded
    if systemctl cat "$SERVICE_NAME" >/dev/null 2>&1; then
        print_pass "Service configuration is valid"
        return 0
    else
        print_fail "Service configuration is invalid"
        return 1
    fi
}

# Test permissions
test_permissions() {
    print_test "Checking file permissions..."
    
    if [[ -O "$INSTALL_DIR" ]] || [[ $(stat -c '%U' "$INSTALL_DIR") == "ipmi-bridge" ]]; then
        print_pass "Installation directory has correct ownership"
        return 0
    else
        print_fail "Installation directory has incorrect ownership"
        return 1
    fi
}

# Test VMware connection (if configured)
test_vmware_connection() {
    print_test "Testing VMware connection..."
    
    # Check if VMware settings are configured
    if grep -q "your-vcenter.domain.com\|chiaretto-vcsa01.chiaret.to" "$INSTALL_DIR/config.ini" 2>/dev/null; then
        print_info "VMware connection test requires proper configuration"
        print_info "Run: ipmi-bridge test"
        return 0
    else
        print_info "VMware not configured for testing"
        return 0
    fi
}

# Run comprehensive test
run_tests() {
    echo "=========================================="
    echo "  IPMI-VMware Bridge Installation Test   "
    echo "=========================================="
    echo ""
    
    local tests_passed=0
    local tests_total=7
    
    test_service_exists && ((tests_passed++))
    test_installation_dir && ((tests_passed++))
    test_management_command && ((tests_passed++))
    test_config_file && ((tests_passed++))
    test_python_env && ((tests_passed++))
    test_service_config && ((tests_passed++))
    test_permissions && ((tests_passed++))
    
    echo ""
    echo "=========================================="
    echo "Test Results: $tests_passed/$tests_total passed"
    echo "=========================================="
    
    if [[ $tests_passed -eq $tests_total ]]; then
        print_pass "All tests passed! Installation is ready for use."
        echo ""
        echo "Next steps:"
        echo "1. Configure VMware settings: ipmi-bridge config"
        echo "2. Test VMware connection: ipmi-bridge test"
        echo "3. Enable service: ipmi-bridge enable"
        echo "4. Start service: ipmi-bridge start"
        echo "5. Check status: ipmi-bridge status"
        return 0
    else
        print_fail "Some tests failed. Please check the installation."
        return 1
    fi
}

# Show current status
show_status() {
    echo "=========================================="
    echo "     IPMI-VMware Bridge Status           "
    echo "=========================================="
    echo ""
    
    print_info "Service Status:"
    systemctl status "$SERVICE_NAME" --no-pager || echo "Service not found or not running"
    
    echo ""
    print_info "Management Commands:"
    echo "ipmi-bridge start    - Start the service"
    echo "ipmi-bridge stop     - Stop the service"
    echo "ipmi-bridge status   - Show detailed status"
    echo "ipmi-bridge logs     - Show live logs"
    echo "ipmi-bridge test     - Test VMware connection"
    echo "ipmi-bridge config   - Edit configuration"
    
    echo ""
    print_info "Files:"
    echo "Config: $INSTALL_DIR/config.ini"
    echo "Logs: $INSTALL_DIR/ipmi_vmware.log"
    echo "Service: /etc/systemd/system/$SERVICE_NAME.service"
}

# Main script
case "${1:-test}" in
    test)
        run_tests
        ;;
    status)
        show_status
        ;;
    *)
        echo "Usage: $0 {test|status}"
        echo ""
        echo "Commands:"
        echo "  test    - Run installation tests"
        echo "  status  - Show current status"
        exit 1
        ;;
esac
