#!/usr/bin/env python3
"""
IPMI Debug Tool - Capture all IPMI requests
This will help us understand exactly what OpenShift is calling
"""
import sys
import time
import subprocess
import json

def monitor_logs_for_power_commands():
    """Monitor journalctl for power-related IPMI commands"""
    
    print("🔍 Starting IPMI Power Commands Monitor...")
    print("📋 Looking for specific power-related IPMI calls from OpenShift")
    print("⏰ Will monitor for 30 seconds...")
    print("=" * 60)
    
    # Commands to watch for
    power_commands = [
        "GET_CHASSIS_STATUS",     # NetFn: 0x00, Command: 0x00
        "CHASSIS_CONTROL",        # NetFn: 0x00, Command: 0x02  
        "GET_DEVICE_ID",         # NetFn: 0x06, Command: 0x01
        "DCMI_POWER_READING",    # NetFn: 0x2C, Command: 0x00
        "power status",           # Generic power status
        "power state",            # Generic power state  
        "poweredOn",             # OpenShift field
    ]
    
    cmd = [
        'sudo', 'timeout', '30',
        'journalctl', '-u', 'ipmi-vmware-bridge', 
        '-f', '--no-pager'
    ]
    
    try:
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        print("🎯 Monitoring OpenShift IPMI calls...")
        
        line_count = 0
        power_related_count = 0
        
        for line in process.stdout:
            line_count += 1
            line_clean = line.strip()
            
            # Check if this is a power-related command
            is_power_related = any(cmd.lower() in line_clean.lower() for cmd in power_commands)
            
            if 'skinner-worker-2' in line_clean:
                if is_power_related:
                    power_related_count += 1
                    print(f"🔋 POWER: {line_clean}")
                else:
                    print(f"📨 INFO:  {line_clean}")
        
        print("\n" + "=" * 60)
        print(f"📊 SUMMARY:")
        print(f"   Total lines processed: {line_count}")
        print(f"   Power-related commands: {power_related_count}")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n⏹️ Monitoring stopped by user")
    except Exception as e:
        print(f"❌ Error monitoring logs: {e}")
    finally:
        if 'process' in locals():
            process.terminate()

def test_specific_ipmi_command():
    """Test specific IPMI commands that OpenShift might be using"""
    
    print("\n🧪 Testing specific IPMI commands...")
    
    # Test chassis status specifically
    test_commands = [
        {
            'name': 'Chassis Power Status',
            'cmd': ['ipmitool', '-I', 'lanplus', '-H', '192.168.86.168', '-p', '627', 
                   '-U', 'admin', '-P', 'password', 'chassis', 'power', 'status']
        },
        {
            'name': 'Chassis Status',
            'cmd': ['ipmitool', '-I', 'lanplus', '-H', '192.168.86.168', '-p', '627', 
                   '-U', 'admin', '-P', 'password', 'chassis', 'status']
        }
    ]
    
    for test in test_commands:
        print(f"\n🔍 Testing: {test['name']}")
        try:
            result = subprocess.run(
                test['cmd'], 
                capture_output=True, 
                text=True, 
                timeout=5
            )
            print(f"   Return code: {result.returncode}")
            print(f"   Stdout: {result.stdout}")
            if result.stderr:
                print(f"   Stderr: {result.stderr}")
        except subprocess.TimeoutExpired:
            print("   ❌ Command timed out")
        except Exception as e:
            print(f"   ❌ Error: {e}")

def main():
    print("🚀 IPMI Power Status Debug Tool")
    print("=" * 60)
    
    # First monitor the logs
    monitor_logs_for_power_commands()
    
    # Then test specific commands  
    test_specific_ipmi_command()
    
    print("\n✅ Debug session completed!")

if __name__ == "__main__":
    main()
