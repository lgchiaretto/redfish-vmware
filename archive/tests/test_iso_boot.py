#!/usr/bin/env python3
"""
Test script for ISO boot functionality via IPMI
"""

import sys
import os
import time
import socket
import struct
import logging

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ipmi_server import BootDevice

# IPMI command constants
IPMI_SET_BOOT_OPTIONS = 0x08
IPMI_GET_BOOT_OPTIONS = 0x09
IPMI_CHASSIS_CONTROL = 0x02

# Chassis control commands
POWER_OFF = 0x00
POWER_ON = 0x01
HARD_RESET = 0x03

def send_ipmi_command(server_ip, server_port, netfn, command, payload=None):
    """Send IPMI command to server"""
    try:
        # Create socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5.0)
        
        # Build IPMI request
        if payload is None:
            payload = []
        
        request = bytes([
            0x00,  # Auth type
            0x00,  # Sequence
            0x00,  # Session ID
            len(payload) + 2,  # Message length
            netfn,  # NetFn
            command  # Command
        ]) + bytes(payload)
        
        print(f"Sending command: NetFn=0x{netfn:02x}, Cmd=0x{command:02x}, Payload={[hex(b) for b in payload]}")
        
        # Send request
        sock.sendto(request, (server_ip, server_port))
        
        # Receive response
        response, addr = sock.recvfrom(1024)
        sock.close()
        
        print(f"Response received: {[hex(b) for b in response]}")
        return response
        
    except Exception as e:
        print(f"Error sending IPMI command: {e}")
        return None

def set_boot_device(server_ip, server_port, boot_device, persistent=False):
    """Set boot device via IPMI"""
    print(f"\n=== Setting Boot Device ===")
    print(f"Target: {server_ip}:{server_port}")
    print(f"Boot device: 0x{boot_device:02x}")
    print(f"Persistent: {persistent}")
    
    # Parameter 5 = Boot device selector
    param = 0x05
    
    # Construct boot data byte
    boot_data = boot_device
    if persistent:
        boot_data |= 0x40  # Set persistent bit
    boot_data |= 0x80  # Set valid bit
    
    payload = [param, boot_data]
    
    response = send_ipmi_command(server_ip, server_port, 0x00, IPMI_SET_BOOT_OPTIONS, payload)
    
    if response and len(response) >= 7:
        completion_code = response[6]
        if completion_code == 0x00:
            print("✅ Boot device set successfully")
            return True
        else:
            print(f"❌ Boot device set failed: completion code 0x{completion_code:02x}")
    else:
        print("❌ No response or invalid response")
    
    return False

def get_boot_device(server_ip, server_port):
    """Get current boot device via IPMI"""
    print(f"\n=== Getting Boot Device ===")
    print(f"Target: {server_ip}:{server_port}")
    
    # Parameter 5 = Boot device selector
    param = 0x05
    payload = [param, 0x00, 0x00]  # param, set_selector, block_selector
    
    response = send_ipmi_command(server_ip, server_port, 0x00, IPMI_GET_BOOT_OPTIONS, payload)
    
    if response and len(response) >= 10:
        completion_code = response[6]
        if completion_code == 0x00:
            boot_data = response[9]
            device = boot_data & 0x3C
            persistent = (boot_data & 0x40) != 0
            valid = (boot_data & 0x80) != 0
            
            print(f"✅ Current boot device: 0x{device:02x}")
            print(f"   Persistent: {persistent}")
            print(f"   Valid: {valid}")
            
            # Decode device type
            device_name = "Unknown"
            if device == BootDevice.NO_OVERRIDE.value:
                device_name = "No Override"
            elif device == BootDevice.HDD.value:
                device_name = "Hard Disk"
            elif device == BootDevice.CD_DVD.value:
                device_name = "CD/DVD"
            elif device == BootDevice.PXE.value:
                device_name = "PXE"
            
            print(f"   Device type: {device_name}")
            return device
        else:
            print(f"❌ Get boot device failed: completion code 0x{completion_code:02x}")
    else:
        print("❌ No response or invalid response")
    
    return None

