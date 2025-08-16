#!/usr/bin/env python3
"""
VMware IPMI Bridge Service
Provides IPMI interface for VMware VMs using pyghmi FakeBmc as base.
"""

import json
import logging
import threading
import time
import sys
import os

# Add the current directory to the path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pyghmi.ipmi.bmc as bmc
from vmware_client import VMwareClient

# Configure logging with DEBUG level for detailed OpenShift communication tracking
debug_env = os.getenv('IPMI_DEBUG', 'false').lower()
debug_enabled = debug_env in ['true', '1', 'yes', 'on']
log_level = logging.DEBUG if debug_enabled else logging.INFO

print(f"🐛 Debug Environment Variable: IPMI_DEBUG={debug_env}")
print(f"🐛 Debug Enabled: {debug_enabled}")
print(f"🐛 Log Level: {log_level}")

# Setup log file path - try multiple locations
log_paths = [
    '/var/log/ipmi-vmware-bridge.log',  # System log (requires root)
    os.path.expanduser('~/ipmi-vmware-bridge.log'),  # User home
    './ipmi-vmware-bridge.log'  # Current directory
]

log_file = None
for path in log_paths:
    try:
        # Test if we can write to this location
        with open(path, 'a') as f:
            pass
        log_file = path
        break
    except (PermissionError, FileNotFoundError):
        continue

handlers = [logging.StreamHandler()]
if log_file:
    handlers.append(logging.FileHandler(log_file))

logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=handlers
)

# Set pyghmi to DEBUG to see all IPMI protocol details
logging.getLogger('pyghmi').setLevel(logging.DEBUG if debug_enabled else logging.WARNING)
logging.getLogger('pyghmi.ipmi.bmc').setLevel(logging.DEBUG if debug_enabled else logging.WARNING)

logger = logging.getLogger(__name__)

if log_file:
    logger.info(f"📝 Logging to: {log_file}")

if debug_enabled:
    logger.info("🐛 DEBUG MODE ENABLED - All IPMI calls from OpenShift will be logged in detail")
else:
    logger.info("📋 PRODUCTION MODE - Limited logging enabled")

