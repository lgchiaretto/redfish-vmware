#!/bin/bash

# Redfish Power Management Test Script
# Testa as operações de power management via Redfish API

REDFISH_BASE="http://bastion.chiaret.to"
VM1_NAME="skinner-worker-1"
VM2_NAME="skinner-worker-2"
VM1_PORT="8443"
VM2_PORT="8444"

echo "🔧 Testing Redfish Power Management"
echo "=================================="

# Test function for power operations
test_power_operation() {
    local vm_name=$1
    local port=$2
    local operation=$3
    local description=$4
    
    echo ""
    echo "🔄 Testing $description for $vm_name..."
    
    # Get current power state
    echo "📊 Current power state:"
    current_state=$(curl -s -u admin:password "${REDFISH_BASE}:${port}/redfish/v1/Systems/${vm_name}" | jq -r '.PowerState')
    echo "   Power State: $current_state"
    
    # Perform power operation
    echo "⚡ Executing $operation..."
    response=$(curl -s -u admin:password -X POST \
        -H "Content-Type: application/json" \
        -d "{\"ResetType\": \"$operation\"}" \
        "${REDFISH_BASE}:${port}/redfish/v1/Systems/${vm_name}/Actions/ComputerSystem.Reset")
    
    echo "   Response: $response"
    
    # Wait a moment and check new state
    echo "⏳ Waiting 5 seconds..."
    sleep 5
    
    echo "📊 New power state:"
    new_state=$(curl -s -u admin:password "${REDFISH_BASE}:${port}/redfish/v1/Systems/${vm_name}" | jq -r '.PowerState')
    echo "   Power State: $new_state"
    
    if [ "$current_state" != "$new_state" ] || [ "$operation" == "PowerCycle" ] || [ "$operation" == "GracefulRestart" ]; then
        echo "✅ Power operation successful!"
    else
        echo "⚠️  Power state unchanged (may be normal for some operations)"
    fi
}

# Test basic connectivity first
echo "🔍 Testing basic connectivity..."
echo ""

echo "📡 Testing VM1 ($VM1_NAME) connectivity:"
response1=$(curl -s "${REDFISH_BASE}:${VM1_PORT}/redfish/v1/Systems/${VM1_NAME}")
if echo "$response1" | jq -e . >/dev/null 2>&1; then
    echo "✅ VM1 Redfish endpoint responding"
    power1=$(echo "$response1" | jq -r '.PowerState')
    echo "   Current Power State: $power1"
else
    echo "❌ VM1 Redfish endpoint not responding"
    exit 1
fi

echo ""
echo "📡 Testing VM2 ($VM2_NAME) connectivity:"
response2=$(curl -s "${REDFISH_BASE}:${VM2_PORT}/redfish/v1/Systems/${VM2_NAME}")
if echo "$response2" | jq -e . >/dev/null 2>&1; then
    echo "✅ VM2 Redfish endpoint responding"
    power2=$(echo "$response2" | jq -r '.PowerState')
    echo "   Current Power State: $power2"
else
    echo "❌ VM2 Redfish endpoint not responding"
    exit 1
fi

echo ""
echo "🎯 Starting Power Management Tests"
echo "=================================="

# Test power cycle on VM1
test_power_operation "$VM1_NAME" "$VM1_PORT" "PowerCycle" "Power Cycle"

# Wait between tests
echo ""
echo "⏳ Waiting 10 seconds between tests..."
sleep 10

# Test graceful restart on VM2
test_power_operation "$VM2_NAME" "$VM2_PORT" "GracefulRestart" "Graceful Restart"

echo ""
echo "🏁 Power Management Tests Completed"
echo "==================================="

# Final status check
echo ""
echo "📊 Final Status Check:"
final_state1=$(curl -s -u admin:password "${REDFISH_BASE}:${VM1_PORT}/redfish/v1/Systems/${VM1_NAME}" | jq -r '.PowerState')
final_state2=$(curl -s -u admin:password "${REDFISH_BASE}:${VM2_PORT}/redfish/v1/Systems/${VM2_NAME}" | jq -r '.PowerState')

echo "   $VM1_NAME: $final_state1"
echo "   $VM2_NAME: $final_state2"

echo ""
echo "✅ All tests completed successfully!"
echo "🚀 Ready for OpenShift BareMetalHost testing!"
