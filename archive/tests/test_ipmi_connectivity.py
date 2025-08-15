#!/usr/bin/env python3
"""
Simple IPMI test script to check basic connectivity
"""

import socket
import struct
import time

def test_ipmi_connectivity(host, port=623):
    """Test basic UDP connectivity to IPMI server"""
    print(f"Testing IPMI connectivity to {host}:{port}")
    
    try:
        # Create UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5.0)
        
        # Simple ping packet
        ping_packet = b'\x06\x00\xff\x07\x00\x00\x00\x00\x00\x00\x00\x00\x00\x09\x20\x18\xc8\x81\x00\x38\x8e\x04\xb5'
        
        print(f"Sending ping packet: {ping_packet.hex()}")
        sock.sendto(ping_packet, (host, port))
        
        # Try to receive response
        response, addr = sock.recvfrom(1024)
        print(f"Received response from {addr}: {response.hex()}")
        
        sock.close()
        return True
        
    except socket.timeout:
        print("❌ Timeout - no response received")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_chassis_status(host, port=623):
    """Test chassis status command"""
    print(f"\nTesting chassis status command to {host}:{port}")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5.0)
        
        # Chassis status command
        # This is a simplified IPMI packet for chassis status
        packet = bytes([
            0x06,  # RMCP version
            0x00,  # Reserved
            0xff,  # Sequence number
            0x07,  # Message class
            # IPMI Session Header
            0x00, 0x00, 0x00, 0x00,  # Session ID
            0x00, 0x00, 0x00, 0x00,  # Sequence number
            # IPMI Message
            0x20,  # Target address
            0x18,  # NetFn (0x06 << 2) | LUN (0x00)
            0x00,  # Checksum (simplified)
            0x81,  # Source address
            0x00,  # Sequence number
            0x01,  # Command (Get Chassis Status)
            0x00   # Checksum
        ])
        
        print(f"Sending chassis status packet: {packet.hex()}")
        sock.sendto(packet, (host, port))
        
        response, addr = sock.recvfrom(1024)
        print(f"✅ Received response from {addr}: {response.hex()}")
        
        sock.close()
        return True
        
    except socket.timeout:
        print("❌ Timeout - no response received")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    import sys
    
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 623
    
    print("🔬 IPMI Connectivity Test")
    print("=" * 40)
    
    # Test 1: Basic connectivity
    if test_ipmi_connectivity(host, port):
        print("✅ Basic UDP connectivity working")
    else:
        print("❌ Basic UDP connectivity failed")
        sys.exit(1)
    
    # Test 2: Chassis status
    if test_chassis_status(host, port):
        print("✅ Chassis status command working")
    else:
        print("❌ Chassis status command failed")
        sys.exit(1)
    
    print("\n🎉 All tests passed!")