class VMwareBMC(bmc.Bmc):
    """VMware BMC implementation - IPv4 only, root required"""
    
    def __init__(self, authdata, port, vm_config):
        # Initialize with standard parameters (IPv4 is default)
        super(VMwareBMC, self).__init__(authdata, port)
        self.vm_config = vm_config
        self.vm_name = vm_config['name']
        self.powerstate = 'unknown'
        self.bootdevice = 'default'
        
        # Enhanced session tracking for OpenShift compatibility
        self.session_timeout = 300  # 5 minutes timeout
        self.last_activity = time.time()
        self.openshift_sessions = {}
        
        # Set up BMC-specific logger
        self.logger = logging.getLogger(f"BMC-{self.vm_name}")
        self.logger.info(f"🚀 Initializing BMC for VM: {self.vm_name} on IPv4 port {port}")
        
        # Log authentication data (without passwords)
        auth_users = list(authdata.keys())
        self.logger.debug(f"🔐 IPMI Auth Users: {auth_users}")
        
        # Initialize VMware client
        try:
            self.vmware_client = VMwareClient(
                vm_config['vcenter_host'],
                vm_config['vcenter_user'], 
                vm_config['vcenter_password']
            )
            self.logger.info(f"✅ VMware client initialized for VM: {self.vm_name}")
            
            # Get initial power state
            self._update_power_state()
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize VMware client for {self.vm_name}: {e}")
            self.vmware_client = None

    def _update_power_state(self):
        """Update power state from VMware"""
        if not self.vmware_client:
            return
            
        try:
            is_powered_on = self.vmware_client.is_vm_powered_on(self.vm_name)
            old_state = self.powerstate
            self.powerstate = 'on' if is_powered_on else 'off'
            if old_state != self.powerstate:
                self.logger.info(f"🔄 VM {self.vm_name} power state changed: {old_state} → {self.powerstate}")
            else:
                self.logger.debug(f"📊 VM {self.vm_name} power state: {self.powerstate}")
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to get power state for {self.vm_name}: {e}")

    def _update_session_activity(self, client_info):
        """Update session activity timestamp for OpenShift clients"""
        self.last_activity = time.time()
        if client_info not in self.openshift_sessions:
            self.openshift_sessions[client_info] = {
                'first_seen': time.time(),
                'last_activity': time.time(),
                'request_count': 0
            }
        else:
            self.openshift_sessions[client_info]['last_activity'] = time.time()
            self.openshift_sessions[client_info]['request_count'] += 1
            
        # Log session stats for OpenShift debugging
        session = self.openshift_sessions[client_info]
        self.logger.debug(f"📈 Session {client_info}: {session['request_count']} requests, "
                         f"active for {time.time() - session['first_seen']:.1f}s")

    def _cleanup_stale_sessions(self):
        """Clean up stale OpenShift sessions"""
        current_time = time.time()
        stale_sessions = []
        
        for client_info, session in self.openshift_sessions.items():
            if current_time - session['last_activity'] > self.session_timeout:
                stale_sessions.append(client_info)
                
        for client_info in stale_sessions:
            self.logger.info(f"🧹 Cleaning up stale session from {client_info}")
            del self.openshift_sessions[client_info]

    # Override BMC methods to add detailed logging for OpenShift communication
    def handle_raw_request(self, request, sockaddr):
        """Override to log all raw IPMI communications for debugging and handle inspection commands"""
        try:
            # Validate input parameters
            if request is None:
                self.logger.error(f"❌ Error: request is None")
                return b'\x01'  # Return command not supported error
                
            if sockaddr is None:
                self.logger.error(f"❌ Error: sockaddr is None") 
                return b'\x01'  # Return command not supported error
            
            # Extract client information safely - improved for OpenShift detection
            if hasattr(sockaddr, 'clientsockaddr') and sockaddr.clientsockaddr:
                client_info = f"{sockaddr.clientsockaddr[0]}:{sockaddr.clientsockaddr[1]}"
                client_ip = sockaddr.clientsockaddr[0]
            elif isinstance(sockaddr, (list, tuple)) and len(sockaddr) >= 2:
                client_info = f"{sockaddr[0]}:{sockaddr[1]}"
                client_ip = sockaddr[0]
            else:
                client_info = "unknown"
                client_ip = "unknown"
                
            # Enhanced OpenShift detection
            is_openshift_client = any([
                "192.168.103" in str(client_ip),  # OpenShift network range
                client_ip in ["192.168.103.52"],  # Known OpenShift BMH controller
                "ocp" in str(client_ip).lower(),
                "openshift" in str(client_ip).lower()
            ])
            
            if is_openshift_client:
                self.logger.info(f"🎯 OPENSHIFT CLIENT DETECTED from {client_info} → VM {self.vm_name}")
                # Update session activity for OpenShift tracking
                self._update_session_activity(client_info)
                # Cleanup stale sessions periodically
                if len(self.openshift_sessions) % 10 == 0:  # Every 10 requests
                    self._cleanup_stale_sessions()
            else:
                self.logger.debug(f"📡 Standard IPMI client from {client_info} → VM {self.vm_name}")
                
            # Parse request for detailed logging
            try:
                # Handle both old byte format and new dict format
                if isinstance(request, dict):
                    netfn = request.get('netfn')
                    cmd = request.get('command')
                    data = request.get('data', bytearray())
                    
                    self.logger.info(f"📨 IPMI REQUEST from {client_info} to VM {self.vm_name} - NetFn: 0x{netfn:02x}, Command: 0x{cmd:02x}")
                    self.logger.info(f"🔍 Data: {data.hex() if hasattr(data, 'hex') else str(data)} (length: {len(data) if data else 0})")
                    
                    # Detailed command identification
                    cmd_name = "UNKNOWN"
                    if netfn == 0x2C and cmd == 0x3E:
                        cmd_name = "DCMI_GET_CAPABILITIES"
                    elif netfn == 0x2C and cmd == 0x00:
                        cmd_name = "DCMI_POWER_READING"
                    elif netfn == 0x06 and cmd == 0x01:
                        cmd_name = "GET_DEVICE_ID"
                    elif netfn == 0x06 and cmd == 0x38:
                        cmd_name = "GET_CHANNEL_AUTH_CAPABILITIES"
                    elif netfn == 0x00 and cmd == 0x00:
                        cmd_name = "GET_CHASSIS_STATUS"
                    elif netfn == 0x00 and cmd == 0x01:
                        cmd_name = "GET_CHASSIS_CAPABILITIES"
                    elif netfn == 0x00 and cmd == 0x02:
                        cmd_name = "CHASSIS_CONTROL"
                    
                    self.logger.info(f"📋 COMMAND: {cmd_name} for VM {self.vm_name}")
                    
                    # Handle specific IPMI commands with proper responses
                    if netfn == 0x2C and cmd == 0x3E:  # DCMI Get DCMI Capabilities Info
                        self.logger.info(f"🔍 DCMI: OpenShift requesting DCMI capabilities for VM {self.vm_name}")
                        # DCMI Get DCMI Capabilities Info Response
                        # Format: CC + DCMI specification conformance + Data model revision + optional parameters
                        dcmi_response = bytearray([
                            0x00,  # Completion Code (Success)
                            0xDC,  # Group Extension Identifier (DCMI)
                            0x01,  # DCMI Specification Conformance (1.0)
                            0x02,  # Data Model Revision (2)
                            0x01,  # Optional Capabilities: Power management supported
                            0x00,  # Mandatory Platform Capabilities
                            0x00,  # Optional Platform Capabilities
                            0x00   # Manageability Access Capabilities
                        ])
                        self.logger.debug(f"📤 DCMI Response for VM {self.vm_name}: {dcmi_response.hex()}")
                        return bytes(dcmi_response)
                        
                    elif netfn == 0x2C and cmd == 0x00:  # DCMI Get DCMI Sensor Info / Power Reading
                        self.logger.info(f"🔍 DCMI: OpenShift requesting DCMI Sensor/Power Info for VM {self.vm_name}")
                        sensor_param = data[1] if len(data) > 1 else 0x00
                        
                        if sensor_param == 0x00:  # Total power reading
                            # Get actual VM power state to provide realistic power readings
                            try:
                                vm_power_state = self.vmware_client.get_vm_power_state(self.vm_name)
                                is_powered_on = vm_power_state == 'on'
                                self.logger.info(f"💡 DCMI Power Reading: VM {self.vm_name} is {'ON' if is_powered_on else 'OFF'} (VMware state: {vm_power_state})")
                                
                                # Update internal power state to stay synchronized
                                expected_state = 'on' if is_powered_on else 'off'
                                if self.powerstate != expected_state:
                                    self.logger.info(f"🔄 Updating power state: {self.powerstate} → {expected_state}")
                                    self.powerstate = expected_state
                                    
                            except Exception as e:
                                self.logger.warning(f"⚠️ Failed to get VMware power state for {self.vm_name}: {e}")
                                is_powered_on = self.powerstate == 'on'  # Fallback to cached state
                                vm_power_state = self.powerstate
                            
                            # Critical: Power readings that OpenShift can interpret correctly
                            if is_powered_on:
                                # VM is ON - return realistic power consumption (NO standby power when on)
                                current_power = 0x64  # 100W
                                min_power = 0x5A      # 90W
                                max_power = 0x78      # 120W
                                avg_power = 0x6E      # 110W
                                # DCMI Power Reading State: 0x01 = Active/Powered On
                                # Bit 0: Power reading state (1 = active, 0 = inactive)
                                # Bit 1-7: Reserved (should be 0)
                                power_state = 0x01    # Active/Powered On - CRITICAL for OpenShift
                                self.logger.info(f"🔋 DCMI: VM {self.vm_name} is POWERED ON - Current: {current_power}W, State: 0x{power_state:02x}")
                            else:
                                # VM is OFF - return ZERO power consumption (critical for OpenShift detection)
                                current_power = 0x00  # 0W (completely off - NO standby power)
                                min_power = 0x00      # 0W  
                                max_power = 0x00      # 0W
                                avg_power = 0x00      # 0W
                                # DCMI Power Reading State: 0x00 = Inactive/Powered Off  
                                # According to DCMI 1.5 spec, 0x00 means measurement not available/inactive
                                power_state = 0x40    # Inactive/Powered Off (0x40 = measurement inactive)
                                self.logger.info(f"🔋 DCMI: VM {self.vm_name} is POWERED OFF - Current: {current_power}W, State: 0x{power_state:02x}")
                            
                            # DCMI Power Reading Response - Enhanced for OpenShift compatibility
                            # Based on real BMC implementations (Dell iDRAC, HP iLO, Supermicro)
                            dcmi_power_response = bytearray([
                                0x00,  # Completion Code (Success)
                                0xDC,  # Group Extension Identifier (DCMI)
                                current_power, 0x00,  # Current Power (little endian 16-bit)
                                min_power, 0x00,      # Minimum Power (little endian 16-bit)
                                max_power, 0x00,      # Maximum Power (little endian 16-bit)
                                avg_power, 0x00,      # Average Power (little endian 16-bit)
                                0x00, 0x00, 0x00, 0x00,  # Timestamp (32-bit)
                                0x10, 0x27, 0x00, 0x00,  # Statistics reporting period (10000ms)
                                power_state   # Power reading state (CRITICAL: 0x01=ACTIVE, 0x40=INACTIVE)
                            ])
                            self.logger.info(f"📤 DCMI Power Reading Response for VM {self.vm_name}: Current={current_power}W, State=0x{power_state:02x}, Response: {dcmi_power_response.hex()}")
                            return bytes(dcmi_power_response)
                        elif sensor_param == 0x03:  # Enhanced system power statistics
                            dcmi_stats_response = bytearray([
                                0x00,  # Completion Code (Success)
                                0xDC,  # Group Extension Identifier (DCMI)
                                0x01,  # Power measurement (available)
                                0x00, 0x00,  # Reserved
                            ])
                            self.logger.debug(f"📤 DCMI Stats Response for VM {self.vm_name}: {dcmi_stats_response.hex()}")
                            return bytes(dcmi_stats_response)
                        else:
                            dcmi_generic_response = bytearray([
                                0x00,  # Completion Code (Success)
                                0xDC,  # Group Extension Identifier (DCMI)
                                0x00   # No data
                            ])
                            self.logger.debug(f"📤 DCMI Generic Response for VM {self.vm_name}: {dcmi_generic_response.hex()}")
                            return bytes(dcmi_generic_response)
                        
                    elif netfn == 0x06 and cmd == 0x01:  # Application / Get Device ID
                        self.logger.info(f"� IPMI: OpenShift requesting Device ID for VM {self.vm_name}")
                        # Standard IPMI Get Device ID Response
                        device_id_response = bytearray([
                            0x00,  # Completion Code (Success)
                            0x20,  # Device ID (BMC)
                            0x81,  # Device Revision (Device available, firmware revision 0.1)
                            0x00,  # Firmware Revision 1 (Major)
                            0x01,  # Firmware Revision 2 (Minor) 
                            0x02,  # IPMI Version (2.0)
                            0x9F,  # Additional Device Support (Sensor, SDR Repository, SEL, FRU, IPMB, Chassis)
                            0x5A, 0x31, 0x00,  # Manufacturer ID (Intel - example)
                            0x00, 0x01,  # Product ID 
                            0x00, 0x00, 0x00, 0x00  # Auxiliary Firmware Revision
                        ])
                        self.logger.debug(f"📤 Device ID Response for VM {self.vm_name}: {device_id_response.hex()}")
                        return bytes(device_id_response)
                        
                    elif netfn == 0x06 and cmd == 0x38:  # Application / Get Channel Auth Capabilities
                        self.logger.info(f"🔍 IPMI: OpenShift requesting Channel Auth Capabilities for VM {self.vm_name}")
                        channel = data[0] if len(data) > 0 else 0x0E  # Use LAN channel or requested channel
                        auth_capabilities_response = bytearray([
                            0x00,  # Completion Code (Success)
                            channel,  # Channel number
                            0x14,  # Authentication type support (MD5, Password)
                            0x14,  # Authentication status (MD5, Password enabled)
                            0x02,  # Extended capabilities (IPMI v2.0)
                            0x00, 0x00, 0x00  # OEM ID (none)
                        ])
                        self.logger.debug(f"📤 Auth Capabilities Response for VM {self.vm_name}: {auth_capabilities_response.hex()}")
                        return bytes(auth_capabilities_response)
                        
                    elif netfn == 0x00 and cmd == 0x00:  # Chassis / Get Chassis Status
                        self.logger.info(f"🔍 CHASSIS: OpenShift requesting Chassis Status for VM {self.vm_name}")
                        
                        # Force fresh power state check with VMware
                        try:
                            vm_power_state = self.vmware_client.get_vm_power_state(self.vm_name)
                            power_on = vm_power_state == 'on'
                            
                            # Update internal state
                            expected_state = 'on' if power_on else 'off'
                            if self.powerstate != expected_state:
                                self.logger.info(f"🔄 Chassis Status: Updating power state {self.powerstate} → {expected_state}")
                                self.powerstate = expected_state
                                
                        except Exception as e:
                            self.logger.warning(f"⚠️ Failed to get VMware power state for {self.vm_name}: {e}")
                            power_on = self.powerstate == 'on'  # Fallback to cached state
                        
                        self.logger.info(f"💡 Chassis Status: VM {self.vm_name} power_on={power_on} (final state='{self.powerstate}')")
                        
                        # IPMI Chassis Status Response Format (IPMI v2.0 spec) - OpenShift compatible
                        # Byte 0: Current Power State and Policies
                        current_power_state = 0x01 if power_on else 0x00  # Bit 0: Power is on (1) or off (0)
                        # No power faults, overloads, or interlocks
                        
                        # Byte 1: Last Power Event  
                        if power_on:
                            last_power_event = 0x01    # Power restored by command
                        else:
                            last_power_event = 0x00    # AC failed / unknown
                        
                        # Byte 2: Misc. Chassis State
                        misc_chassis_state = 0x00  # No intrusions, lockouts, or faults
                        
                        # Optional Byte 3: Front Panel Button Capabilities
                        front_panel_caps = 0x00    # No front panel features
                        
                        chassis_status_response = bytearray([
                            0x00,  # Completion Code (Success)
                            current_power_state,    # Current Power State (CRITICAL: bit 0 = power on)
                            last_power_event,       # Last Power Event 
                            misc_chassis_state,     # Misc Chassis State
                            front_panel_caps        # Front Panel Button Capabilities
                        ])
                        self.logger.info(f"📤 Chassis Status Response for VM {self.vm_name}: Power={'ON' if power_on else 'OFF'}, State=0x{current_power_state:02x}, Response: {chassis_status_response.hex()}")
                        return bytes(chassis_status_response)
                        
                    elif netfn == 0x00 and cmd == 0x01:  # Chassis / Get Chassis Capabilities  
                        self.logger.info(f"🔍 CHASSIS: OpenShift requesting Chassis Capabilities for VM {self.vm_name}")
                        chassis_capabilities_response = bytearray([
                            0x00,  # Completion Code (Success)
                            0x00,  # Capabilities flags
                            0x00, 0x00, 0x00, 0x00,  # FRU Info Device Address, SDR Device Address, SEL Device Address, System Management Device Address
                            0x00, 0x00, 0x00, 0x00   # Bridge Device Address
                        ])
                        self.logger.debug(f"📤 Chassis Capabilities Response for VM {self.vm_name}: {chassis_capabilities_response.hex()}")
                        return bytes(chassis_capabilities_response)
                        
                    elif netfn == 0x00 and cmd == 0x02:  # Chassis / Chassis Control
                        self.logger.info(f"🔍 CHASSIS: OpenShift sending Chassis Control command for VM {self.vm_name}")
                        control_code = data[0] if len(data) > 0 else 0x00
                        self.logger.info(f"🔧 Chassis Control Code: 0x{control_code:02x} for VM {self.vm_name}")
                        
                        # Handle power control commands
                        if control_code == 0x00:  # Power Down
                            self.logger.info(f"🔌 POWER: OpenShift requesting Power DOWN for VM {self.vm_name}")
                            try:
                                self.vmware_client.power_off_vm(self.vm_name)
                                self.logger.info(f"✅ VM {self.vm_name} powered down successfully")
                            except Exception as e:
                                self.logger.warning(f"⚠️ Failed to power down VM {self.vm_name}: {e}")
                        elif control_code == 0x01:  # Power Up
                            self.logger.info(f"🔌 POWER: OpenShift requesting Power UP for VM {self.vm_name}")
                            try:
                                self.vmware_client.power_on_vm(self.vm_name)
                                self.logger.info(f"✅ VM {self.vm_name} powered up successfully")
                            except Exception as e:
                                self.logger.warning(f"⚠️ Failed to power up VM {self.vm_name}: {e}")
                        elif control_code == 0x02:  # Power Cycle
                            self.logger.info(f"🔌 POWER: OpenShift requesting Power CYCLE for VM {self.vm_name}")
                            try:
                                self.vmware_client.reset_vm(self.vm_name)
                                self.logger.info(f"✅ VM {self.vm_name} power cycled successfully")
                            except Exception as e:
                                self.logger.warning(f"⚠️ Failed to power cycle VM {self.vm_name}: {e}")
                        elif control_code == 0x03:  # Hard Reset
                            self.logger.info(f"🔌 POWER: OpenShift requesting HARD RESET for VM {self.vm_name}")
                            try:
                                self.vmware_client.reset_vm(self.vm_name)
                                self.logger.info(f"✅ VM {self.vm_name} hard reset successfully")
                            except Exception as e:
                                self.logger.warning(f"⚠️ Failed to hard reset VM {self.vm_name}: {e}")
                        
                        chassis_control_response = bytearray([0x00])  # Success
                        self.logger.debug(f"📤 Chassis Control Response for VM {self.vm_name}: {chassis_control_response.hex()}")
                        return bytes(chassis_control_response)
                        
                    elif netfn == 0x00 and cmd == 0x08:  # Chassis / Set System Boot Options
                        self.logger.info(f"🔍 CHASSIS: OpenShift setting Boot Options for VM {self.vm_name}")
                        param = data[0] if len(data) > 0 else 0x00
                        
                        self.logger.info(f"🥾 Boot Options Parameter: 0x{param:02x} for VM {self.vm_name}")
                        
                        # Handle boot device selection
                        if param == 0x05:  # Boot flags
                            if len(data) >= 2:
                                boot_flags = data[1]
                                boot_device_map = {
                                    0x00: 'default',
                                    0x04: 'hdd',
                                    0x08: 'cdrom', 
                                    0x20: 'network',
                                    0x24: 'floppy'
                                }
                                boot_device = boot_device_map.get(boot_flags & 0x3C, 'default')
                                self.logger.info(f"🥾 Setting boot device to: {boot_device} for VM {self.vm_name}")
                                self.bootdevice = boot_device
                        
                        boot_options_response = bytearray([0x00])  # Success
                        self.logger.debug(f"📤 Boot Options Response for VM {self.vm_name}: {boot_options_response.hex()}")
                        return bytes(boot_options_response)
                        
                    elif netfn == 0x00 and cmd == 0x09:  # Chassis / Get System Boot Options
                        self.logger.info(f"🔍 CHASSIS: OpenShift requesting Boot Options for VM {self.vm_name}")
                        param = data[0] if len(data) > 0 else 0x05
                        
                        if param == 0x05:  # Boot flags
                            # Convert boot device to IPMI boot flags
                            boot_device_flags = {
                                'default': 0x00,
                                'hdd': 0x04,
                                'disk': 0x04,
                                'cdrom': 0x08,
                                'network': 0x20,
                                'pxe': 0x20,
                                'floppy': 0x24
                            }
                            boot_flag = boot_device_flags.get(self.bootdevice, 0x00)
                            
                            boot_options_response = bytearray([
                                0x00,  # Completion Code (Success)
                                0x01,  # Parameter version
                                0x05,  # Parameter selector (boot flags)
                                0x80,  # Valid bit + boot type (legacy)
                                boot_flag,  # Boot device selector
                                0x00, 0x00, 0x00  # Reserved
                            ])
                        else:
                            # Generic response for other parameters
                            boot_options_response = bytearray([
                                0x00,  # Completion Code (Success)
                                0x01,  # Parameter version
                                param,  # Parameter selector
                                0x00   # No data
                            ])
                            
                        self.logger.debug(f"📤 Get Boot Options Response for VM {self.vm_name}: {boot_options_response.hex()}")
                        return bytes(boot_options_response)
                        
                    elif netfn == 0x04 and cmd == 0x20:  # Sensor/Event / Get SDR Repository Info
                        self.logger.info(f"🔍 SENSOR: OpenShift requesting SDR Repository Info for VM {self.vm_name}")
                        sdr_info_response = bytearray([
                            0x00,  # Completion Code (Success)
                            0x51,  # SDR version (5.1)
                            0x00, 0x05,  # Record count (5 records, little endian)
                            0x00, 0x00,  # Free space (0 bytes)
                            0x00, 0x00, 0x00, 0x00,  # Most recent addition timestamp
                            0x00, 0x00, 0x00, 0x00,  # Most recent erase timestamp  
                            0x02,  # SDR support: Get SDR Repository Info + Reserve SDR Repository
                        ])
                        self.logger.debug(f"📤 SDR Repository Info Response for VM {self.vm_name}: {sdr_info_response.hex()}")
                        return bytes(sdr_info_response)
                        
                    elif netfn == 0x04 and cmd == 0x22:  # Sensor/Event / Reserve SDR Repository
                        self.logger.info(f"🔍 SENSOR: OpenShift reserving SDR Repository for VM {self.vm_name}")
                        reserve_sdr_response = bytearray([
                            0x00,  # Completion Code (Success)
                            0x01, 0x00  # Reservation ID (little endian)
                        ])
                        self.logger.debug(f"📤 Reserve SDR Response for VM {self.vm_name}: {reserve_sdr_response.hex()}")
                        return bytes(reserve_sdr_response)
                        
                    elif netfn == 0x04 and cmd == 0x23:  # Sensor/Event / Get SDR
                        self.logger.info(f"🔍 SENSOR: OpenShift requesting SDR record for VM {self.vm_name}")
                        # Return "no more records" to indicate end of SDR repository
                        get_sdr_response = bytearray([0xCB])  # Completion Code: Requested data not present
                        self.logger.debug(f"📤 Get SDR Response for VM {self.vm_name}: {get_sdr_response.hex()}")
                        return bytes(get_sdr_response)
                        
                    elif netfn == 0x04 and cmd == 0x2D:  # Sensor/Event / Get Sensor Reading
                        self.logger.info(f"🔍 SENSOR: OpenShift requesting sensor reading for VM {self.vm_name}")
                        sensor_num = data[0] if len(data) > 0 else 0x00
                        
                        # Provide fake but consistent sensor readings
                        sensor_reading_response = bytearray([
                            0x00,  # Completion Code (Success)
                            0x20,  # Sensor reading (32)
                            0x80,  # Sensor status (reading valid, no events)
                            0x00, 0x00  # Event status (no events)
                        ])
                        self.logger.debug(f"📤 Sensor Reading Response for VM {self.vm_name}: {sensor_reading_response.hex()}")
                        return bytes(sensor_reading_response)
                        
                    elif netfn == 0x0A and cmd == 0x40:  # Storage / Get SEL Info
                        self.logger.info(f"🔍 SEL: OpenShift requesting SEL Info for VM {self.vm_name}")
                        sel_info_response = bytearray([
                            0x00,  # Completion Code (Success)
                            0x51,  # SEL version (5.1)
                            0x00, 0x00,  # Entry count (0 entries, little endian)
                            0xFF, 0xFF,  # Free space (65535 bytes)
                            0x00, 0x00, 0x00, 0x00,  # Most recent addition timestamp
                            0x00, 0x00, 0x00, 0x00,  # Most recent erase timestamp
                            0x02,  # SEL support: Get SEL Info + Reserve SEL
                        ])
                        self.logger.debug(f"📤 SEL Info Response for VM {self.vm_name}: {sel_info_response.hex()}")
                        return bytes(sel_info_response)
                        
                    elif netfn == 0x0A and cmd == 0x42:  # Storage / Reserve SEL
                        self.logger.info(f"🔍 SEL: OpenShift reserving SEL for VM {self.vm_name}")
                        reserve_sel_response = bytearray([
                            0x00,  # Completion Code (Success)
                            0x01, 0x00  # Reservation ID (little endian)
                        ])
                        self.logger.debug(f"📤 Reserve SEL Response for VM {self.vm_name}: {reserve_sel_response.hex()}")
                        return bytes(reserve_sel_response)
                        
                    elif netfn == 0x0A and cmd == 0x43:  # Storage / Get SEL Entry
                        self.logger.info(f"🔍 SEL: OpenShift requesting SEL entry for VM {self.vm_name}")
                        # Return "no more entries" to indicate empty SEL
                        get_sel_response = bytearray([0xCB])  # Completion Code: Requested data not present  
                        self.logger.debug(f"📤 Get SEL Entry Response for VM {self.vm_name}: {get_sel_response.hex()}")
                        return bytes(get_sel_response)
                        
                    else:
                        # Handle unimplemented commands - log them for debugging
                        self.logger.warning(f"⚠️ UNIMPLEMENTED IPMI COMMAND from {client_info} to VM {self.vm_name}")
                        self.logger.warning(f"🔍 NetFn: 0x{netfn:02x}, Command: 0x{cmd:02x}, Data: {data.hex() if hasattr(data, 'hex') else str(data)}")
                        
                        # Return "Command not supported" for unimplemented commands
                        unimplemented_response = bytearray([0xC1])  # Command not supported
                        self.logger.debug(f"📤 Unimplemented Command Response for VM {self.vm_name}: {unimplemented_response.hex()}")
                        return bytes(unimplemented_response)
                        
                elif hasattr(request, '__iter__') and len(request) >= 2:
                    netfn = request[0] if len(request) > 0 else None
                    cmd = request[1] if len(request) > 1 else None
                    
                    self.logger.debug(f"📨 IPMI BYTES REQUEST from {client_info} to VM {self.vm_name}")
                    self.logger.debug(f"🔍 NetFn: 0x{netfn:02x}, Command: 0x{cmd:02x}" if netfn is not None and cmd is not None else f"🔍 Raw Request Data: {request}")
                else:
                    self.logger.debug(f"📨 IPMI UNKNOWN REQUEST from {client_info} to VM {self.vm_name}")
                    self.logger.debug(f"🔍 Raw Request Data: {request.hex() if hasattr(request, 'hex') else str(request)}")
                    
                # Log special commands for inspection tracking
                if isinstance(request, dict):
                    netfn = request.get('netfn')
                    cmd = request.get('command')
                elif hasattr(request, '__iter__') and len(request) >= 2:
                    netfn = request[0] if len(request) > 0 else None
                    cmd = request[1] if len(request) > 1 else None
                else:
                    netfn = cmd = None
                    
                if netfn is not None and cmd is not None:
                    # Special handling for inspection-related commands
                    if netfn == 0x04:  # Sensor/Event Request
                        self.logger.info(f"🔍 INSPECTION: Sensor/Event request (0x{cmd:02x}) from OpenShift for VM {self.vm_name}")
                    elif netfn == 0x06:  # Application Request  
                        self.logger.info(f"🔍 INSPECTION: Application request (0x{cmd:02x}) from OpenShift for VM {self.vm_name}")
                        if cmd == 0x01:  # Get Device ID
                            self.logger.info(f"📋 OpenShift requesting device ID for inspection of VM {self.vm_name}")
                        elif cmd == 0x38:  # Get Channel Auth Capabilities
                            self.logger.info(f"🔐 OpenShift checking auth capabilities for VM {self.vm_name}")
                    elif netfn == 0x2C:  # Group Extension Request
                        self.logger.info(f"🔍 INSPECTION: Group Extension request (0x{cmd:02x}) from OpenShift for VM {self.vm_name}")
                    elif netfn == 0x00:  # Chassis Request
                        if cmd == 0x01:  # Get Chassis Capabilities
                            self.logger.info(f"🏗️ INSPECTION: OpenShift requesting chassis capabilities for VM {self.vm_name}")
                        elif cmd == 0x00:  # Get Chassis Status
                            self.logger.debug(f"📊 OpenShift requesting chassis status for VM {self.vm_name}")
                            
            except (IndexError, TypeError, AttributeError, KeyError) as parse_error:
                self.logger.debug(f"📨 IPMI REQUEST PARSE ERROR from {client_info} to VM {self.vm_name}")
                self.logger.debug(f"🔍 Raw Request Data (parse error): {request} (Error: {parse_error})")
            
            response = super().handle_raw_request(request, sockaddr)
            
            # Log response details safely
            try:
                if hasattr(response, '__iter__') and len(response) > 0:
                    self.logger.debug(f"📤 IPMI RAW RESPONSE to {client_info}: CC=0x{response[0]:02x} (Success)" if response[0] == 0 else f"📤 IPMI RAW RESPONSE to {client_info}: CC=0x{response[0]:02x} (Error)")
                else:
                    self.logger.debug(f"📤 IPMI RAW RESPONSE to {client_info}: {response.hex() if hasattr(response, 'hex') else str(response)}")
            except (IndexError, TypeError, AttributeError) as resp_error:
                self.logger.debug(f"📤 IPMI RAW RESPONSE to {client_info}: {response} (Parse error: {resp_error})")
            
            return response
        except KeyError as ke:
            if ke.args and ke.args[0] == 0:
                # This is a known issue with pyghmi - unsupported command
                self.logger.debug(f"🔧 Unsupported IPMI command from {client_info}: {request} - Returning 'command not supported'")
                return b'\x01'  # Command not supported
            else:
                self.logger.error(f"❌ KeyError in raw request from {client_info}: {ke}, request: {request}")
                return b'\x01'  # Return command not supported error
        except Exception as e:
            self.logger.error(f"❌ Error handling raw request - Exception type: {type(e).__name__}, value: {repr(e)}, request: {request.hex() if hasattr(request, 'hex') else repr(request)}")
            # Return a proper IPMI error response instead of calling super again
            return b'\x01'  # Return command not supported error

    def handle_request(self, request, sockaddr):
        """Override to log structured IPMI requests"""
        try:
            # Extract client information safely
            if hasattr(sockaddr, 'clientsockaddr') and sockaddr.clientsockaddr:
                client_info = f"{sockaddr.clientsockaddr[0]}:{sockaddr.clientsockaddr[1]}"
            elif isinstance(sockaddr, (list, tuple)) and len(sockaddr) >= 2:
                client_info = f"{sockaddr[0]}:{sockaddr[1]}"
            else:
                client_info = "unknown"
                
            self.logger.info(f"🎯 IPMI REQUEST from OpenShift/BMH at {client_info} → VM {self.vm_name}")
            
            # Log request details if available
            if hasattr(request, 'command'):
                self.logger.info(f"📋 Command: {request.command}")
            if hasattr(request, 'netfn'):
                self.logger.info(f"📋 NetFn: {request.netfn}")
            if hasattr(request, 'data'):
                self.logger.debug(f"📋 Data: {request.data}")
            
            response = super().handle_request(request, sockaddr)
            self.logger.info(f"✅ IPMI RESPONSE sent to OpenShift/BMH at {client_info}")
            return response
        except Exception as e:
            self.logger.error(f"❌ Error handling request from {client_info}: {e}")
            return super().handle_request(request, sockaddr)

    def get_power_state(self):
        """Get current power state - required by pyghmi BMC"""
        self.logger.info(f"🔍 DIRECT: OpenShift requesting power state via get_power_state() for VM {self.vm_name}")
        
        # Force update power state every time
        self._update_power_state()
        
        # Extra debug logging
        self.logger.info(f"📊 Current power state for VM {self.vm_name}: '{self.powerstate}' (type: {type(self.powerstate)})")
        
        if self.vmware_client:
            try:
                # Double-check directly with VMware
                is_powered_on = self.vmware_client.is_vm_powered_on(self.vm_name)
                self.logger.info(f"🔄 VMware direct check for VM {self.vm_name}: {is_powered_on}")
                
                # Ensure consistent state
                expected_state = 'on' if is_powered_on else 'off'
                if self.powerstate != expected_state:
                    self.logger.warning(f"⚠️ POWER STATE MISMATCH! VM {self.vm_name}: IPMI={self.powerstate}, VMware={expected_state}")
                    self.powerstate = expected_state
            except Exception as e:
                self.logger.error(f"❌ Error double-checking power state for VM {self.vm_name}: {e}")
        
        self.logger.info(f"📊 DIRECT RESPONSE: Reporting power state to OpenShift: VM {self.vm_name} is '{self.powerstate}'")
        return self.powerstate  # Should return 'on' or 'off' as string

    def power_off(self):
        """Power off the VM"""
        self.logger.info(f"🔴 OpenShift requesting POWER OFF for VM: {self.vm_name}")
        
        if not self.vmware_client:
            self.logger.error(f"❌ No VMware client available for {self.vm_name}")
            return
            
        try:
            self.logger.info(f"⚡ Executing VMware power off for VM: {self.vm_name}")
            success = self.vmware_client.power_off_vm(self.vm_name)
            if success:
                self.powerstate = 'off'
                self.logger.info(f"✅ VM {self.vm_name} powered off successfully - OpenShift notified")
            else:
                self.logger.error(f"❌ Failed to power off VM {self.vm_name} - OpenShift will see error")
        except Exception as e:
            self.logger.error(f"💥 Error powering off VM {self.vm_name}: {e}")

    def power_on(self):
        """Power on the VM"""
        self.logger.info(f"🟢 OpenShift requesting POWER ON for VM: {self.vm_name}")
        
        if not self.vmware_client:
            self.logger.error(f"❌ No VMware client available for {self.vm_name}")
            return
            
        try:
            self.logger.info(f"⚡ Executing VMware power on for VM: {self.vm_name}")
            success = self.vmware_client.power_on_vm(self.vm_name)
            if success:
                self.powerstate = 'on'
                self.logger.info(f"✅ VM {self.vm_name} powered on successfully - OpenShift notified")
            else:
                self.logger.error(f"❌ Failed to power on VM {self.vm_name} - OpenShift will see error")
        except Exception as e:
            self.logger.error(f"💥 Error powering on VM {self.vm_name}: {e}")

    def power_reset(self):
        """Reset the VM"""
        self.logger.info(f"🔄 OpenShift requesting RESET for VM: {self.vm_name}")
        
        if not self.vmware_client:
            self.logger.error(f"❌ No VMware client available for {self.vm_name}")
            return
            
        try:
            self.logger.info(f"⚡ Executing VMware reset for VM: {self.vm_name}")
            success = self.vmware_client.reset_vm(self.vm_name)
            if success:
                self.powerstate = 'on'  # Reset leaves VM in powered on state
                self.logger.info(f"✅ VM {self.vm_name} reset successfully - OpenShift notified")
            else:
                self.logger.error(f"❌ Failed to reset VM {self.vm_name} - OpenShift will see error")
        except Exception as e:
            self.logger.error(f"💥 Error resetting VM {self.vm_name}: {e}")

    def power_shutdown(self):
        """Gracefully shutdown the VM"""
        if not self.vmware_client:
            logger.error(f"No VMware client available for {self.vm_name}")
            return
            
        try:
            logger.info(f"Gracefully shutting down VM: {self.vm_name}")
            success = self.vmware_client.power_off_vm(self.vm_name, force=False)
            if success:
                # Wait a bit for shutdown to complete
                time.sleep(5)
                self._update_power_state()
                logger.info(f"VM {self.vm_name} shutdown initiated")
            else:
                logger.error(f"Failed to shutdown VM {self.vm_name}")
        except Exception as e:
            logger.error(f"Error shutting down VM {self.vm_name}: {e}")

    def get_boot_device(self):
        """Get boot device"""
        self.logger.debug(f"🔍 OpenShift requesting boot device for VM {self.vm_name}")
        self.logger.info(f"📋 Reporting boot device to OpenShift: VM {self.vm_name} → {self.bootdevice}")
        return self.bootdevice

    def set_boot_device(self, bootdevice):
        """Set boot device"""
        self.logger.info(f"💾 OpenShift requesting boot device change for VM {self.vm_name}: {self.bootdevice} → {bootdevice}")
        
        if not self.vmware_client:
            self.logger.error(f"❌ No VMware client available for {self.vm_name}")
            return
            
        try:
            # Map IPMI boot devices to VMware boot devices
            device_map = {
                'network': 'network',
                'hd': 'disk',
                'disk': 'disk',
                'cdrom': 'cdrom',
                'cd': 'cdrom',
                'dvd': 'cdrom',
                'default': 'disk'
            }
            
            vmware_device = device_map.get(bootdevice.lower(), 'disk')
            self.logger.debug(f"🔄 Mapping IPMI device '{bootdevice}' → VMware device '{vmware_device}'")
            
            success = self.vmware_client.set_boot_device(self.vm_name, vmware_device)
            
            if success:
                old_device = self.bootdevice
                self.bootdevice = bootdevice
                self.logger.info(f"✅ Boot device changed for VM {self.vm_name}: {old_device} → {bootdevice} - OpenShift notified")
            else:
                self.logger.error(f"❌ Failed to set boot device for VM {self.vm_name} - OpenShift will see error")
                
        except Exception as e:
            self.logger.error(f"💥 Error setting boot device for VM {self.vm_name}: {e}")

    def mount_cdrom_iso(self, iso_path, datastore_name=None):
        """
        Mount ISO to VM's CDROM
        
        Args:
            iso_path: Path to ISO file
            datastore_name: Datastore name (optional)
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.vmware_client:
            logger.error(f"No VMware client available for {self.vm_name}")
            return False
            
        try:
            logger.info(f"Mounting ISO {iso_path} to VM {self.vm_name}")
            success = self.vmware_client.mount_iso(self.vm_name, iso_path, datastore_name)
            
            if success:
                logger.info(f"ISO {iso_path} mounted successfully to VM {self.vm_name}")
                return True
            else:
                logger.error(f"Failed to mount ISO to VM {self.vm_name}")
                return False
                
        except Exception as e:
            logger.error(f"Error mounting ISO to VM {self.vm_name}: {e}")
            return False

    def unmount_cdrom_iso(self):
        """
        Unmount ISO from VM's CDROM
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.vmware_client:
            logger.error(f"No VMware client available for {self.vm_name}")
            return False
            
        try:
            logger.info(f"Unmounting ISO from VM {self.vm_name}")
            success = self.vmware_client.unmount_iso(self.vm_name)
            
            if success:
                logger.info(f"ISO unmounted successfully from VM {self.vm_name}")
                return True
            else:
                logger.error(f"Failed to unmount ISO from VM {self.vm_name}")
                return False
                
        except Exception as e:
            logger.error(f"Error unmounting ISO from VM {self.vm_name}: {e}")
            return False

    def set_boot_from_cdrom(self):
        """
        Set VM to boot from CDROM
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info(f"Setting VM {self.vm_name} to boot from CDROM")
            # Set boot device to CDROM
            self.set_boot_device('cdrom')
            
            # Also set boot order to prioritize CDROM
            if hasattr(self.vmware_client, 'set_boot_order'):
                success = self.vmware_client.set_boot_order(self.vm_name, ['cdrom', 'disk', 'network'])
                if success:
                    logger.info(f"Boot order set to CDROM first for VM {self.vm_name}")
                else:
                    logger.warning(f"Failed to set boot order for VM {self.vm_name}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error setting CDROM boot for VM {self.vm_name}: {e}")
            return False

    def cold_reset(self):
        """Cold reset - just reset the VM, don't exit"""
        logger.info(f"Cold reset requested for VM: {self.vm_name}")
        self.power_reset()

    def get_sensor_data(self, sensorname):
        """
        Get sensor data for inspection
        OpenShift inspection uses this to validate hardware
        """
        self.logger.info(f"🔍 INSPECTION: OpenShift requesting sensor data for '{sensorname}' on VM {self.vm_name}")
        
        # Return fake but consistent sensor data for virtual machines
        # This helps with OpenShift inspection success
        fake_sensors = {
            'system_temp': {'value': 35, 'units': 'C', 'unavailable': False},
            'cpu_temp': {'value': 45, 'units': 'C', 'unavailable': False},
            'ambient_temp': {'value': 25, 'units': 'C', 'unavailable': False},
            'system_fan': {'value': 2000, 'units': 'RPM', 'unavailable': False},
            'cpu_fan': {'value': 2500, 'units': 'RPM', 'unavailable': False},
            'power_supply': {'value': 150, 'units': 'W', 'unavailable': False}
        }
        
        sensor_data = fake_sensors.get(sensorname.lower(), {'value': 0, 'units': '', 'unavailable': True})
        self.logger.info(f"📊 INSPECTION: Returning sensor data for VM {self.vm_name}: {sensorname} = {sensor_data}")
        
        return sensor_data

    def get_system_info(self):
        """
        Get system info for inspection
        """
        self.logger.info(f"🔍 INSPECTION: OpenShift requesting system info for VM {self.vm_name}")
        
        # Get VM info from VMware if possible
        try:
            if self.vmware_client:
                vm_info = self.vmware_client.get_vm_info(self.vm_name)
                if vm_info:
                    self.logger.info(f"📋 INSPECTION: VM {self.vm_name} - CPU: {vm_info.get('cpu', 'unknown')}, Memory: {vm_info.get('memory', 'unknown')} MB")
                    return vm_info
        except Exception as e:
            self.logger.warning(f"⚠️ Could not get VM info from VMware: {e}")
        
        # Return default system info for virtual environment
        default_info = {
            'manufacturer': 'VMware',
            'product': 'Virtual Machine',
            'version': '1.0',
            'cpu_count': 2,
            'memory_mb': 4096
        }
        
        self.logger.info(f"📋 INSPECTION: Returning default system info for VM {self.vm_name}: {default_info}")
        return default_info

    def get_fru_info(self, fru_id=0):
        """
        Get Field Replaceable Unit info for inspection
        """
        self.logger.info(f"🔍 INSPECTION: OpenShift requesting FRU info for VM {self.vm_name} (FRU ID: {fru_id})")
        
        # Return fake but valid FRU data for virtual machine
        fru_info = {
            'manufacturer': 'VMware Inc.',
            'product': f'Virtual Machine {self.vm_name}',
            'serial': f'VM-{self.vm_name.upper()}-{hash(self.vm_name) % 100000}',
            'version': '1.0'
        }
        
        self.logger.info(f"📋 INSPECTION: Returning FRU info for VM {self.vm_name}: {fru_info}")
        return fru_info

    def get_sel_info(self):
        """
        Get System Event Log info for inspection
        """
        self.logger.info(f"🔍 INSPECTION: OpenShift requesting SEL info for VM {self.vm_name}")
        
        # Return empty/minimal SEL info for virtual machine
        sel_info = {
            'entries': 0,
            'free_space': 100,
            'most_recent': 0,
            'supported': True
        }
        
        self.logger.info(f"📋 INSPECTION: Returning SEL info for VM {self.vm_name}: {sel_info}")
        return sel_info

    # Override specific IPMI commands that are failing during inspection
    def get_sdr_info(self):
        """Override SDR info - return minimal but valid response"""
        self.logger.info(f"🔍 INSPECTION: OpenShift requesting SDR info for VM {self.vm_name}")
        return {'entries': 0, 'free_space': 100, 'supported': False}

    def get_fru_inventory(self):
        """Override FRU inventory - return minimal but valid response"""
        self.logger.info(f"🔍 INSPECTION: OpenShift requesting FRU inventory for VM {self.vm_name}")
        return []

    def get_lan_config(self, channel=1):
        """Override LAN config - return minimal but valid response"""
        self.logger.info(f"🔍 INSPECTION: OpenShift requesting LAN config for VM {self.vm_name} (channel {channel})")
        return {
            'ipsrc': 1,  # Static IP
            'ipaddr': '192.168.1.100',
            'netmask': '255.255.255.0',
            'gateway': '192.168.1.1'
        }

    def handle_request(self, request, sockaddr):
        """Override to handle inspection commands that are failing"""
        try:
            # Extract client information safely
            if hasattr(sockaddr, 'clientsockaddr') and sockaddr.clientsockaddr:
                client_info = f"{sockaddr.clientsockaddr[0]}:{sockaddr.clientsockaddr[1]}"
            elif isinstance(sockaddr, (list, tuple)) and len(sockaddr) >= 2:
                client_info = f"{sockaddr[0]}:{sockaddr[1]}"
            else:
                client_info = "unknown"
                
            # Check for specific inspection commands that need special handling
            if hasattr(request, 'command') and hasattr(request, 'netfn'):
                self.logger.debug(f"🎯 IPMI REQUEST from OpenShift at {client_info} → VM {self.vm_name}")
                self.logger.debug(f"📋 NetFn: 0x{request.netfn:02x}, Command: 0x{request.command:02x}")
                
                # Handle specific problematic commands
                if request.netfn == 0x0A and request.command == 0x10:  # Get FRU Inventory Area Info
                    self.logger.info(f"🔍 INSPECTION: Handling FRU Inventory request for VM {self.vm_name}")
                    # Return a proper response indicating no FRU data
                    return None  # Let pyghmi handle with default response
                elif request.netfn == 0x04 and request.command == 0x20:  # Get SDR
                    self.logger.info(f"🔍 INSPECTION: Handling SDR request for VM {self.vm_name}")
                    # Return response indicating no SDR entries  
                    return None  # Let pyghmi handle with default response
                elif request.netfn == 0x0A and request.command == 0x42:  # Get SEL Info
                    self.logger.info(f"🔍 INSPECTION: Handling SEL Info request for VM {self.vm_name}")
                    # Return minimal SEL info
                    return None  # Let pyghmi handle with default response
                elif request.netfn == 0x0C and request.command == 0x02:  # Get LAN Configuration
                    self.logger.info(f"🔍 INSPECTION: Handling LAN Config request for VM {self.vm_name}")
                    # Return valid LAN config
                    return None  # Let pyghmi handle with default response
            
            # For all other requests, use the parent handler
            response = super().handle_request(request, sockaddr)
            return response
            
        except Exception as e:
            self.logger.error(f"❌ Error handling request from {client_info}: {e}")
            # Return a generic success response to avoid breaking inspection
            return super().handle_request(request, sockaddr)

