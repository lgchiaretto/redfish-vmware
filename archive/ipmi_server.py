#!/usr/bin/env python3
"""
Simulated IPMI server that translates IPMI commands to VMware operations
"""

import logging
import socket
import threading
import struct
from enum import Enum

class IPMICommand(Enum):
    """Main IPMI commands"""
    CHASSIS_CONTROL = 0x02
    GET_CHASSIS_STATUS = 0x01
    SET_SYSTEM_BOOT_OPTIONS = 0x08
    GET_SYSTEM_BOOT_OPTIONS = 0x09
    
class IPMIAppCommand(Enum):
    """Application NetFn commands"""
    GET_DEVICE_ID = 0x01
    GET_CHANNEL_AUTH_CAPABILITIES = 0x38
    GET_SESSION_CHALLENGE = 0x39
    ACTIVATE_SESSION = 0x3A
    SET_SESSION_PRIVILEGE_LEVEL = 0x3B
    CLOSE_SESSION = 0x3C

class BootDevice(Enum):
    """Boot device options"""
    NO_OVERRIDE = 0x00
    PXE = 0x04
    HDD = 0x08
    SAFE_MODE_HDD = 0x0C
    DIAG_PARTITION = 0x10
    CD_DVD = 0x14
    BIOS_SETUP = 0x18
    REMOTE_FLOPPY = 0x1C
    REMOTE_CD_DVD = 0x20
    PRIMARY_REMOTE_MEDIA = 0x24

class ChassisControl(Enum):
    """Chassis control subcommands"""
    POWER_DOWN = 0x00
    POWER_UP = 0x01
    POWER_CYCLE = 0x02
    HARD_RESET = 0x03
    PULSE_DIAGNOSTIC_INTERRUPT = 0x04
    SOFT_SHUTDOWN = 0x05

