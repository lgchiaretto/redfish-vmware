#!/usr/bin/env python3
"""
Simplified IPMI Server - Direct Chassis Command Support
Accepts chassis commands without session establishment for OpenShift compatibility
"""

import socket
import struct
import logging
import threading
import time
from typing import Dict, Optional, Tuple

class SimpleIPMIServer:
    def __init__(self, port: int = 623):
        self.port = port
        self.running = False
        self.socket = None
        
        # VM mappings
        self.vm_mapping = {
            '192.168.86.50': 'skinner-master-0',
            '192.168.86.51': 'skinner-master-1', 
            '192.168.86.52': 'skinner-master-2',
            '192.168.86.168': 'skinner-master-0',  # Local testing
            '192.168.110.50': 'skinner-master-0',
            '192.168.110.51': 'skinner-master-1',
            '192.168.110.52': 'skinner-master-2'
        }
        
        # Setup logging
        self.logger = logging.getLogger('simple_ipmi')
        self.logger.setLevel(logging.DEBUG)
        
    def start(self):
        """Start the simplified IPMI server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind(('0.0.0.0', self.port))
            
            self.running = True
            self.logger.info(f"Simple IPMI server started on port {self.port}")
            
            while self.running:
                try:
                    self.socket.settimeout(1.0)
                    data, addr = self.socket.recvfrom(1024)
                    
                    # Process in separate thread
                    thread = threading.Thread(target=self.handle_packet, args=(data, addr))
                    thread.daemon = True
                    thread.start()
                    
                except socket.timeout:
                    continue
                except socket.error as e:
                    if self.running:
                        self.logger.error(f"Socket error: {e}")
                        break
                        
        except Exception as e:
            self.logger.error(f"Error starting server: {e}")
        finally:
            self.stop()
            
    def stop(self):
        """Stop the server"""
        self.running = False
        if self.socket:
            self.socket.close()
        self.logger.info("Simple IPMI server stopped")
        
    def handle_packet(self, data: bytes, addr: Tuple[str, int]):
        """Handle incoming IPMI packet"""
        try:
            client_ip = addr[0]
            vm_name = self.vm_mapping.get(client_ip)
            
            self.logger.debug(f"Packet from {addr}: {data.hex()}")
            
            if not vm_name:
                self.logger.warning(f"No VM mapped for IP {client_ip}")
                return
                
            # Check for RMCP
            if len(data) >= 4 and data[0] == 0x06:
                if data[3] == 0x06:  # ASF Ping
                    self.send_asf_pong(addr)
                    return
                elif data[3] == 0x07:  # IPMI
                    self.handle_ipmi_packet(data, addr, vm_name)
                    return
                    
        except Exception as e:
            self.logger.error(f"Error handling packet: {e}")
            
    def send_asf_pong(self, addr: Tuple[str, int]):
        """Send ASF pong response"""
        try:
            # Simple ASF pong
            pong = bytes([0x06, 0x00, 0xFF, 0x06, 0x00, 0x00, 0x11, 0xBE, 0x40, 0x00, 0x00, 0x00])
            self.socket.sendto(pong, addr)
            self.logger.debug(f"Sent ASF pong to {addr}")
        except Exception as e:
            self.logger.error(f"Error sending ASF pong: {e}")
            
    def handle_ipmi_packet(self, data: bytes, addr: Tuple[str, int], vm_name: str):
        """Handle IPMI over RMCP packet"""
        try:
            # Skip RMCP header (4 bytes)
            if len(data) < 14:
                return
                
            rmcp_data = data[4:]
            
            # Parse session wrapper
            auth_type = rmcp_data[0]
            seq = struct.unpack('<I', rmcp_data[1:5])[0]
            session_id = struct.unpack('<I', rmcp_data[5:9])[0]
            msg_len = rmcp_data[9]
            
            if len(rmcp_data) < 10 + msg_len:
                return
                
            msg_data = rmcp_data[10:10+msg_len]
            
            if len(msg_data) < 6:
                return
                
            # Parse IPMI message
            target_addr = msg_data[0]
            netfn_lun = msg_data[1]
            header_checksum = msg_data[2]
            source_addr = msg_data[3]
            seq_lun = msg_data[4]
            cmd = msg_data[5]
            
            netfn = (netfn_lun >> 2) & 0x3f
            payload = msg_data[6:-1] if len(msg_data) > 6 else []
            
            self.logger.debug(f"IPMI: netfn=0x{netfn:02x}, cmd=0x{cmd:02x}, vm={vm_name}")
            
            # Handle commands
            response_data = None
            
            if netfn == 0x06:  # App commands
                if cmd == 0x38:  # Get Channel Auth Capabilities
                    response_data = self.handle_auth_capabilities(payload)
                elif cmd == 0x39:  # Get Session Challenge  
                    response_data = self.handle_session_challenge(payload)
                elif cmd == 0x3A:  # Activate Session
                    response_data = self.handle_activate_session(payload)
                elif cmd == 0x01:  # Get Device ID
                    response_data = self.handle_device_id()
                    
            elif netfn == 0x00:  # Chassis commands - accept directly!
                if cmd == 0x01:  # Get Chassis Status
                    response_data = self.get_power_status(vm_name)
                elif cmd == 0x02:  # Chassis Control
                    if len(payload) >= 1:
                        response_data = self.chassis_control(payload[0], vm_name)
                        
            # Send response if we have one
            if response_data is not None:
                self.send_response(addr, target_addr, source_addr, netfn, seq_lun, cmd, response_data)
                
        except Exception as e:
            self.logger.error(f"Error handling IPMI packet: {e}")
            
    def handle_auth_capabilities(self, payload: bytes) -> bytes:
        """Return simplified auth capabilities"""
        channel = payload[0] if len(payload) > 0 else 0x0E
        priv_level = payload[1] if len(payload) > 1 else 0x04
        
        self.logger.debug(f"Auth capabilities request: channel=0x{channel:02x}, priv=0x{priv_level:02x}")
        
        # Try the simplest possible response that should work
        response = [
            channel & 0x0F,  # Channel number  
            0x01,  # Auth types: None only (bit 0)
            0x02,  # Auth status: login available (but not required for none auth)
            0x00,  # Extended capabilities: basic
            0x00, 0x00, 0x00, 0x00  # OEM data
        ]
        
        self.logger.debug(f"Auth capabilities response: {[hex(x) for x in response]}")
        return bytes(response)
        
    def handle_session_challenge(self, payload: bytes) -> bytes:
        """Return session challenge"""
        # Simple challenge for compatibility
        session_id = 0x12345678
        challenge = bytes([0x00] * 16)
        
        response = []
        response.extend(struct.pack('<I', session_id))
        response.extend(challenge)
        return bytes(response)
        
    def handle_activate_session(self, payload: bytes) -> bytes:
        """Activate session"""
        auth_type = payload[0] if len(payload) > 0 else 0x00
        
        response = [
            auth_type,  # Auth type
            0x78, 0x56, 0x34, 0x12,  # Session ID (little endian)
            0x01, 0x00, 0x00, 0x00,  # Initial sequence  
            0x04  # Max privilege level
        ]
        return bytes(response)
        
    def handle_device_id(self) -> bytes:
        """Return device ID"""
        response = [
            0x20,  # Device ID
            0x81,  # Device revision
            0x00, 0x01,  # Firmware revision
            0x02,  # IPMI version
            0x00,  # Additional device support
            0x00, 0x00, 0x00,  # Manufacturer ID
            0x00, 0x00,  # Product ID
            0x00, 0x00, 0x00, 0x00  # Aux firmware revision
        ]
        return bytes(response)
        
    def get_power_status(self, vm_name: str) -> bytes:
        """Get chassis power status"""
        self.logger.info(f"Getting power status for VM: {vm_name}")
        
        # For now, always return "power on"
        # TODO: Integrate with VMware API
        response = [
            0x01,  # Current power state: on
            0x00,  # Last power event
            0x00   # Misc chassis state
        ]
        
        self.logger.info(f"Power status for {vm_name}: ON")
        return bytes(response)
        
    def chassis_control(self, control: int, vm_name: str) -> bytes:
        """Execute chassis control command"""
        self.logger.info(f"Chassis control 0x{control:02x} for VM: {vm_name}")
        
        # 0x00 = power down
        # 0x01 = power up  
        # 0x02 = power cycle
        # 0x03 = hard reset
        # 0x05 = diagnostic interrupt (NMI)
        # 0x06 = soft shutdown via ACPI
        
        if control == 0x00:
            action = "Power Down"
        elif control == 0x01:
            action = "Power Up"
        elif control == 0x02:
            action = "Power Cycle"
        elif control == 0x03:
            action = "Hard Reset"
        else:
            action = f"Unknown (0x{control:02x})"
            
        self.logger.info(f"Chassis action for {vm_name}: {action}")
        
        # TODO: Integrate with VMware API to actually control the VM
        
        # Return success
        return bytes([])  # Empty response means success
        
    def send_response(self, addr: Tuple[str, int], orig_target: int, orig_source: int, 
                     orig_netfn: int, orig_seq_lun: int, cmd: int, response_data: bytes):
        """Send IPMI response"""
        try:
            # Build response
            resp_netfn = (orig_netfn | 0x01) << 2  # Set response bit
            target_addr = orig_source
            source_addr = orig_target
            netfn_lun = resp_netfn
            seq_lun = orig_seq_lun
            completion_code = 0x00  # Success
            
            # Calculate header checksum
            header_checksum = (0x100 - (target_addr + netfn_lun)) & 0xff
            
            # Build message
            msg_payload = [target_addr, netfn_lun, header_checksum, source_addr, seq_lun, cmd, completion_code]
            msg_payload.extend(response_data)
            
            # Calculate data checksum
            data_checksum = (0x100 - sum(msg_payload[3:])) & 0xff
            msg_payload.append(data_checksum)
            
            # Build RMCP packet
            rmcp_header = bytes([0x06, 0x00, 0xFF, 0x07])  # RMCP header
            session_wrapper = bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, len(msg_payload)])
            
            response_packet = rmcp_header + session_wrapper + bytes(msg_payload)
            
            self.socket.sendto(response_packet, addr)
            self.logger.debug(f"Sent response to {addr}: {response_packet.hex()}")
            
        except Exception as e:
            self.logger.error(f"Error sending response: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    server = SimpleIPMIServer()
    try:
        server.start()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.stop()