def check_port_availability(config):
    """Check if configured ports are available on IPv4"""
    import socket
    
    logger.info("🔍 Checking IPv4 port availability...")
    
    for vm_config in config.get('vms', []):
        vm_name = vm_config.get('name', 'unknown')
        port = vm_config.get('port', 623)
        
        try:
            # Try to bind to the port on IPv4 only
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP for IPMI
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('0.0.0.0', port))
            sock.close()
            
            logger.info(f"✅ IPv4 Port {port} (VM: {vm_name}): Available")
                
        except PermissionError:
            logger.error(f"❌ Port {port} (VM: {vm_name}): Permission denied (must run as root)")
        except OSError as e:
            if "Address already in use" in str(e):
                logger.error(f"❌ Port {port} (VM: {vm_name}): Already in use")
                # Try to find what's using the port
                try:
                    import subprocess
                    result = subprocess.run(['netstat', '-tulpn'], capture_output=True, text=True)
                    for line in result.stdout.split('\n'):
                        if f':{port} ' in line:
                            logger.info(f"📋 Port usage: {line.strip()}")
                except:
                    pass
            else:
                logger.error(f"❌ Port {port} (VM: {vm_name}): {e}")

def load_config(config_file=None):
    """Load configuration from JSON file"""
    # Try multiple config paths (production only)
    if config_file:
        config_paths = [config_file]
    else:
        config_paths = [
            '/home/lchiaret/git/ipmi-vmware/config/config.json',  # Production config
            '/opt/ipmi-vmware-bridge/config.json',               # Production path
            'config/config.json',                                # Relative path
            'config.json'                                        # Fallback
        ]
    
    for config_path in config_paths:
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                logger.info(f"✅ Configuration loaded from {config_path}")
                
                # Validate that we're running as root
                if os.geteuid() != 0:
                    logger.error(f"❌ This service must run as root for IPMI standard ports")
                    logger.error(f"� Run with: sudo ./ipmi-bridge")
                    sys.exit(1)
                
                # Log port information
                if 'vms' in config:
                    ports = [vm.get('port', 'unknown') for vm in config['vms']]
                    logger.info(f"✅ Using IPMI standard ports: {ports} (running as root)")
                
                return config
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON in configuration file {config_path}: {e}")
        except Exception as e:
            logger.debug(f"📁 Could not load config from {config_path}: {e}")
    
    logger.error(f"❌ No valid configuration file found in any of: {config_paths}")
    return None