class IPMIServer:
    def __init__(self, config, vmware_client):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.vmware_client = vmware_client
        
        # Server settings
        self.listen_address = config.get('ipmi', 'listen_address', fallback='0.0.0.0')
        self.listen_port = config.getint('ipmi', 'listen_port', fallback=623)
        
        # IP -> VM mapping
        self.vm_mapping = {}
        self.load_vm_mapping()
        
        # Boot options per VM
        self.boot_options = {}
        
        # Session management
        self.sessions = {}  # client_addr -> session_data
        self.session_id_counter = 1
        self.current_client_ip = None
        self.current_client_port = None
        
        # UDP socket for IPMI
        self.socket = None
        self.running = False
    
    def load_vm_mapping(self):
        """Load IP to VM mapping"""
        try:
            if self.config.has_section('vm_mapping'):
                for ip, vm_name in self.config.items('vm_mapping'):
                    self.vm_mapping[ip] = vm_name
                    self.logger.info(f"Mapping: {ip} -> {vm_name}")
        except Exception as e:
            self.logger.warning(f"Error loading VM mapping: {e}")
    
    def start(self):
        """Start IPMI server"""
        try:
            self.logger.info(f"Starting IPMI server on {self.listen_address}:{self.listen_port}")
            
            # Create UDP socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            try:
                self.socket.bind((self.listen_address, self.listen_port))
            except PermissionError:
                raise PermissionError(f"Permission denied binding to port {self.listen_port}. "
                                    f"Port {self.listen_port} requires root privileges. "
                                    f"Consider using a port > 1024 or running as root.")
            except OSError as e:
                if e.errno == 98:  # Address already in use
                    raise OSError(f"Port {self.listen_port} is already in use")
                raise
            
            self.running = True
            self.logger.info("IPMI server started successfully")
            
            # Main loop
            while self.running:
                try:
                    # Set socket timeout to allow checking self.running periodically
                    self.socket.settimeout(1.0)
                    data, addr = self.socket.recvfrom(1024)
                    self.logger.debug(f"Received from {addr}: {data.hex()}")
                    
                    # Process in separate thread
                    thread = threading.Thread(
                        target=self.handle_request,
                        args=(data, addr)
                    )
                    thread.daemon = True
                    thread.start()
                    
                except socket.timeout:
                    # Timeout is expected, just continue to check self.running
                    continue
                except socket.error as e:
                    if self.running:
                        self.logger.error(f"Socket error: {e}")
                        break
                        
        except Exception as e:
            self.logger.error(f"Error starting IPMI server: {e}")
            raise
        finally:
            self.stop()
    
    def stop(self):
        """Stop IPMI server"""
        self.running = False
        if self.socket:
            self.socket.close()
        self.logger.info("IPMI server stopped")
    
    def handle_request(self, data, addr):
        """Process an IPMI request"""
        try:
            # Store current client info for session management
            self.current_client_ip = addr[0]
            self.current_client_port = addr[1]
            
            self.logger.debug(f"Received from {addr}: {data.hex()}")
            self.logger.debug(f"Packet length: {len(data)}, bytes: {[hex(b) for b in data[:8]]}")
            self.logger.debug(f"Processing request from {addr[0]}:{addr[1]}")
            
            # Check for ASF ping (class 0x06) - these don't seem to be used by OpenShift
            if len(data) >= 4 and data[0] == 0x06 and data[3] == 0x06:
                self.logger.debug("Received ASF ping, sending pong")
                self.send_rmcp_pong(addr)
                return
            
            # Check for IPMI over RMCP (class 0x07)
            if len(data) >= 4 and data[0] == 0x06 and data[3] == 0x07:
                self.logger.debug("Processing IPMI over RMCP packet")
                self.handle_ipmi_packet(data, addr)
                return
            
            # Log any unexpected packets
            self.logger.warning(f"Received unexpected packet from {addr}: {data.hex()}")
            
            # Legacy direct IPMI handling for backward compatibility
            client_ip = addr[0]
            vm_name = self.vm_mapping.get(client_ip)
            
            if not vm_name:
                self.logger.warning(f"No VM mapped for IP {client_ip}")
                return
            
            # Parse simplified IPMI command
            if len(data) < 6:
                self.logger.warning("IPMI command too short")
                return
            
            if len(data) >= 6:
                netfn = data[4]
                command = data[5]
                
                self.logger.info(f"Legacy NetFn: 0x{netfn:02x}, Command: 0x{command:02x}, VM: {vm_name}")
                
                # Process command
                response = self.process_command(netfn, command, data[6:], vm_name)
                
                if response:
                    # Send response
                    self.send_response(addr, response)
                    
        except Exception as e:
            self.logger.error(f"Error processing request: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            
    def handle_ipmi_packet(self, data, addr):
        """Handle IPMI over RMCP packet"""
        try:
            if len(data) < 4:
                return
                
            # RMCP header: version(1) + reserved(1) + sequence(1) + class(1)
            rmcp_version = data[0]
            rmcp_reserved = data[1] 
            rmcp_sequence = data[2]
            rmcp_class = data[3]
            
            if rmcp_class != 0x07:  # IPMI class
                return
                
            # IPMI session header starts at offset 4
            if len(data) < 10:  # Minimum IPMI packet size
                return
                
            auth_type = data[4]
            session_sequence = struct.unpack('>I', data[5:9])[0]
            session_id = struct.unpack('>I', data[9:13])[0]
            
            self.logger.debug(f"IPMI: auth_type=0x{auth_type:02x}, seq={session_sequence}, session_id=0x{session_id:08x}")
            
            # For auth_type=0 (none), message starts at offset 13
            if auth_type == 0x00:
                if len(data) < 14:
                    return
                    
                msg_len = data[13]
                if len(data) < 14 + msg_len:
                    return
                    
                # IPMI message: target_addr(1) + netfn_lun(1) + checksum(1) + source_addr(1) + seq_lun(1) + cmd(1) + data + checksum(1)
                msg_data = data[14:14+msg_len]
                if len(msg_data) < 6:
                    return
                    
                target_addr = msg_data[0]
                netfn_lun = msg_data[1]
                header_checksum = msg_data[2]
                source_addr = msg_data[3]
                seq_lun = msg_data[4]
                command = msg_data[5]
                
                netfn = (netfn_lun >> 2) & 0x3f
                lun = netfn_lun & 0x03
                req_seq = (seq_lun >> 2) & 0x3f
                req_lun = seq_lun & 0x03
                
                payload = msg_data[6:-1] if len(msg_data) > 7 else []
                
                self.logger.debug(f"IPMI Message: netfn=0x{netfn:02x}, cmd=0x{command:02x}, payload={len(payload)} bytes")
                
                # Get VM name from IP mapping
                client_ip = addr[0]
                vm_name = self.vm_mapping.get(client_ip)
                
                if not vm_name:
                    self.logger.warning(f"No VM mapped for IP {client_ip}")
                    return
                
                # Process the command
                response_data = self.process_command(netfn, command, payload, vm_name)
                
                if response_data:
                    # Send IPMI response
                    self.send_ipmi_response(addr, rmcp_sequence, session_sequence, session_id, 
                                          target_addr, source_addr, netfn, req_seq, req_lun, 
                                          command, response_data)
                                          
            elif auth_type == 0x02:  # MD5 authentication
                # For compatibility, we'll accept MD5 but treat as none
                self.logger.debug("MD5 authentication requested, treating as none for compatibility")
                
                # Skip the auth code (16 bytes) and process normally
                if len(data) < 30:  # 13 (header) + 16 (auth) + 1 (length)
                    return
                    
                auth_code = data[13:29]  # Skip auth code
                msg_len = data[29]
                
                if len(data) < 30 + msg_len:
                    return
                    
                msg_data = data[30:30+msg_len]
                if len(msg_data) < 6:
                    return
                    
                target_addr = msg_data[0]
                netfn_lun = msg_data[1]
                header_checksum = msg_data[2]
                source_addr = msg_data[3]
                seq_lun = msg_data[4]
                command = msg_data[5]
                
                netfn = (netfn_lun >> 2) & 0x3f
                lun = netfn_lun & 0x03
                req_seq = (seq_lun >> 2) & 0x3f
                req_lun = seq_lun & 0x03
                
                payload = msg_data[6:-1] if len(msg_data) > 7 else []
                
                self.logger.debug(f"IPMI Message (MD5): netfn=0x{netfn:02x}, cmd=0x{command:02x}, payload={len(payload)} bytes")
                
                # Get VM name from IP mapping
                client_ip = addr[0]
                vm_name = self.vm_mapping.get(client_ip)
                
                if not vm_name:
                    self.logger.warning(f"No VM mapped for IP {client_ip}")
                    return
                
                # Process the command
                response_data = self.process_command(netfn, command, payload, vm_name)
                
                if response_data:
                    # Send IPMI response with MD5 (but empty auth code)
                    self.send_ipmi_response_with_auth(addr, rmcp_sequence, session_sequence, session_id, 
                                                    target_addr, source_addr, netfn, req_seq, req_lun, 
                                                    command, response_data, auth_type)
                                          
        except Exception as e:
            self.logger.error(f"Error handling IPMI packet: {e}")
            
    def send_ipmi_response_with_auth(self, addr, rmcp_seq, session_seq, session_id, 
                                   orig_target, orig_source, orig_netfn, orig_req_seq, orig_req_lun,
                                   command, response_data, auth_type):
        """Send IPMI response packet with authentication"""
        try:
            # Build IPMI response message
            # Response NetFn = Request NetFn | 0x01 (response bit)
            resp_netfn = (orig_netfn | 0x01) << 2
            
            # IPMI message structure
            target_addr = orig_source  # Response goes back to source
            netfn_lun = resp_netfn | orig_req_lun
            source_addr = orig_target
            seq_lun = (orig_req_seq << 2) | orig_req_lun
            completion_code = 0x00  # Success
            
            # Calculate header checksum (two's complement)
            header_checksum = (0x100 - (target_addr + netfn_lun)) & 0xff
            
            # Build message payload
            msg_payload = [target_addr, netfn_lun, header_checksum, source_addr, seq_lun, command, completion_code]
            msg_payload.extend(response_data)
            
            # Calculate data checksum
            data_checksum = (0x100 - sum(msg_payload[3:])) & 0xff
            msg_payload.append(data_checksum)
            
            msg_len = len(msg_payload)
            
            # Build IPMI session wrapper with authentication
            ipmi_packet = []
            ipmi_packet.append(auth_type)  # auth_type
            ipmi_packet.extend(struct.pack('>I', session_seq))  # session sequence
            ipmi_packet.extend(struct.pack('>I', session_id))   # session ID
            
            if auth_type == 0x02:  # MD5
                # Add dummy auth code (16 bytes of zeros)
                ipmi_packet.extend([0x00] * 16)
            
            ipmi_packet.append(msg_len)  # message length
            ipmi_packet.extend(msg_payload)
            
            # Build RMCP header
            rmcp_packet = []
            rmcp_packet.append(0x06)  # RMCP version
            rmcp_packet.append(0x00)  # reserved
            rmcp_packet.append(rmcp_seq)  # sequence number (echo back)
            rmcp_packet.append(0x07)  # class = IPMI
            rmcp_packet.extend(ipmi_packet)
            
            response = bytes(rmcp_packet)
            self.socket.sendto(response, addr)
            self.logger.debug(f"Sent IPMI response with auth to {addr}: {response.hex()}")
            
        except Exception as e:
            self.logger.error(f"Error sending IPMI response with auth: {e}")
            
    def send_ipmi_response(self, addr, rmcp_seq, session_seq, session_id, 
                          orig_target, orig_source, orig_netfn, orig_req_seq, orig_req_lun,
                          command, response_data):
        """Send IPMI response packet"""
        try:
            # Build IPMI response message
            # Response NetFn = Request NetFn | 0x01 (response bit)
            resp_netfn = (orig_netfn | 0x01) << 2
            
            # IPMI message structure
            target_addr = orig_source  # Response goes back to source
            netfn_lun = resp_netfn | orig_req_lun
            source_addr = orig_target
            seq_lun = (orig_req_seq << 2) | orig_req_lun
            completion_code = 0x00  # Success
            
            # Calculate header checksum (two's complement)
            header_checksum = (0x100 - (target_addr + netfn_lun)) & 0xff
            
            # Build message payload
            msg_payload = [target_addr, netfn_lun, header_checksum, source_addr, seq_lun, command, completion_code]
            msg_payload.extend(response_data)
            
            # Calculate data checksum
            data_checksum = (0x100 - sum(msg_payload[3:])) & 0xff
            msg_payload.append(data_checksum)
            
            msg_len = len(msg_payload)
            
            # Build IPMI session wrapper (auth_type = none)
            ipmi_packet = []
            ipmi_packet.append(0x00)  # auth_type = none
            ipmi_packet.extend(struct.pack('>I', session_seq))  # session sequence
            ipmi_packet.extend(struct.pack('>I', session_id))   # session ID
            ipmi_packet.append(msg_len)  # message length
            ipmi_packet.extend(msg_payload)
            
            # Build RMCP header
            rmcp_packet = []
            rmcp_packet.append(0x06)  # RMCP version
            rmcp_packet.append(0x00)  # reserved
            rmcp_packet.append(rmcp_seq)  # sequence number (echo back)
            rmcp_packet.append(0x07)  # class = IPMI
            rmcp_packet.extend(ipmi_packet)
            
            response = bytes(rmcp_packet)
            self.socket.sendto(response, addr)
            self.logger.debug(f"Sent IPMI response to {addr}: {response.hex()}")
            
        except Exception as e:
            self.logger.error(f"Error sending IPMI response: {e}")
    
    def send_rmcp_pong(self, addr):
        """Send RMCP pong response"""
        try:
            # RMCP pong response structure
            pong = bytes([
                0x06,  # RMCP version
                0x00,  # Reserved
                0xff,  # Sequence number (echo back)
                0x06,  # Message class (ASF)
                # ASF header
                0x00, 0x00, 0x11, 0xbe,  # Enterprise number (ASF)
                0x40,  # Message type (pong)
                0x00,  # Message tag
                0x00,  # Reserved
                0x10,  # Data length
                # Pong data
                0x00, 0x00, 0x11, 0xbe,  # Enterprise number
                0x00, 0x00, 0x00, 0x00,  # OEM defined
                0x80, 0x00, 0x00, 0x00,  # Supported entities (IPMI entity class)
                0x07, 0x00, 0x00, 0x00   # Supported interactions (RMCP security + presence ping)
            ])
            
            self.socket.sendto(pong, addr)
            self.logger.debug(f"RMCP pong sent to {addr}")
            
        except Exception as e:
            self.logger.error(f"Error sending RMCP pong: {e}")
    
    def process_command(self, netfn, command, payload, vm_name):
        """Process specific IPMI command"""
        try:
            # NetFn 0x00 = Chassis
            if netfn == 0x00:
                return self.process_chassis_command(command, payload, vm_name)
            
            # NetFn 0x04 = Sensor/Event
            elif netfn == 0x04:
                return self.process_sensor_command(command, payload, vm_name)
            
            # NetFn 0x06 = Application
            elif netfn == 0x06:
                return self.process_app_command(command, payload, vm_name)
            
            else:
                self.logger.warning(f"Unsupported NetFn: 0x{netfn:02x}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error processing command: {e}")
            return None
    
    def process_chassis_command(self, command, payload, vm_name):
        """Process chassis commands (power control)"""
        try:
            self.logger.debug(f"Chassis command: 0x{command:02x}, payload: {[hex(x) for x in payload]}")
            
            if command == IPMICommand.CHASSIS_CONTROL.value:
                if len(payload) >= 1:
                    control = payload[0]
                    return self.handle_chassis_control(control, vm_name)
            
            elif command == IPMICommand.GET_CHASSIS_STATUS.value:
                return self.handle_get_chassis_status(vm_name)
            
            elif command == 0x00:  # Sometimes sent as command 0x00
                # Treat as chassis status request
                self.logger.debug("Command 0x00 treated as chassis status")
                return self.handle_get_chassis_status(vm_name)
            
            elif command == IPMICommand.SET_SYSTEM_BOOT_OPTIONS.value:
                return self.handle_set_boot_options(payload, vm_name)
            
            elif command == IPMICommand.GET_SYSTEM_BOOT_OPTIONS.value:
                return self.handle_get_boot_options(payload, vm_name)
            
            else:
                self.logger.warning(f"Unsupported chassis command: 0x{command:02x}")
                return bytes([0xC1])  # Invalid command
                
        except Exception as e:
            self.logger.error(f"Error in chassis command: {e}")
            return bytes([0xFF])  # Unspecified error
    
    def handle_chassis_control(self, control, vm_name):
        """Execute chassis control (power)"""
        try:
            self.logger.info(f"Chassis control: 0x{control:02x} for VM {vm_name}")
            
            success = False
            
            if control == ChassisControl.POWER_UP.value:
                success = self.vmware_client.power_on_vm(vm_name)
                
            elif control == ChassisControl.POWER_DOWN.value:
                success = self.vmware_client.power_off_vm(vm_name)
                
            elif control == ChassisControl.POWER_CYCLE.value:
                # Power cycle = power off and on
                self.vmware_client.power_off_vm(vm_name)
                success = self.vmware_client.power_on_vm(vm_name)
                
            elif control == ChassisControl.HARD_RESET.value:
                success = self.vmware_client.reset_vm(vm_name)
                
            else:
                self.logger.warning(f"Unsupported chassis control: 0x{control:02x}")
            
            # Simple response: completion code
            return bytes([0x00 if success else 0xFF])
            
        except Exception as e:
            self.logger.error(f"Error in chassis control: {e}")
            return bytes([0xFF])  # Error completion code
    
    def handle_get_chassis_status(self, vm_name):
        """Get chassis status"""
        try:
            self.logger.debug(f"Getting chassis status for VM: {vm_name}")
            power_state = self.vmware_client.get_vm_power_state(vm_name)
            
            self.logger.debug(f"VM {vm_name} power state: {power_state}")
            
            # IPMI Chassis Status Response (5 bytes)
            # Byte 0: Current Power State
            #   bit 0: power is on
            #   bit 1: power overload
            #   bit 2: power interlock
            #   bit 3: power fault
            #   bit 4: power control fault
            #   bit 5: power restore policy
            #   bit 7-6: reserved
            # Byte 1: Last Power Event
            # Byte 2: Misc. Chassis State  
            # Byte 3: Front Panel Button Capabilities
            
            if power_state is None:
                self.logger.warning(f"Could not get power state for VM: {vm_name}")
                # Return default powered off state
                return bytes([0x00, 0x00, 0x00, 0x00])
            
            # Check if VM is powered on
            is_powered_on = str(power_state).lower() == 'poweredon'
            
            current_power_state = 0x01 if is_powered_on else 0x00
            last_power_event = 0x00  # No event
            misc_chassis_state = 0x00  # Default state
            front_panel_caps = 0x00  # No capabilities
            
            response = bytes([current_power_state, last_power_event, misc_chassis_state, front_panel_caps])
            
            self.logger.debug(f"Chassis status response: {[hex(x) for x in response]}")
            return response
            
        except Exception as e:
            self.logger.error(f"Error getting chassis status for {vm_name}: {e}")
            # Return error with default state
            return bytes([0x00, 0x00, 0x00, 0x00])
    
    def process_sensor_command(self, command, payload, vm_name):
        """Process sensor commands (simulated)"""
        # TODO: Implement simulated sensors based on VM metrics
        self.logger.debug(f"Sensor command: 0x{command:02x}")
        return bytes([0x00])  # OK for now
    
    def process_app_command(self, command, payload, vm_name):
        """Process application commands"""
        try:
            self.logger.debug(f"App command: 0x{command:02x}, payload: {len(payload)} bytes")
            
            if command == IPMIAppCommand.GET_DEVICE_ID.value:
                return self.handle_get_device_id()
            
            elif command == IPMIAppCommand.GET_CHANNEL_AUTH_CAPABILITIES.value:
                return self.handle_get_channel_auth_capabilities(payload)
            
            elif command == IPMIAppCommand.GET_SESSION_CHALLENGE.value:
                return self.handle_get_session_challenge(payload)
            
            elif command == IPMIAppCommand.ACTIVATE_SESSION.value:
                return self.handle_activate_session(payload)
            
            elif command == IPMIAppCommand.SET_SESSION_PRIVILEGE_LEVEL.value:
                return self.handle_set_session_privilege_level(payload)
            
            elif command == IPMIAppCommand.CLOSE_SESSION.value:
                return self.handle_close_session(payload)
            
            else:
                self.logger.debug(f"Unsupported app command: 0x{command:02x}")
                return bytes([0x00])  # OK for now
                
        except Exception as e:
            self.logger.error(f"Error in app command: {e}")
            return bytes([0xFF])  # Unspecified error
    
    def handle_get_device_id(self):
        """Return device ID information"""
        try:
            # IPMI Device ID response
            response = [
                0x20,  # Device ID
                0x81,  # Device revision & availability
                0x00,  # Firmware revision 1
                0x01,  # Firmware revision 2
                0x02,  # IPMI version (2.0)
                0x00,  # Additional device support
                0x00, 0x00, 0x00,  # Manufacturer ID (3 bytes)
                0x00, 0x00,  # Product ID (2 bytes)
                0x00, 0x00, 0x00, 0x00  # Aux firmware revision (4 bytes)
            ]
            return bytes(response)
        except Exception as e:
            self.logger.error(f"Error getting device ID: {e}")
            return bytes([0xFF])
    
    def handle_get_channel_auth_capabilities(self, payload):
        """Return channel authentication capabilities"""
        try:
            # Parse request
            channel = payload[0] if len(payload) > 0 else 0x0E  # Current channel
            priv_level = payload[1] if len(payload) > 1 else 0x04  # Admin level
            
            self.logger.debug(f"Get channel auth capabilities: channel=0x{channel:02x}, priv=0x{priv_level:02x}")
            
            # Response format per IPMI spec section 22.13
            # Byte 1: Channel number
            # Byte 2: Authentication type support  
            # Byte 3: Authentication status
            # Byte 4: Extended capabilities
            # Bytes 5-8: OEM auxiliary data
            response = [
                channel & 0x0F,  # Channel number (lower 4 bits)  
                0x01,  # Authentication type support: None only (bit 0)
                0x04,  # Authentication status: Non-null usernames enabled, no per-message auth
                0x01,  # Extended capabilities: IPMI v1.5 support
                0x00, 0x00, 0x00, 0x00  # OEM auxiliary data
            ]
            
            self.logger.debug(f"Channel auth response: {[hex(x) for x in response]}")
            return bytes(response)
        except Exception as e:
            self.logger.error(f"Error getting auth capabilities: {e}")
            return bytes([0xFF])
    
    # Also override to handle chassis commands without requiring session
    def process_chassis_command_directly(self, command, payload, vm_name):
        """Process chassis commands directly without session - for compatibility"""
        try:
            self.logger.info(f"Direct chassis command: 0x{command:02x}, VM: {vm_name}")
            
            if command == 0x01:  # Get Chassis Status
                return self.handle_get_chassis_status(vm_name)
            elif command == 0x02:  # Chassis Control
                if len(payload) >= 1:
                    control = payload[0]
                    return self.handle_chassis_control(control, vm_name)
            else:
                self.logger.warning(f"Unsupported direct chassis command: 0x{command:02x}")
                return bytes([0xC1])  # Invalid command
                
        except Exception as e:
            self.logger.error(f"Error in direct chassis command: {e}")
            return bytes([0xFF])  # Unspecified error
    
    def handle_get_session_challenge(self, payload):
        """Return session challenge for authentication"""
        try:
            if len(payload) < 17:  # auth_type + username (16 bytes)
                self.logger.warning(f"Get session challenge: invalid payload length {len(payload)}")
                return bytes([0xCC])  # Invalid request
            
            auth_type = payload[0]
            username = payload[1:17].rstrip(b'\x00')  # Remove null padding
            
            self.logger.debug(f"Get session challenge: auth_type=0x{auth_type:02x}, user='{username.decode('ascii', errors='ignore')}'")
            
            # Return a simple response - no challenge needed for none auth
            temp_session_id = 0x12345678  # Fixed for simplicity
            challenge = bytes([0x00] * 16)  # No challenge for none auth
            
            response = []
            response.extend(struct.pack('<I', temp_session_id))  # Session ID
            response.extend(challenge)  # Challenge (16 bytes)
            
            self.logger.debug(f"Session challenge response: session_id=0x{temp_session_id:08x}")
            return bytes(response)
        except Exception as e:
            self.logger.error(f"Error getting session challenge: {e}")
            return bytes([0xFF])
    
    def handle_activate_session(self, payload):
        """Activate a session"""
        try:
            if len(payload) < 22:  # auth_type + auth_code + seq + initial_outbound_seq 
                self.logger.warning(f"Activate session: invalid payload length {len(payload)}")
                return bytes([0xCC])  # Invalid request
            
            auth_type = payload[0]
            # Skip parsing the full payload - just return success
            
            self.logger.debug(f"Activate session: auth_type=0x{auth_type:02x}")
            
            # Simple activation response
            session_id = 0x12345678
            initial_inbound_seq = 1
            max_priv_level = 0x04  # Administrator
            
            response = []
            response.append(auth_type)  # Auth type
            response.extend(struct.pack('<I', session_id))  # Session ID
            response.extend(struct.pack('<I', initial_inbound_seq))  # Initial inbound sequence
            response.append(max_priv_level)  # Maximum privilege level
            
            self.logger.debug(f"Session activated: session_id=0x{session_id:08x}")
            return bytes(response)
        except Exception as e:
            self.logger.error(f"Error activating session: {e}")
            return bytes([0xFF])
            response.extend(challenge)
            
            self.logger.debug(f"Session challenge response: session_id=0x{temp_session_id:08x}")
            return bytes(response)
        except Exception as e:
            self.logger.error(f"Error getting session challenge: {e}")
            return bytes([0xFF])
    
    def handle_activate_session(self, payload):
        """Activate session"""
        try:
            if len(payload) < 6:  # Minimum required
                self.logger.warning(f"Activate session: invalid payload length {len(payload)}")
                return bytes([0xCC])  # Invalid request
            
            auth_type = payload[0]
            max_priv = payload[1] if len(payload) > 1 else 0x04
            
            self.logger.debug(f"Activate session: auth_type=0x{auth_type:02x}, max_priv=0x{max_priv:02x}")
            
            if auth_type == 0x00:
                # No authentication - simple response
                session_id = 0x00000000  # No session for auth type none
                initial_seq = 0x00000000
                max_priv_granted = min(max_priv, 0x04)  # Grant up to admin level
                
                response = [
                    auth_type,  # Echo auth type
                ]
                response.extend(struct.pack('<I', session_id))
                response.extend(struct.pack('<I', initial_seq))
                response.append(max_priv_granted)
                
            else:
                # For other auth types, create a real session
                if len(payload) < 22:  # auth_type + max_priv + challenge_response(16) + initial_seq(4)
                    return bytes([0xCC])
                
                challenge_response = payload[2:18]
                initial_seq = struct.unpack('<I', payload[18:22])[0]
                
                # Create new session
                new_session_id = self.session_id_counter
                self.session_id_counter += 1
                
                # Store session info
                client_addr = f"{self.current_client_ip}:{self.current_client_port}"
                self.sessions[client_addr] = {
                    'session_id': new_session_id,
                    'auth_type': auth_type,
                    'privilege': min(max_priv, 0x04),
                    'sequence': initial_seq
                }
                
                response = [
                    auth_type,  # Echo auth type
                ]
                response.extend(struct.pack('<I', new_session_id))
                response.extend(struct.pack('<I', initial_seq))
                response.append(min(max_priv, 0x04))
            
            self.logger.debug(f"Activate session response: {[hex(x) for x in response]}")
            return bytes(response)
        except Exception as e:
            self.logger.error(f"Error activating session: {e}")
            return bytes([0xFF])
    
    def handle_set_session_privilege_level(self, payload):
        """Set session privilege level"""
        try:
            if len(payload) < 1:
                return bytes([0xCC])  # Invalid request
            
            requested_level = payload[0]
            # Grant the requested level (or limit it)
            granted_level = min(requested_level, 0x04)  # Max admin level
            
            return bytes([granted_level])
        except Exception as e:
            self.logger.error(f"Error setting privilege level: {e}")
            return bytes([0xFF])
    
    def handle_close_session(self, payload):
        """Close session"""
        try:
            if len(payload) < 4:
                return bytes([0xCC])  # Invalid request
            
            session_id = struct.unpack('>I', payload[0:4])[0]
            # Session closed successfully
            return bytes([])
        except Exception as e:
            self.logger.error(f"Error closing session: {e}")
            return bytes([0xFF])
    
    def handle_set_boot_options(self, payload, vm_name):
        """Handle set system boot options command"""
        try:
            if len(payload) < 2:
                self.logger.warning("Invalid boot options payload")
                return bytes([0xCC])  # Invalid request
            
            param = payload[0]
            data = payload[1]
            
            self.logger.info(f"Set boot options - Param: 0x{param:02x}, Data: 0x{data:02x}, VM: {vm_name}")
            
            # Parameter 5 = Boot device selector
            if param == 0x05:
                boot_device = data & 0x3C  # Extract boot device bits
                persistent = (data & 0x40) != 0  # Persistent bit
                valid = (data & 0x80) != 0  # Valid bit
                
                self.logger.info(f"Boot device: 0x{boot_device:02x}, Persistent: {persistent}, Valid: {valid}")
                
                # Store boot options for this VM
                if vm_name not in self.boot_options:
                    self.boot_options[vm_name] = {}
                
                self.boot_options[vm_name]['device'] = boot_device
                self.boot_options[vm_name]['persistent'] = persistent
                self.boot_options[vm_name]['valid'] = valid
                
                # Apply boot configuration to VM
                success = self.apply_boot_configuration(vm_name, boot_device)
                
                return bytes([0x00 if success else 0xFF])
            
            else:
                self.logger.warning(f"Unsupported boot parameter: 0x{param:02x}")
                return bytes([0x80])  # Parameter not supported
                
        except Exception as e:
            self.logger.error(f"Error setting boot options: {e}")
            return bytes([0xFF])
    
    def handle_get_boot_options(self, payload, vm_name):
        """Handle get system boot options command"""
        try:
            if len(payload) < 3:
                self.logger.warning("Invalid get boot options payload")
                return bytes([0xCC])
            
            param = payload[0]
            set_selector = payload[1]
            block_selector = payload[2]
            
            self.logger.info(f"Get boot options - Param: 0x{param:02x}, VM: {vm_name}")
            
            # Parameter 5 = Boot device selector
            if param == 0x05:
                # Get current boot options for VM
                boot_opts = self.boot_options.get(vm_name, {})
                device = boot_opts.get('device', BootDevice.NO_OVERRIDE.value)
                persistent = boot_opts.get('persistent', False)
                valid = boot_opts.get('valid', True)
                
                # Construct response
                response = [
                    0x00,  # Completion code
                    0x01,  # Parameter version
                    param & 0x7F  # Parameter selector (clear valid bit for response)
                ]
                
                # Boot device data
                boot_data = device
                if persistent:
                    boot_data |= 0x40
                if valid:
                    boot_data |= 0x80
                
                response.append(boot_data)
                response.append(0x00)  # Instance ID
                
                return bytes(response)
            
            else:
                self.logger.warning(f"Unsupported boot parameter: 0x{param:02x}")
                return bytes([0x80])  # Parameter not supported
                
        except Exception as e:
            self.logger.error(f"Error getting boot options: {e}")
            return bytes([0xFF])
    
    def apply_boot_configuration(self, vm_name, boot_device):
        """Apply boot configuration to VMware VM"""
        try:
            self.logger.info(f"Applying boot configuration to VM {vm_name}, device: 0x{boot_device:02x}")
            
            success = True
            
            if boot_device == BootDevice.CD_DVD.value or boot_device == BootDevice.REMOTE_CD_DVD.value:
                # Boot from CD/DVD - set boot order to CD first
                self.logger.info(f"Setting {vm_name} to boot from CD/DVD")
                success = self.vmware_client.set_boot_order(vm_name, boot_from_cdrom=True)
                
                # Check if we need to mount an ISO
                iso_path = self.config.get('iso', 'default_iso_path', fallback=None)
                datastore = self.config.get('iso', 'datastore', fallback=None)
                
                if iso_path and success:
                    self.logger.info(f"Mounting ISO {iso_path} to {vm_name}")
                    success = self.vmware_client.mount_iso(vm_name, iso_path, datastore)
                
            elif boot_device == BootDevice.HDD.value:
                # Boot from hard disk - set boot order to HDD first
                self.logger.info(f"Setting {vm_name} to boot from HDD")
                success = self.vmware_client.set_boot_order(vm_name, boot_from_cdrom=False)
                
                # Unmount any ISO
                self.vmware_client.unmount_iso(vm_name)
                
            elif boot_device == BootDevice.NO_OVERRIDE.value:
                # No override - restore default boot order (HDD first)
                self.logger.info(f"Clearing boot override for {vm_name}")
                success = self.vmware_client.set_boot_order(vm_name, boot_from_cdrom=False)
                self.vmware_client.unmount_iso(vm_name)
                
            else:
                self.logger.warning(f"Unsupported boot device: 0x{boot_device:02x}")
                return False
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error applying boot configuration: {e}")
            return False
    
    def send_response(self, addr, response):
        """Send IPMI response"""
        try:
            if self.socket and response:
                # Simple IPMI response header
                header = bytes([
                    0x00,  # Auth type
                    0x00,  # Sequence
                    0x00,  # Session ID
                    len(response),  # Message length
                    0x00,  # NetFn (response)
                    0x00   # Command (response)
                ])
                
                full_response = header + response
                self.socket.sendto(full_response, addr)
                self.logger.debug(f"Sent response to {addr[0]}:{addr[1]}")
                
        except Exception as e:
            self.logger.error(f"Error sending response: {e}")
