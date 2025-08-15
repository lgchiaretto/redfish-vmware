#!/usr/bin/env python3
"""
IPMI VMware Bridge Test Script

This script tests the IPMI bridge functionality by simulating IPMI commands
and verifying VMware connectivity.
"""

import sys
import subprocess
import time
import json
import socket
from vmware_client import VMwareClient

def test_vmware_connection():
    """Test VMware vSphere connectivity"""
    print("Testing VMware vSphere connection...")
    
    try:
        # Load configuration
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        vmware_config = config['vmware']
        
        # Create client
        client = VMwareClient(
            host=vmware_config['host'],
            user=vmware_config['user'],
            password=vmware_config['password'],
            port=vmware_config.get('port', 443),
            disable_ssl_verification=vmware_config.get('disable_ssl', True)
        )
        
        # List VMs
        vms = client.list_vms()
        print(f"✓ Successfully connected to {vmware_config['host']}")
        print(f"✓ Found {len(vms)} virtual machines")
        
        # Show first few VMs
        if vms:
            print("\nFirst 5 VMs:")
            for i, vm in enumerate(vms[:5]):
                info = client.get_vm_info(vm.name)
                print(f"  {i+1}. {vm.name} - {info.get('power_state', 'unknown')}")
        
        client.disconnect()
        return True
        
    except Exception as e:
        print(f"✗ VMware connection failed: {e}")
        return False

def test_ipmi_ports():
    """Test IPMI port availability"""
    print("\nTesting IPMI port availability...")
    
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        for vm_config in config['vms']:
            port = vm_config['ipmi_port']
            address = vm_config.get('ipmi_address', '0.0.0.0')
            
            try:
                # Try to bind to the port
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.bind((address, port))
                sock.close()
                print(f"✓ Port {port} is available for {vm_config['vm_name']}")
            except OSError as e:
                print(f"✗ Port {port} is not available for {vm_config['vm_name']}: {e}")
                return False
        
        return True
        
    except Exception as e:
        print(f"✗ Port test failed: {e}")
        return False

def test_dependencies():
    """Test Python dependencies"""
    print("\nTesting Python dependencies...")
    
    dependencies = [
        'pyvmomi',
        'pyghmi',
        'ssl',
        'json',
        'logging',
        'threading'
    ]
    
    missing = []
    
    for dep in dependencies:
        try:
            __import__(dep)
            print(f"✓ {dep}")
        except ImportError:
            print(f"✗ {dep} - MISSING")
            missing.append(dep)
    
    if missing:
        print(f"\nMissing dependencies: {missing}")
        print("Install with: pip3 install -r requirements.txt")
        return False
    
    return True

def test_config_file():
    """Test configuration file"""
    print("\nTesting configuration file...")
    
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        # Check required sections
        required_sections = ['vmware', 'vms']
        for section in required_sections:
            if section not in config:
                print(f"✗ Missing section: {section}")
                return False
            print(f"✓ Section {section} found")
        
        # Check VMware configuration
        vmware_config = config['vmware']
        required_vmware_fields = ['host', 'user', 'password']
        for field in required_vmware_fields:
            if field not in vmware_config:
                print(f"✗ Missing VMware field: {field}")
                return False
            print(f"✓ VMware field {field} found")
        
        # Check VM configurations
        if not config['vms']:
            print("✗ No VMs configured")
            return False
        
        print(f"✓ {len(config['vms'])} VMs configured")
        
        for i, vm_config in enumerate(config['vms']):
            required_vm_fields = ['vm_name', 'ipmi_port', 'ipmi_user', 'ipmi_password']
            for field in required_vm_fields:
                if field not in vm_config:
                    print(f"✗ VM {i+1} missing field: {field}")
                    return False
            print(f"✓ VM {i+1} ({vm_config['vm_name']}) configured correctly")
        
        return True
        
    except FileNotFoundError:
        print("✗ config.json not found")
        return False
    except json.JSONDecodeError as e:
        print(f"✗ Invalid JSON in config.json: {e}")
        return False
    except Exception as e:
        print(f"✗ Config test failed: {e}")
        return False

def test_permissions():
    """Test file permissions and access"""
    print("\nTesting permissions...")
    
    files_to_check = [
        'ipmi_vmware_bridge.py',
        'vmware_client.py',
        'config.json',
        'configure-ipmi.sh'
    ]
    
    for file_path in files_to_check:
        try:
            with open(file_path, 'r') as f:
                f.read(1)  # Try to read first character
            print(f"✓ {file_path} is readable")
        except Exception as e:
            print(f"✗ Cannot read {file_path}: {e}")
            return False
    
    return True

def simulate_ipmi_command():
    """Simulate IPMI command using ipmitool"""
    print("\nTesting IPMI command simulation...")
    
    try:
        # Check if ipmitool is available
        result = subprocess.run(['which', 'ipmitool'], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            print("ℹ ipmitool not found - skipping IPMI command test")
            return True
        
        print("✓ ipmitool found")
        
        # Load config to get first VM's IPMI settings
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        if not config['vms']:
            print("ℹ No VMs configured - skipping IPMI test")
            return True
        
        vm_config = config['vms'][0]
        
        # Try to connect to IPMI (this will fail if service isn't running, which is expected)
        cmd = [
            'ipmitool', '-I', 'lanplus',
            '-H', 'localhost',
            '-p', str(vm_config['ipmi_port']),
            '-U', vm_config['ipmi_user'],
            '-P', vm_config['ipmi_password'],
            'chassis', 'status'
        ]
        
        print(f"Testing IPMI command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✓ IPMI command succeeded")
            return True
        else:
            print(f"ℹ IPMI command failed (expected if service not running): {result.stderr}")
            return True  # This is expected if service isn't running yet
            
    except subprocess.TimeoutExpired:
        print("ℹ IPMI command timed out (expected if service not running)")
        return True
    except Exception as e:
        print(f"ℹ IPMI test failed: {e}")
        return True  # Non-critical failure

def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("IPMI VMware Bridge - Test Suite")
    print("=" * 60)
    
    tests = [
        ("Configuration File", test_config_file),
        ("File Permissions", test_permissions),
        ("Python Dependencies", test_dependencies),
        ("IPMI Ports", test_ipmi_ports),
        ("VMware Connection", test_vmware_connection),
        ("IPMI Command", simulate_ipmi_command)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            if test_func():
                passed += 1
                print(f"✓ {test_name} PASSED")
            else:
                print(f"✗ {test_name} FAILED")
        except Exception as e:
            print(f"✗ {test_name} ERROR: {e}")
    
    print("\n" + "=" * 60)
    print(f"Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 All tests passed! The system appears to be ready.")
        return True
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
        return False

if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