def main():
    """Main function to start the IPMI VMware bridge"""
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='IPMI VMware Bridge - OpenShift Virtualization Integration')
    parser.add_argument('--config', '-c', help='Configuration file path')
    parser.add_argument('--dev', action='store_true', help='Use development config with non-privileged ports')
    parser.add_argument('--test-config', action='store_true', help='Test configuration and exit')
    parser.add_argument('--check-ports', action='store_true', help='Check if ports are available')
    args = parser.parse_args()
    
    # Determine config file
    config_file = None
    if args.dev:
        config_file = 'config/config-dev.json'
        logger.info("� Development mode: Using non-privileged ports")
    elif args.config:
        config_file = args.config
        logger.info(f"📁 Using custom config: {config_file}")
    
    logger.info("�🚀 Starting IPMI VMware Bridge Service")
    logger.info("📡 This bridge will receive IPMI calls from OpenShift Virtualization BMH (BareMetalHost) resources")
    
    # Load configuration
    config = load_config(config_file)
    if not config:
        logger.error("❌ Failed to load configuration. Exiting.")
        logger.info("💡 Try: ./ipmi-bridge --dev  (for development with non-privileged ports)")
        sys.exit(1)
    
    # Test configuration and exit if requested
    if args.test_config:
        vm_count = len(config.get('vms', []))
        logger.info(f"✅ Configuration test passed: {vm_count} VMs configured")
        return
    
    # Check port availability if requested
    if args.check_ports:
        check_port_availability(config)
        return
    
    # Log configuration summary
    vm_count = len(config.get('vms', []))
    logger.info(f"📋 Configuration loaded: {vm_count} VMs configured")
    
    # Start BMC instances for each VM
    bmc_instances = []
    threads = []
    
    try:
        for i, vm_config in enumerate(config['vms']):
            try:
                vm_name = vm_config.get('name', f'VM-{i}')
                port = vm_config.get('port', 623 + i)
                
                logger.info(f"🎯 Setting up BMC {i+1}/{vm_count} for VM '{vm_name}' on port {port}")
                
                # Create authentication data
                authdata = {
                    vm_config.get('ipmi_user', 'admin'): vm_config.get('ipmi_password', 'password')
                }
                
                # Create BMC instance
                bmc_instance = VMwareBMC(authdata, port, vm_config)
                bmc_instances.append(bmc_instance)
                
                # Start BMC in separate thread
                thread = threading.Thread(target=bmc_instance.listen, daemon=True, name=f"BMC-{vm_name}")
                thread.start()
                threads.append(thread)
                
                logger.info(f"✅ BMC started for VM '{vm_name}' on port {port}")
                logger.info(f"🔗 OpenShift BMH can connect to: IPMI over LAN+ at port {port}")
                
            except PermissionError as e:
                if port < 1024:
                    logger.error(f"❌ Permission denied for VM {vm_name} on port {port}")
                    logger.error(f"🔒 Port {port} requires root privileges")
                    logger.info(f"💡 Solution: Run as root -> sudo ./ipmi-bridge")
                else:
                    logger.error(f"❌ Permission denied for VM {vm_name} on port {port}: {e}")
            except OSError as e:
                if "Address already in use" in str(e):
                    logger.error(f"❌ Port {port} already in use for VM {vm_name}")
                    logger.info(f"💡 Check if another IPMI service is running: sudo netstat -tulpn | grep {port}")
                else:
                    logger.error(f"❌ Network error for VM {vm_name} on port {port}: {e}")
            except Exception as e:
                logger.error(f"❌ Failed to start BMC for VM {vm_config.get('name', 'unknown')}: {e}")
                if "permission" in str(e).lower():
                    logger.info(f"💡 Try running as root: sudo ./ipmi-bridge")
        
        if not bmc_instances:
            logger.error("❌ No BMC instances started. Exiting.")
            sys.exit(1)
            
        logger.info(f"🎉 IPMI VMware Bridge started successfully!")
        logger.info(f"📊 Active BMC instances: {len(bmc_instances)}")
        logger.info(f"🔧 Debug mode: {'ENABLED' if debug_enabled else 'DISABLED'}")
        logger.info(f"📡 Ready to receive IPMI calls from OpenShift Virtualization")
        
        # Keep the main thread alive
        try:
            while True:
                time.sleep(10)
                # Check if any threads died
                for i, thread in enumerate(threads):
                    if not thread.is_alive():
                        logger.warning(f"🔄 BMC thread {i} died, restarting...")
                        vm_config = config['vms'][i]
                        authdata = {
                            vm_config.get('ipmi_user', 'admin'): vm_config.get('ipmi_password', 'password')
                        }
                        bmc_instance = VMwareBMC(authdata, vm_config['port'], vm_config)
                        thread = threading.Thread(target=bmc_instance.listen, daemon=True, name=f"BMC-{vm_config['name']}")
                        thread.start()
                        threads[i] = thread
                        bmc_instances[i] = bmc_instance
                        logger.info(f"✅ BMC thread restarted for VM {vm_config['name']}")
                        
        except KeyboardInterrupt:
            logger.info("🛑 Received interrupt signal, shutting down...")
            
    except Exception as e:
        logger.error(f"💥 Unexpected error in main: {e}")
        sys.exit(1)
    
    finally:
        # Cleanup
        logger.info("🧹 Cleaning up resources...")
        for i, bmc_instance in enumerate(bmc_instances):
            try:
                if hasattr(bmc_instance, 'vmware_client') and bmc_instance.vmware_client:
                    bmc_instance.vmware_client.disconnect()
                    logger.debug(f"🔌 Disconnected VMware client for BMC {i}")
            except Exception as e:
                logger.warning(f"⚠️ Error during cleanup for BMC {i}: {e}")
        
        logger.info("🏁 IPMI VMware Bridge stopped")

if __name__ == '__main__':
    main()
