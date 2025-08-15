#!/bin/bash

# Setup Virtual BMC IPs for OpenShift Integration
# This script configures virtual IPs on the IPMI server to provide
# dedicated BMC addresses for each OpenShift node

set -e

INTERFACE="ens33"
BASE_IP="192.168.86"
BMC_IPS=("50" "51" "52")
NODE_NAMES=("skinner-master-0" "skinner-master-1" "skinner-master-2")

echo "🔧 Setting up Virtual BMC IPs..."

# Function to add virtual IP
add_virtual_ip() {
    local ip_suffix=$1
    local label=$2
    local full_ip="${BASE_IP}.${ip_suffix}"
    
    echo "Adding virtual IP: ${full_ip} (${label})"
    
    if ip addr show | grep -q "${full_ip}/24"; then
        echo "  ✅ IP ${full_ip} already exists"
    else
        sudo ip addr add ${full_ip}/24 dev ${INTERFACE} label ${INTERFACE}:${label}
        echo "  ✅ Added ${full_ip}"
    fi
}

# Function to remove virtual IP
remove_virtual_ip() {
    local ip_suffix=$1
    local full_ip="${BASE_IP}.${ip_suffix}"
    
    echo "Removing virtual IP: ${full_ip}"
    
    if ip addr show | grep -q "${full_ip}/24"; then
        sudo ip addr del ${full_ip}/24 dev ${INTERFACE}
        echo "  ✅ Removed ${full_ip}"
    else
        echo "  ⚠️  IP ${full_ip} not found"
    fi
}

# Function to setup virtual IPs
setup_virtual_ips() {
    echo "Setting up virtual BMC IPs..."
    
    for i in "${!BMC_IPS[@]}"; do
        add_virtual_ip "${BMC_IPS[$i]}" "bmh${i}"
    done
    
    echo ""
    echo "📋 Current IP configuration:"
    ip addr show ${INTERFACE} | grep "inet "
}

# Function to remove virtual IPs
cleanup_virtual_ips() {
    echo "Removing virtual BMC IPs..."
    
    for ip_suffix in "${BMC_IPS[@]}"; do
        remove_virtual_ip "${ip_suffix}"
    done
}

# Function to make configuration persistent
make_persistent() {
    echo "Making virtual IP configuration persistent..."
    
    # Create systemd service for virtual IPs
    cat > /tmp/virtual-bmcs.service << EOF
[Unit]
Description=Virtual BMC IPs for IPMI-VMware Bridge
After=network.target
Wants=network.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/bash -c 'for ip in ${BMC_IPS[@]}; do ip addr add ${BASE_IP}.\$ip/24 dev ${INTERFACE} label ${INTERFACE}:bmh\$((\$ip-50)) 2>/dev/null || true; done'
ExecStop=/bin/bash -c 'for ip in ${BMC_IPS[@]}; do ip addr del ${BASE_IP}.\$ip/24 dev ${INTERFACE} 2>/dev/null || true; done'

[Install]
WantedBy=multi-user.target
EOF

    sudo mv /tmp/virtual-bmcs.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable virtual-bmcs.service
    
    echo "  ✅ Created systemd service: virtual-bmcs.service"
}

