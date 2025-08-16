#!/usr/bin/env python3
"""
Simple Redfish VMware Connectivity Test
Tests basic connectivity and operations with VMware vCenter
"""

import sys
import json
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_vmware_connection():
    """Test VMware connection and basic operations"""
    try:
        from vmware_client import VMwareClient
        
        # Load config
        config_file = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.json')
        
        if not os.path.exists(config_file):
            print("❌ Configuration file not found:", config_file)
            return False
        
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        print("🔍 Testing VMware connectivity...")
        
        # Test connection with first VM config
        if not config['vms']:
            print("❌ No VMs configured")
            return False
        
        vm_config = config['vms'][0]
        vm_name = vm_config['name']
        
        print(f"📡 Connecting to vCenter: {vm_config['vcenter_host']}")
        print(f"🖥️  Testing with VM: {vm_name}")
        
        client = VMwareClient(
            vm_config['vcenter_host'],
            vm_config['vcenter_user'],
            vm_config['vcenter_password'],
            disable_ssl=vm_config.get('disable_ssl', True)
        )
        
        # List VMs to test connection
        print("📋 Listing all VMs...")
        vms = client.list_vms()
        print(f"✅ Successfully connected to VMware. Found {len(vms)} VMs:")
        
        for vm in vms[:5]:  # Show first 5 VMs
            print(f"   - {vm.name}")
        
        if len(vms) > 5:
            print(f"   ... and {len(vms) - 5} more")
        
        # Test specific VM
        print(f"\n🔍 Testing specific VM: {vm_name}")
        vm_info = client.get_vm_info(vm_name)
        if vm_info:
            print(f"✅ VM '{vm_name}' found!")
            print(f"   Power State: {vm_info['power_state']}")
            print(f"   Guest OS: {vm_info['guest_os']}")
            print(f"   Memory: {vm_info['memory_mb']} MB")
            print(f"   CPUs: {vm_info['num_cpu']}")
            print(f"   VMware Tools: {vm_info['guest_tools_status']}")
            if vm_info['guest_ip']:
                print(f"   Guest IP: {vm_info['guest_ip']}")
        else:
            print(f"⚠️ VM '{vm_name}' not found in vCenter")
            print("Available VMs:")
            for vm in vms:
                print(f"   - {vm.name}")
        
        # Test power state query
        print(f"\n🔋 Testing power state query...")
        power_state = client.get_vm_power_state(vm_name)
        if power_state:
            print(f"✅ Current power state: {power_state}")
        else:
            print("❌ Could not retrieve power state")
        
        client.disconnect()
        print("\n✅ VMware connectivity test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ VMware connection test failed: {e}")
        return False

def test_redfish_endpoints():
    """Test basic Redfish endpoints"""
    try:
        import requests
        
        # Load config
        config_file = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.json')
        
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        if not config['vms']:
            print("❌ No VMs configured")
            return False
        
        vm_config = config['vms'][0]
        port = vm_config.get('redfish_port', 8443)
        vm_name = vm_config['name']
        
        base_url = f"http://localhost:{port}"
        
        print(f"\n🌐 Testing Redfish endpoints on port {port}...")
        
        # Test service root
        print(f"📡 Testing service root: {base_url}/redfish/v1/")
        try:
            response = requests.get(f"{base_url}/redfish/v1/", timeout=5)
            if response.status_code == 200:
                print("✅ Service root responding")
                data = response.json()
                print(f"   Service: {data.get('Name', 'Unknown')}")
                print(f"   Version: {data.get('RedfishVersion', 'Unknown')}")
            else:
                print(f"❌ Service root returned HTTP {response.status_code}")
                return False
        except requests.exceptions.ConnectionError:
            print("❌ Connection refused - Redfish server not running?")
            return False
        except Exception as e:
            print(f"❌ Service root test failed: {e}")
            return False
        
        # Test systems collection
        print(f"📋 Testing systems collection...")
        response = requests.get(f"{base_url}/redfish/v1/Systems", timeout=5)
        if response.status_code == 200:
            print("✅ Systems collection responding")
            data = response.json()
            member_count = data.get('Members@odata.count', 0)
            print(f"   Systems available: {member_count}")
        else:
            print(f"❌ Systems collection returned HTTP {response.status_code}")
            return False
        
        # Test specific system
        print(f"🖥️  Testing system: {vm_name}")
        response = requests.get(f"{base_url}/redfish/v1/Systems/{vm_name}", timeout=5)
        if response.status_code == 200:
            print("✅ System information responding")
            data = response.json()
            print(f"   Name: {data.get('Name', 'Unknown')}")
            print(f"   Power State: {data.get('PowerState', 'Unknown')}")
            print(f"   System Type: {data.get('SystemType', 'Unknown')}")
        else:
            print(f"❌ System information returned HTTP {response.status_code}")
            return False
        
        print("\n✅ Redfish endpoints test completed successfully!")
        return True
        
    except ImportError:
        print("⚠️ requests module not available, skipping Redfish endpoint tests")
        print("   Install with: pip3 install requests")
        return True
    except Exception as e:
        print(f"❌ Redfish endpoint test failed: {e}")
        return False

def main():
    """Main test function"""
    print("🧪 Redfish VMware Server - Connectivity Test")
    print("=" * 45)
    
    success = True
    
    # Test VMware connectivity
    if not test_vmware_connection():
        success = False
    
    # Test Redfish endpoints if service is running
    if not test_redfish_endpoints():
        success = False
    
    print("\n" + "=" * 45)
    if success:
        print("🎉 All connectivity tests passed!")
        print("\n💡 You can now start the Redfish server with:")
        print("   sudo systemctl start redfish-vmware-server")
        print("\n💡 Or run tests with:")
        print("   ./tests/test_redfish.sh")
    else:
        print("❌ Some connectivity tests failed")
        print("\n🔧 Please check:")
        print("   1. VMware vCenter credentials in config.json")
        print("   2. Network connectivity to vCenter")
        print("   3. VM names exist in vCenter")
        print("   4. Redfish service is running (if testing endpoints)")
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