def power_control(server_ip, server_port, action):
    """Send power control command"""
    print(f"\n=== Power Control ===")
    print(f"Target: {server_ip}:{server_port}")
    
    action_names = {
        POWER_OFF: "Power Off",
        POWER_ON: "Power On", 
        HARD_RESET: "Hard Reset"
    }
    
    print(f"Action: {action_names.get(action, f'Unknown (0x{action:02x})')}")
    
    payload = [action]
    response = send_ipmi_command(server_ip, server_port, 0x00, IPMI_CHASSIS_CONTROL, payload)
    
    if response and len(response) >= 7:
        completion_code = response[6]
        if completion_code == 0x00:
            print("✅ Power control command successful")
            return True
        else:
            print(f"❌ Power control failed: completion code 0x{completion_code:02x}")
    else:
        print("❌ No response or invalid response")
    
    return False

def test_iso_boot_sequence(server_ip="127.0.0.1", server_port=623):
    """Test complete ISO boot sequence"""
    print("🔬 IPMI ISO Boot Test")
    print("=" * 50)
    
    # Test 1: Get current boot device
    print("\n📋 Test 1: Get current boot device")
    current_device = get_boot_device(server_ip, server_port)
    
    # Test 2: Set boot to CD/DVD
    print("\n📋 Test 2: Set boot device to CD/DVD")
    success = set_boot_device(server_ip, server_port, BootDevice.CD_DVD.value, persistent=False)
    
    if success:
        time.sleep(1)
        
        # Verify the setting
        print("\n📋 Test 3: Verify CD/DVD boot setting")
        device = get_boot_device(server_ip, server_port)
        
        if device == BootDevice.CD_DVD.value:
            print("✅ CD/DVD boot setting verified")
        else:
            print("❌ CD/DVD boot setting not applied correctly")
    
    # Test 3: Power cycle to test boot
    print("\n📋 Test 4: Power cycle VM (this will attempt to boot from ISO)")
    print("⚠️  Warning: This will restart the VM!")
    
    confirm = input("Continue with power cycle? (y/N): ")
    if confirm.lower() == 'y':
        # Power off first
        power_control(server_ip, server_port, POWER_OFF)
        time.sleep(3)
        
        # Power on
        power_control(server_ip, server_port, POWER_ON)
        print("🔄 VM should now boot from ISO (if mounted)")
    else:
        print("⏭️  Skipping power cycle")
    
    # Test 4: Reset to HDD boot
    print("\n📋 Test 5: Reset boot device to Hard Disk")
    success = set_boot_device(server_ip, server_port, BootDevice.HDD.value, persistent=False)
    
    if success:
        time.sleep(1)
        
        # Verify the setting
        print("\n📋 Test 6: Verify HDD boot setting")
        device = get_boot_device(server_ip, server_port)
        
        if device == BootDevice.HDD.value:
            print("✅ HDD boot setting verified")
        else:
            print("❌ HDD boot setting not applied correctly")
    
    # Test 5: Clear boot override
    print("\n📋 Test 7: Clear boot override (no override)")
    success = set_boot_device(server_ip, server_port, BootDevice.NO_OVERRIDE.value, persistent=False)
    
    print("\n🏁 ISO Boot Test Complete!")

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test IPMI ISO boot functionality")
    parser.add_argument("--host", default="127.0.0.1", help="IPMI server host")
    parser.add_argument("--port", type=int, default=623, help="IPMI server port")
    parser.add_argument("--device", type=str, help="Set specific boot device (hdd, cdrom, pxe, none)")
    parser.add_argument("--persistent", action="store_true", help="Make boot setting persistent")
    parser.add_argument("--get", action="store_true", help="Only get current boot device")
    parser.add_argument("--power", choices=["on", "off", "reset"], help="Power control action")
    
    args = parser.parse_args()
    
    if args.get:
        get_boot_device(args.host, args.port)
    elif args.device:
        device_map = {
            "none": BootDevice.NO_OVERRIDE.value,
            "hdd": BootDevice.HDD.value,
            "cdrom": BootDevice.CD_DVD.value,
            "pxe": BootDevice.PXE.value
        }
        
        if args.device in device_map:
            set_boot_device(args.host, args.port, device_map[args.device], args.persistent)
        else:
            print(f"Invalid device: {args.device}")
            print("Valid devices: none, hdd, cdrom, pxe")
    elif args.power:
        power_map = {
            "off": POWER_OFF,
            "on": POWER_ON,
            "reset": HARD_RESET
        }
        power_control(args.host, args.port, power_map[args.power])
    else:
        test_iso_boot_sequence(args.host, args.port)

if __name__ == "__main__":
    main()