# Function to generate OpenShift BareMetalHost configurations
generate_openshift_configs() {
    echo "Generating OpenShift BareMetalHost configurations..."
    
    mkdir -p /home/lchiaret/git/ipmi-vmware/openshift-configs
    
    for i in "${!NODE_NAMES[@]}"; do
        local node_name="${NODE_NAMES[$i]}"
        local bmc_ip="${BASE_IP}.${BMC_IPS[$i]}"
        local node_ip="192.168.110.${BMC_IPS[$i]}"
        
        cat > "/home/lchiaret/git/ipmi-vmware/openshift-configs/${node_name}-bmh.yaml" << EOF
---
apiVersion: metal3.io/v1alpha1
kind: BareMetalHost
metadata:
  name: ${node_name}
  namespace: openshift-machine-api
spec:
  online: true
  bootMACAddress: "52:54:00:$(printf '%02x:%02x:%02x' $((RANDOM%256)) $((RANDOM%256)) $((RANDOM%256)))"
  bmc:
    address: ipmi://${bmc_ip}:623
    credentialsName: ${node_name}-bmc-secret
    disableCertificateVerification: true
  externallyProvisioned: true
  networkData:
    name: ${node_name}-network-data
    namespace: openshift-machine-api
---
apiVersion: v1
kind: Secret
metadata:
  name: ${node_name}-bmc-secret
  namespace: openshift-machine-api
type: Opaque
data:
  username: $(echo -n "admin" | base64)
  password: $(echo -n "admin" | base64)
EOF
        
        echo "  ✅ Generated: ${node_name}-bmh.yaml (BMC: ${bmc_ip})"
    done
    
    # Generate summary file
    cat > "/home/lchiaret/git/ipmi-vmware/openshift-configs/README.md" << EOF
# OpenShift BareMetalHost Configuration

## Virtual BMC Mapping

| Node Name | BMC IP | OpenShift Node IP | VM Name |
|-----------|--------|-------------------|---------|
$(for i in "${!NODE_NAMES[@]}"; do
    echo "| ${NODE_NAMES[$i]} | ${BASE_IP}.${BMC_IPS[$i]} | 192.168.110.${BMC_IPS[$i]} | ${NODE_NAMES[$i]} |"
done)

## Deployment Commands

Apply the BareMetalHost configurations:

\`\`\`bash
# Apply all configurations
kubectl apply -f /home/lchiaret/git/ipmi-vmware/openshift-configs/

# Or apply individually
$(for i in "${!NODE_NAMES[@]}"; do
    echo "kubectl apply -f ${NODE_NAMES[$i]}-bmh.yaml"
done)
\`\`\`

## Testing BMC Connectivity

\`\`\`bash
# Test each BMC
$(for i in "${!BMC_IPS[@]}"; do
    echo "ipmitool -I lan -H ${BASE_IP}.${BMC_IPS[$i]} -p 623 -U admin -P admin chassis power status"
done)
\`\`\`
EOF
    
    echo "  ✅ Generated: README.md with deployment instructions"
}

# Function to test BMC connectivity
test_connectivity() {
    echo "Testing BMC connectivity..."
    
    for i in "${!BMC_IPS[@]}"; do
        local bmc_ip="${BASE_IP}.${BMC_IPS[$i]}"
        local node_name="${NODE_NAMES[$i]}"
        
        echo "Testing ${node_name} BMC at ${bmc_ip}..."
        
        # Test RMCP ping
        if timeout 5 bash -c "echo | nc -u ${bmc_ip} 623" 2>/dev/null; then
            echo "  ✅ Port 623 is reachable"
        else
            echo "  ❌ Port 623 unreachable"
        fi
    done
}

# Function to restart IPMI service
restart_ipmi_service() {
    echo "Restarting IPMI service to pick up new configuration..."
    
    # Stop current process
    sudo pkill -f "python.*main.py" 2>/dev/null || true
    sleep 2
    
    # Start with new config
    sudo /opt/ipmi-vmware/.venv/bin/python /opt/ipmi-vmware/main.py --daemon &
    sleep 3
    
    # Check if running
    if pgrep -f "python.*main.py" > /dev/null; then
        echo "  ✅ IPMI service restarted successfully"
    else
        echo "  ❌ Failed to restart IPMI service"
        return 1
    fi
}

# Main function
main() {
    case "${1:-setup}" in
        "setup")
            setup_virtual_ips
            generate_openshift_configs
            restart_ipmi_service
            test_connectivity
            echo ""
            echo "🎉 Virtual BMC setup complete!"
            echo ""
            echo "Next steps:"
            echo "1. Apply the BareMetalHost configurations in openshift-configs/"
            echo "2. Test BMC connectivity from OpenShift nodes"
            echo "3. Run 'sudo $0 persistent' to make configuration persistent"
            ;;
        "persistent")
            make_persistent
            echo "  ✅ Configuration made persistent"
            ;;
        "cleanup")
            cleanup_virtual_ips
            sudo systemctl disable virtual-bmcs.service 2>/dev/null || true
            sudo rm -f /etc/systemd/system/virtual-bmcs.service
            sudo systemctl daemon-reload
            echo "  ✅ Virtual BMC configuration removed"
            ;;
        "status")
            echo "Virtual BMC Status:"
            echo ""
            for i in "${!BMC_IPS[@]}"; do
                local bmc_ip="${BASE_IP}.${BMC_IPS[$i]}"
                local node_name="${NODE_NAMES[$i]}"
                
                if ip addr show | grep -q "${bmc_ip}/24"; then
                    echo "  ✅ ${node_name}: ${bmc_ip} (Active)"
                else
                    echo "  ❌ ${node_name}: ${bmc_ip} (Missing)"
                fi
            done
            ;;
        "test")
            test_connectivity
            ;;
        *)
            echo "Usage: $0 {setup|persistent|cleanup|status|test}"
            echo ""
            echo "Commands:"
            echo "  setup     - Setup virtual BMC IPs and generate configs"
            echo "  persistent- Make configuration persistent across reboots"
            echo "  cleanup   - Remove virtual BMC configuration"
            echo "  status    - Show current virtual BMC status"
            echo "  test      - Test BMC connectivity"
            exit 1
            ;;
    esac
}

main "$@"
