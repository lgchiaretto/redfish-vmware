#!/usr/bin/env python3
"""
Test script for IPMI port 627 (skinner-worker-2) 
Helps debug OpenShift connectivity issues
"""

import subprocess
import time
import sys
import socket

def test_port_binding():
    """Test if port 627 is bound"""
    print("🔍 Testing if port 627 is bound...")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        result = sock.connect_ex(('127.0.0.1', 627))
        sock.close()
        
        if result == 0:
            print("✅ Port 627 is responding")
            return True
        else:
            print("❌ Port 627 is not responding")
            return False
    except Exception as e:
        print(f"❌ Error testing port 627: {e}")
        return False

def test_ipmitool_commands():
    """Test various IPMI commands on port 627"""
    print("\n🧪 Testing IPMI commands on port 627 (skinner-worker-2)...")
    
    commands = [
        ("Get Device ID", ["ipmitool", "-I", "lanplus", "-H", "127.0.0.1", "-p", "627", "-U", "admin", "-P", "password", "mc", "info"]),
        ("Get Chassis Status", ["ipmitool", "-I", "lanplus", "-H", "127.0.0.1", "-p", "627", "-U", "admin", "-P", "password", "chassis", "status"]),
        ("Get Power Status", ["ipmitool", "-I", "lanplus", "-H", "127.0.0.1", "-p", "627", "-U", "admin", "-P", "password", "power", "status"]),
        ("Get SDR Info", ["ipmitool", "-I", "lanplus", "-H", "127.0.0.1", "-p", "627", "-U", "admin", "-P", "password", "sdr", "info"]),
        ("Get SEL Info", ["ipmitool", "-I", "lanplus", "-H", "127.0.0.1", "-p", "627", "-U", "admin", "-P", "password", "sel", "info"]),
    ]
    
    results = []
    for name, cmd in commands:
        print(f"\n📋 Testing: {name}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print(f"✅ {name}: SUCCESS")
                print(f"   Output: {result.stdout.strip()[:100]}...")
                results.append((name, True, result.stdout.strip()))
            else:
                print(f"❌ {name}: FAILED")
                print(f"   Error: {result.stderr.strip()}")
                results.append((name, False, result.stderr.strip()))
        except subprocess.TimeoutExpired:
            print(f"⏰ {name}: TIMEOUT")
            results.append((name, False, "Timeout"))
        except Exception as e:
            print(f"💥 {name}: EXCEPTION - {e}")
            results.append((name, False, str(e)))
    
    return results

def check_service_logs():
    """Check recent service logs for port 627"""
    print("\n📝 Checking service logs for skinner-worker-2...")
    
    try:
        result = subprocess.run([
            "sudo", "journalctl", "-u", "ipmi-vmware-bridge", 
            "--since", "5 minutes ago", "--grep", "worker-2", "--no-pager"
        ], capture_output=True, text=True, timeout=10)
        
        if result.stdout.strip():
            print("📋 Recent logs for skinner-worker-2:")
            for line in result.stdout.strip().split('\n')[-10:]:  # Last 10 lines
                print(f"   {line}")
        else:
            print("⚠️ No recent logs found for skinner-worker-2")
            
    except Exception as e:
        print(f"❌ Error checking logs: {e}")

def main():
    print("🔧 IPMI Port 627 Test Tool for OpenShift Worker")
    print("=" * 50)
    
    # Test 1: Port binding
    port_ok = test_port_binding()
    
    # Test 2: IPMI commands
    if port_ok:
        results = test_ipmitool_commands()
        
        # Summary
        print("\n📊 Test Summary:")
        success_count = sum(1 for _, success, _ in results if success)
        total_count = len(results)
        print(f"   Successful: {success_count}/{total_count}")
        
        if success_count == total_count:
            print("✅ All IPMI tests passed! OpenShift worker inspection should work.")
        elif success_count > 0:
            print("⚠️ Some IPMI tests passed. OpenShift inspection may have partial functionality.")
        else:
            print("❌ All IPMI tests failed. OpenShift worker inspection will likely fail.")
    else:
        print("❌ Port 627 is not accessible. Service may not be running correctly.")
    
    # Test 3: Service logs
    check_service_logs()
    
    print("\n💡 Troubleshooting Tips:")
    print("   - Restart service: sudo systemctl restart ipmi-vmware-bridge")
    print("   - Check logs: sudo journalctl -u ipmi-vmware-bridge -f")
    print("   - Verify config: cat /home/lchiaret/git/ipmi-vmware/config/config.json")
    print("   - Test all ports: ss -tuln | grep -E ':(623|624|625|626|627)'")

if __name__ == "__main__":
    main()
