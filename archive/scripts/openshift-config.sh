#!/bin/bash
# OpenShift IPMI Bridge Configuration Helper

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

CONFIG_FILE="/opt/ipmi-vmware/config.ini"

show_current_config() {
    print_info "Current IPMI Bridge Configuration:"
    echo "=================================="
    
    if [[ -f "$CONFIG_FILE" ]]; then
        echo "🌐 IPMI Server:"
        grep -A 3 "\[ipmi\]" "$CONFIG_FILE" | grep -v "^#" | grep -v "^\[" | grep -v "^$"
        
        echo ""
        echo "🔗 VM Mappings:"
        grep -A 20 "\[vm_mapping\]" "$CONFIG_FILE" | grep -v "^#" | grep -v "^\[" | grep -v "^$" | head -10
        
        echo ""
        echo "📊 Server Status:"
        systemctl is-active ipmi-vmware-bridge && echo "✅ Service is running" || echo "❌ Service is not running"
        
        # Show listening ports
        if netstat -ulnp 2>/dev/null | grep -q ":623 "; then
            SERVER_IP=$(hostname -I | awk '{print $1}')
            echo "✅ Listening on ${SERVER_IP}:623"
        else
            echo "❌ Not listening on port 623"
        fi
    else
        print_error "Configuration file not found: $CONFIG_FILE"
        exit 1
    fi
}

add_vm_mapping() {
    local openshift_ip="$1"
    local vm_name="$2"
    
    if [[ -z "$openshift_ip" || -z "$vm_name" ]]; then
        print_error "Usage: add_vm_mapping <openshift_ip> <vm_name>"
        return 1
    fi
    
    print_info "Adding VM mapping: $openshift_ip -> $vm_name"
    
    # Check if mapping already exists
    if grep -q "^$openshift_ip = " "$CONFIG_FILE"; then
        print_warning "Mapping for $openshift_ip already exists, updating..."
        sudo sed -i "s/^$openshift_ip = .*/$openshift_ip = $vm_name/" "$CONFIG_FILE"
    else
        # Add to vm_mapping section
        sudo sed -i "/\[vm_mapping\]/a $openshift_ip = $vm_name" "$CONFIG_FILE"
    fi
    
    print_success "VM mapping added: $openshift_ip -> $vm_name"
    
    # Restart service
    print_info "Restarting IPMI bridge service..."
    sudo systemctl restart ipmi-vmware-bridge
    
    if systemctl is-active ipmi-vmware-bridge >/dev/null; then
        print_success "Service restarted successfully"
    else
        print_error "Service failed to restart"
        return 1
    fi
}

test_connectivity() {
    local target_ip="${1:-127.0.0.1}"
    
    print_info "Testing IPMI connectivity to $target_ip:623"
    
    # Create simple test script
    cat > /tmp/ipmi_test.py << 'EOF'
import socket
import sys

def test_rmcp_ping(host, port=623):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5.0)
        
        # RMCP ping packet
        ping = bytes([0x06, 0x00, 0xff, 0x07, 0x00, 0x00, 0x00, 0x00, 
                     0x00, 0x00, 0x00, 0x00, 0x00, 0x09, 0x20, 0x18, 
                     0xc8, 0x81, 0x00, 0x38, 0x8e, 0x04, 0xb5])
        
        sock.sendto(ping, (host, port))
        response, addr = sock.recvfrom(1024)
        sock.close()
        
        if len(response) > 0:
            print("✅ RMCP ping successful")
            return True
        else:
            print("❌ No response received")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    test_rmcp_ping(host)
EOF

    if python3 /tmp/ipmi_test.py "$target_ip"; then
        print_success "IPMI connectivity test passed"
    else
        print_error "IPMI connectivity test failed"
    fi
    
    rm -f /tmp/ipmi_test.py
}

monitor_logs() {
    print_info "Monitoring IPMI bridge logs (Ctrl+C to stop)..."
    echo "Look for 'No VM mapped for IP' messages to identify OpenShift cluster IPs"
    echo "=================================================="
    
    sudo journalctl -u ipmi-vmware-bridge -f --no-hostname
}

generate_bmh_yaml() {
    local vm_name="$1"
    local server_ip="${2:-$(hostname -I | awk '{print $1}')}"
    
    if [[ -z "$vm_name" ]]; then
        print_error "Usage: generate_bmh_yaml <vm_name> [server_ip]"
        return 1
    fi
    
    local yaml_file="/tmp/baremetalhost-${vm_name}.yaml"
    
    print_info "Generating BareMetalHost YAML for $vm_name..."
    
    cat > "$yaml_file" << EOF
apiVersion: metal3.io/v1alpha1
kind: BareMetalHost
metadata:
  name: $vm_name
  namespace: openshift-machine-api
spec:
  online: true
  bmc:
    address: ipmi://$server_ip:623
    credentialsName: ${vm_name}-bmc-secret
  bootMACAddress: "00:50:56:xx:xx:xx"  # Update with actual VM MAC
  hardwareProfile: default
---
apiVersion: v1
kind: Secret
metadata:
  name: ${vm_name}-bmc-secret
  namespace: openshift-machine-api
type: Opaque
data:
  username: YWRtaW4=        # "admin" in base64
  password: cGFzc3dvcmQ=    # "password" in base64
EOF

    print_success "BareMetalHost YAML generated: $yaml_file"
    echo ""
    echo "To apply to OpenShift cluster:"
    echo "  oc apply -f $yaml_file"
    echo ""
    echo "Remember to update the bootMACAddress with the actual VM MAC address"
}

show_help() {
    echo "OpenShift IPMI Bridge Configuration Helper"
    echo "=========================================="
    echo ""
    echo "Commands:"
    echo "  status                           - Show current configuration and status"
    echo "  add <openshift_ip> <vm_name>     - Add VM mapping for OpenShift IP"
    echo "  test [target_ip]                 - Test IPMI connectivity"
    echo "  monitor                          - Monitor logs for OpenShift requests"
    echo "  generate <vm_name> [server_ip]   - Generate BareMetalHost YAML"
    echo "  help                             - Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 status"
    echo "  $0 add 192.168.110.50 willie-master-0"
    echo "  $0 test 192.168.86.168"
    echo "  $0 monitor"
    echo "  $0 generate willie-master-0"
}

# Main
case "${1:-help}" in
    status)
        show_current_config
        ;;
    add)
        add_vm_mapping "$2" "$3"
        ;;
    test)
        test_connectivity "$2"
        ;;
    monitor)
        monitor_logs
        ;;
    generate)
        generate_bmh_yaml "$2" "$3"
        ;;
    help|*)
        show_help
        ;;
esac
