#!/usr/bin/env python3
"""
Direct Chassis IPMI Server - No Authentication Required
This server bypasses the auth capabilities loop and accepts chassis commands directly
"""

import socket
import struct
import logging
import threading
import time

class DirectChassisIPMI:
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
            '192.168.110.50': 'skinner-master-0',  # OpenShift
            '192.168.110.51': 'skinner-master-1',
            '192.168.110.52': 'skinner-master-2'
        }
        
        # Setup logging
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger('direct_chassis')
        
    def start(self):
        """Start the server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind(('0.0.0.0', self.port))
            
            self.running = True
            self.logger.info(f"Direct Chassis IPMI server started on port {self.port}")
            
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
        self.logger.info("Direct Chassis IPMI server stopped")
        
    def handle_packet(self, data: bytes, addr):
        """Handle incoming packet"""
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
                    self.handle_ipmi(data, addr, vm_name)
                    return
                    
        except Exception as e:
            self.logger.error(f"Error handling packet: {e}")
            
    def send_asf_pong(self, addr):
        """Send ASF pong"""
        try:
            pong = bytes([0x06, 0x00, 0xFF, 0x06, 0x00, 0x00, 0x11, 0xBE, 0x40, 0x00, 0x00, 0x00])
            self.socket.sendto(pong, addr)
            self.logger.debug(f"Sent ASF pong to {addr}")
        except Exception as e:
            self.logger.error(f"Error sending ASF pong: {e}")
            
    def handle_ipmi(self, data: bytes, addr, vm_name: str):
        """Handle IPMI packet with direct chassis support"""
        try:
            # Parse RMCP + IPMI headers
            if len(data) < 20:
                return
                
            # Skip RMCP header (4 bytes) + session wrapper (10 bytes)
            offset = 14
            if len(data) <= offset:
                return
                
            msg_len = data[13]
            msg_data = data[offset:offset+msg_len]
            
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
            
            self.logger.info(f"IPMI Command: NetFn=0x{netfn:02x}, Cmd=0x{cmd:02x}, VM={vm_name}")
            
            # Process commands
            response_data = None
            
            if netfn == 0x06 and cmd == 0x38:  # Get Channel Auth Capabilities
                # Return simple capabilities that don't require sessions
                response_data = bytes([
                    0x0E,  # Channel number
                    0x01,  # Auth types: None only
                    0x00,  # Auth status: No login required 
                    0x00,  # Extended capabilities
                    0x00, 0x00, 0x00, 0x00  # OEM data
                ])
                self.logger.debug("Responded to Auth Capabilities")
                
            elif netfn == 0x00:  # Chassis commands - handle directly!
                self.logger.info(f"🎯 CHASSIS COMMAND DETECTED: 0x{cmd:02x} for {vm_name}")
                
                if cmd == 0x01:  # Get Chassis Status
                    response_data = bytes([
                        0x01,  # Power state: ON
                        0x00,  # Last power event
                        0x00   # Misc chassis state  
                    ])
                    self.logger.info(f"✅ Chassis Status: {vm_name} = POWER ON")
                    
                elif cmd == 0x02:  # Chassis Control
                    if len(payload) >= 1:
                        control = payload[0]
                        actions = {
                            0x00: "Power Down", 0x01: "Power Up", 0x02: "Power Cycle",
                            0x03: "Hard Reset", 0x05: "Diagnostic Interrupt", 
                            0x06: "Soft Shutdown"
                        }
                        action = actions.get(control, f"Unknown (0x{control:02x})")
                        self.logger.info(f"✅ Chassis Control: {vm_name} = {action}")
                        response_data = bytes([])  # Success
                    
            elif netfn == 0x06:  # Other App commands
                if cmd == 0x01:  # Get Device ID
                    response_data = bytes([
                        0x20, 0x81, 0x00, 0x01, 0x02, 0x00,
                        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
                    ])
                    
            # Send response if we have one
            if response_data is not None:
                self.send_response(addr, target_addr, source_addr, netfn, seq_lun, cmd, response_data)
            else:
                self.logger.warning(f"No handler for NetFn=0x{netfn:02x}, Cmd=0x{cmd:02x}")
                
        except Exception as e:
            self.logger.error(f"Error handling IPMI: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            
    def send_response(self, addr, orig_target, orig_source, orig_netfn, orig_seq_lun, cmd, response_data):
        """Send IPMI response"""
        try:
            # Build response message
            resp_netfn = (orig_netfn | 0x01) << 2  # Set response bit
            target_addr = orig_source
            source_addr = orig_target
            netfn_lun = resp_netfn
            seq_lun = orig_seq_lun
            completion_code = 0x00
            
            # Calculate header checksum
            header_checksum = (0x100 - (target_addr + netfn_lun)) & 0xff
            
            # Build message payload
            msg_payload = [target_addr, netfn_lun, header_checksum, source_addr, seq_lun, cmd, completion_code]
            msg_payload.extend(response_data)
            
            # Calculate data checksum
            data_checksum = (0x100 - sum(msg_payload[3:])) & 0xff
            msg_payload.append(data_checksum)
            
            # Build RMCP packet
            rmcp_header = bytes([0x06, 0x00, 0xFF, 0x07])
            session_wrapper = bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, len(msg_payload)])
            
            response_packet = rmcp_header + session_wrapper + bytes(msg_payload)
            
            self.socket.sendto(response_packet, addr)
            self.logger.debug(f"Sent response to {addr}: {response_packet.hex()}")
            
        except Exception as e:
            self.logger.error(f"Error sending response: {e}")

if __name__ == "__main__":
    server = DirectChassisIPMI()
    try:
        server.start()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.stop()
