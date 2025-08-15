#!/usr/bin/env python3

import sys
import os
import subprocess
import time

def test_ipmi_ports():
    """Test IPMI connectivity on all configured ports"""
    print("🧪 Testing IPMI VMware Bridge")
    print("=" * 50)
    
    ports = [623, 624, 625, 626]
    
    for port in ports:
        print(f"\n🎯 Testing port {port}...")
        
        # Test UDP socket binding
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            
            if result == 0:
                print(f"  ✅ Port {port} is accessible")
            else:
                print(f"  ❌ Port {port} is not accessible")
        except Exception as e:
            print(f"  ❌ Error testing port {port}: {e}")
        
        # Test with ipmitool
        print(f"  🔧 Testing IPMI tools on port {port}...")
        
        # Try different IPMI interfaces
        interfaces = ['lan', 'lanplus']
        
        for interface in interfaces:
            try:
                cmd = [
                    'ipmitool', '-I', interface, 
                    '-H', '127.0.0.1', '-p', str(port),
                    '-U', 'admin', '-P', 'admin',
                    'mc', 'info'
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    print(f"    ✅ {interface}: SUCCESS")
                    print(f"    📋 Response: {result.stdout.strip()[:100]}...")
                    break
                else:
                    print(f"    ❌ {interface}: FAILED - {result.stderr.strip()[:100]}")
                    
            except subprocess.TimeoutExpired:
                print(f"    ⏰ {interface}: TIMEOUT")
            except Exception as e:
                print(f"    ❌ {interface}: ERROR - {e}")

if __name__ == "__main__":
    test_ipmi_ports()
