#!/bin/bash
"""
Test Script for VMware IPMI BMC
Tests different VM mappings and OpenShift compatibility
"""

echo "🧪 VMware IPMI BMC Test Suite"
echo "================================"

# Test configuration
BMC_HOST="127.0.0.1"
BMC_USER="admin"
BMC_PASS="password"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Function to run test
run_test() {
    local test_name="$1"
    local command="$2"
    local expected="$3"
    
    echo -e "\n${BLUE}🔍 Testing: $test_name${NC}"
    echo "Command: $command"
    
    result=$(eval $command 2>&1)
    exit_code=$?
    
    if [ $exit_code -eq 0 ] && [[ "$result" == *"$expected"* ]]; then
        echo -e "${GREEN}✅ PASS${NC}: $result"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}❌ FAIL${NC}: $result (exit code: $exit_code)"
        echo -e "Expected: $expected"
        ((TESTS_FAILED++))
    fi
}

# Start tests
echo -e "\n${YELLOW}📋 Running IPMI BMC Tests...${NC}"

# Test 1: Basic connectivity
run_test "Basic IPMI Connectivity" \
    "ipmitool -I lanplus -H $BMC_HOST -U $BMC_USER -P $BMC_PASS mc info | head -1" \
    "Device ID"

# Test 2: Power status
run_test "Power Status Query" \
    "ipmitool -I lanplus -H $BMC_HOST -U $BMC_USER -P $BMC_PASS chassis power status" \
    "Chassis Power is"

# Test 3: Power on
run_test "Power On Command" \
    "ipmitool -I lanplus -H $BMC_HOST -U $BMC_USER -P $BMC_PASS chassis power on" \
    "Up/On"

# Test 4: Power status after on
run_test "Power Status After On" \
    "ipmitool -I lanplus -H $BMC_HOST -U $BMC_USER -P $BMC_PASS chassis power status" \
    "Chassis Power is on"

# Test 5: Power off
run_test "Power Off Command" \
    "ipmitool -I lanplus -H $BMC_HOST -U $BMC_USER -P $BMC_PASS chassis power off" \
    "Down/Off"

# Test 6: Power status after off
run_test "Power Status After Off" \
    "ipmitool -I lanplus -H $BMC_HOST -U $BMC_USER -P $BMC_PASS chassis power status" \
    "Chassis Power is off"

# Test 7: Boot device
run_test "Boot Device Query" \
    "ipmitool -I lanplus -H $BMC_HOST -U $BMC_USER -P $BMC_PASS chassis bootdev pxe" \
    ""

# Test 8: Chassis status
run_test "Chassis Status" \
    "ipmitool -I lanplus -H $BMC_HOST -U $BMC_USER -P $BMC_PASS chassis status" \
    "System Power"

echo -e "\n${YELLOW}🔧 Testing OpenShift Compatibility...${NC}"

# Test 9: Metal3 style power status
run_test "Metal3 Power Status Format" \
    "ipmitool -I lanplus -H $BMC_HOST -U $BMC_USER -P $BMC_PASS power status" \
    "Chassis Power is"

# Test 10: Metal3 style power on
run_test "Metal3 Power On Format" \
    "ipmitool -I lanplus -H $BMC_HOST -U $BMC_USER -P $BMC_PASS power on" \
    "Up/On"

echo -e "\n${YELLOW}🌐 Testing Different IP Scenarios...${NC}"

# Test with different host IPs (simulating OpenShift nodes)
if ping -c 1 192.168.86.168 >/dev/null 2>&1; then
    run_test "External IP Access" \
        "ipmitool -I lanplus -H 192.168.86.168 -U $BMC_USER -P $BMC_PASS chassis power status" \
        "Chassis Power is"
else
    echo -e "${YELLOW}⚠️  Skipping external IP test (192.168.86.168 not reachable)${NC}"
fi

echo -e "\n${YELLOW}📊 Test Results Summary${NC}"
echo "================================"
echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"
echo -e "Total Tests: $((TESTS_PASSED + TESTS_FAILED))"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "\n${GREEN}🎉 All tests passed! VMware IPMI BMC is working correctly.${NC}"
    exit 0
else
    echo -e "\n${RED}❌ Some tests failed. Check the BMC server and configuration.${NC}"
    exit 1
fi
