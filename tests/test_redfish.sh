#!/bin/bash

# Redfish VMware Server - Test Script
# Comprehensive testing of Redfish endpoints and functionality

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
CONFIG_FILE="../config/config.json"
BASE_URL=""
VM_NAME=""
PORT=""

print_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Function to extract VM info from config
extract_vm_info() {
    if [[ ! -f "$CONFIG_FILE" ]]; then
        print_error "Config file not found: $CONFIG_FILE"
        exit 1
    fi
    
    VM_NAME=$(python3 -c "
import json
config = json.load(open('$CONFIG_FILE'))
if config['vms']:
    print(config['vms'][0]['name'])
else:
    print('unknown')
" 2>/dev/null)
    
    PORT=$(python3 -c "
import json
config = json.load(open('$CONFIG_FILE'))
if config['vms']:
    print(config['vms'][0].get('redfish_port', 8443))
else:
    print(8443)
" 2>/dev/null)
    
    BASE_URL="http://localhost:${PORT}"
    
    print_info "Testing VM: $VM_NAME on port $PORT"
}

# Function to test HTTP endpoint
test_endpoint() {
    local method="$1"
    local url="$2"
    local data="$3"
    local expected_code="$4"
    local description="$5"
    
    echo ""
    print_info "Testing: $description"
    echo "URL: $url"
    
    local cmd="curl -s -w '%{http_code}' -o /tmp/redfish_response.json"
    
    if [[ "$method" == "POST" ]]; then
        cmd="$cmd -X POST -H 'Content-Type: application/json'"
        if [[ -n "$data" ]]; then
            cmd="$cmd -d '$data'"
        fi
    elif [[ "$method" == "PATCH" ]]; then
        cmd="$cmd -X PATCH -H 'Content-Type: application/json'"
        if [[ -n "$data" ]]; then
            cmd="$cmd -d '$data'"
        fi
    fi
    
    cmd="$cmd '$url'"
    
    local http_code
    http_code=$(eval "$cmd")
    
    if [[ "$http_code" == "$expected_code" ]]; then
        print_success "HTTP $http_code (Expected: $expected_code)"
        
        # Show response if it's JSON
        if [[ -f /tmp/redfish_response.json ]]; then
            local content_type
            content_type=$(python3 -c "
import json
try:
    with open('/tmp/redfish_response.json', 'r') as f:
        data = json.load(f)
    print('json')
except:
    print('text')
" 2>/dev/null)
            
            if [[ "$content_type" == "json" ]]; then
                echo "Response:"
                python3 -m json.tool /tmp/redfish_response.json | head -20
                if [[ $(wc -l < /tmp/redfish_response.json) -gt 20 ]]; then
                    echo "... (truncated)"
                fi
            else
                echo "Response: $(cat /tmp/redfish_response.json)"
            fi
        fi
    else
        print_error "HTTP $http_code (Expected: $expected_code)"
        if [[ -f /tmp/redfish_response.json ]]; then
            echo "Response: $(cat /tmp/redfish_response.json)"
        fi
        return 1
    fi
    
    return 0
}

# Function to run all tests
run_tests() {
    local test_count=0
    local passed_count=0
    
    echo -e "${BLUE}🧪 Redfish VMware Server Test Suite${NC}"
    echo -e "${BLUE}====================================${NC}"
    
    # Test 1: Service Root
    ((test_count++))
    if test_endpoint "GET" "$BASE_URL/redfish/v1/" "" "200" "Service Root"; then
        ((passed_count++))
    fi
    
    # Test 2: Systems Collection
    ((test_count++))
    if test_endpoint "GET" "$BASE_URL/redfish/v1/Systems" "" "200" "Systems Collection"; then
        ((passed_count++))
    fi
    
    # Test 3: Specific System
    ((test_count++))
    if test_endpoint "GET" "$BASE_URL/redfish/v1/Systems/$VM_NAME" "" "200" "System Information"; then
        ((passed_count++))
    fi
    
    # Test 4: Invalid System (should return 404)
    ((test_count++))
    if test_endpoint "GET" "$BASE_URL/redfish/v1/Systems/nonexistent-vm" "" "404" "Invalid System (404 test)"; then
        ((passed_count++))
    fi
    
    # Test 5: Power On
    ((test_count++))
    if test_endpoint "POST" "$BASE_URL/redfish/v1/Systems/$VM_NAME/Actions/ComputerSystem.Reset" '{"ResetType": "On"}' "204" "Power On Action"; then
        ((passed_count++))
        sleep 2  # Brief pause between power operations
    fi
    
    # Test 6: Get System Status After Power On
    ((test_count++))
    if test_endpoint "GET" "$BASE_URL/redfish/v1/Systems/$VM_NAME" "" "200" "System Status After Power On"; then
        ((passed_count++))
    fi
    
    # Test 7: Power Off
    ((test_count++))
    if test_endpoint "POST" "$BASE_URL/redfish/v1/Systems/$VM_NAME/Actions/ComputerSystem.Reset" '{"ResetType": "ForceOff"}' "204" "Power Off Action"; then
        ((passed_count++))
        sleep 2  # Brief pause between power operations
    fi
    
    # Test 8: Graceful Shutdown
    ((test_count++))
    # First power on, then graceful shutdown
    curl -s -X POST -H 'Content-Type: application/json' -d '{"ResetType": "On"}' "$BASE_URL/redfish/v1/Systems/$VM_NAME/Actions/ComputerSystem.Reset" >/dev/null
    sleep 3
    if test_endpoint "POST" "$BASE_URL/redfish/v1/Systems/$VM_NAME/Actions/ComputerSystem.Reset" '{"ResetType": "GracefulShutdown"}' "204" "Graceful Shutdown"; then
        ((passed_count++))
    fi
    
    # Test 9: Invalid Reset Type
    ((test_count++))
    if test_endpoint "POST" "$BASE_URL/redfish/v1/Systems/$VM_NAME/Actions/ComputerSystem.Reset" '{"ResetType": "InvalidType"}' "400" "Invalid Reset Type (400 test)"; then
        ((passed_count++))
    fi
    
    # Test 10: Malformed JSON
    ((test_count++))
    if test_endpoint "POST" "$BASE_URL/redfish/v1/Systems/$VM_NAME/Actions/ComputerSystem.Reset" '{"ResetType": "On"' "400" "Malformed JSON (400 test)"; then
        ((passed_count++))
    fi
    
    # Test 11: PATCH method (should return 405)
    ((test_count++))
    if test_endpoint "PATCH" "$BASE_URL/redfish/v1/Systems/$VM_NAME" '{"Name": "NewName"}' "405" "PATCH Method Not Allowed (405 test)"; then
        ((passed_count++))
    fi
    
    # Test 12: Invalid Action Path
    ((test_count++))
    if test_endpoint "POST" "$BASE_URL/redfish/v1/Systems/$VM_NAME/Actions/InvalidAction" '{}' "404" "Invalid Action Path (404 test)"; then
        ((passed_count++))
    fi
    
    # Results
    echo ""
    echo -e "${BLUE}📊 Test Results${NC}"
    echo -e "${BLUE}===============${NC}"
    echo "Total tests: $test_count"
    echo "Passed: $passed_count"
    echo "Failed: $((test_count - passed_count))"
    
    if [[ $passed_count -eq $test_count ]]; then
        echo ""
        print_success "All tests passed! 🎉"
        return 0
    else
        echo ""
        print_error "Some tests failed. Check the output above for details."
        return 1
    fi
}

# Function to test power cycle sequence
test_power_cycle() {
    echo ""
    echo -e "${BLUE}🔄 Power Cycle Test${NC}"
    echo -e "${BLUE}===================${NC}"
    
    print_info "Starting power cycle test sequence..."
    
    # Power off
    print_info "Step 1: Power Off"
    curl -s -X POST -H 'Content-Type: application/json' -d '{"ResetType": "ForceOff"}' "$BASE_URL/redfish/v1/Systems/$VM_NAME/Actions/ComputerSystem.Reset"
    sleep 3
    
    # Check status
    print_info "Step 2: Check Power State"
    local power_state
    power_state=$(curl -s "$BASE_URL/redfish/v1/Systems/$VM_NAME" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    print(data.get('PowerState', 'Unknown'))
except:
    print('Unknown')
")
    echo "Power state: $power_state"
    
    # Power on
    print_info "Step 3: Power On"
    curl -s -X POST -H 'Content-Type: application/json' -d '{"ResetType": "On"}' "$BASE_URL/redfish/v1/Systems/$VM_NAME/Actions/ComputerSystem.Reset"
    sleep 3
    
    # Check status again
    print_info "Step 4: Check Power State"
    power_state=$(curl -s "$BASE_URL/redfish/v1/Systems/$VM_NAME" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    print(data.get('PowerState', 'Unknown'))
except:
    print('Unknown')
")
    echo "Power state: $power_state"
    
    print_success "Power cycle test completed"
}

# Function to show service status
show_service_status() {
    echo ""
    echo -e "${BLUE}📋 Service Status${NC}"
    echo -e "${BLUE}=================${NC}"
    
    if systemctl is-active redfish-vmware-server >/dev/null 2>&1; then
        print_success "Redfish VMware Server is running"
        
        # Show basic service info
        echo ""
        echo "Service details:"
        systemctl status redfish-vmware-server --no-pager -l | head -10
        
        # Show ports in use
        echo ""
        print_info "Listening ports:"
        netstat -tlnp 2>/dev/null | grep python3 | grep ":84" || echo "No Redfish ports found in netstat"
        
    else
        print_error "Redfish VMware Server is not running"
        print_info "Start with: sudo systemctl start redfish-vmware-server"
        return 1
    fi
}

# Function to monitor real-time logs
monitor_logs() {
    echo ""
    echo -e "${BLUE}📝 Real-time Service Logs${NC}"
    echo -e "${BLUE}==========================${NC}"
    print_info "Press Ctrl+C to stop monitoring"
    echo ""
    
    sudo journalctl -u redfish-vmware-server -f
}

# Main function
main() {
    # Check if curl is available
    if ! command -v curl >/dev/null 2>&1; then
        print_error "curl is required for testing but not installed"
        exit 1
    fi
    
    # Extract VM info from config
    extract_vm_info
    
    # Check if service is running
    if ! systemctl is-active redfish-vmware-server >/dev/null 2>&1; then
        print_warning "Redfish VMware Server is not running"
        print_info "Start with: sudo systemctl start redfish-vmware-server"
        echo ""
        show_service_status
        exit 1
    fi
    
    # Run tests based on argument
    case "${1:-all}" in
        "all"|"")
            run_tests
            ;;
        "power")
            test_power_cycle
            ;;
        "status")
            show_service_status
            ;;
        "logs")
            monitor_logs
            ;;
        *)
            echo "Usage: $0 [all|power|status|logs]"
            echo ""
            echo "Options:"
            echo "  all     - Run all tests (default)"
            echo "  power   - Test power cycle sequence"
            echo "  status  - Show service status"
            echo "  logs    - Monitor real-time logs"
            echo ""
            exit 1
            ;;
    esac
}

# Cleanup function
cleanup() {
    rm -f /tmp/redfish_response.json
}

trap cleanup EXIT

# Run main function
main "$@"
