#!/usr/bin/env python3
"""
Simple IPMI client for testing the IPMI-VMware Bridge
This simulates basic IPMI commands
"""

import socket
import logging
import argparse

class SimpleIPMIClient:
    def __init__(self, host, port=623):
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.logger = logging.getLogger(__name__)
    
    def send_command(self, netfn, command, payload=b''):
        """Send IPMI command and return response"""
        try:
            # Build simple IPMI message
            message = bytes([
                0x00,  # Auth type
                0x01,  # Sequence
                0x00,  # Session ID
                len(payload) + 2,  # Message length
                netfn,  # NetFn
                command  # Command
            ]) + payload
            
            self.logger.info(f"Sending to {self.host}:{self.port} - NetFn: 0x{netfn:02x}, Cmd: 0x{command:02x}")
            self.logger.debug(f"Raw message: {message.hex()}")
            
            # Send message
            self.socket.sendto(message, (self.host, self.port))
            
            # Wait for response (with timeout)
            self.socket.settimeout(5.0)
            response, addr = self.socket.recvfrom(1024)
            
            self.logger.info(f"Response received from {addr}")
            self.logger.debug(f"Raw response: {response.hex()}")
            
            return response
            
        except socket.timeout:
            self.logger.error("Timeout waiting for response")
            return None
        except Exception as e:
            self.logger.error(f"Error sending command: {e}")
            return None
    
    def chassis_power_on(self):
        """Send chassis power on command"""
        self.logger.info("Sending chassis power on command")
        return self.send_command(0x00, 0x02, bytes([0x01]))  # NetFn=Chassis, Cmd=Control, Payload=PowerOn
    
    def chassis_power_off(self):
        """Send chassis power off command"""
        self.logger.info("Sending chassis power off command")
        return self.send_command(0x00, 0x02, bytes([0x00]))  # NetFn=Chassis, Cmd=Control, Payload=PowerOff
    
    def chassis_reset(self):
        """Send chassis reset command"""
        self.logger.info("Sending chassis reset command")
        return self.send_command(0x00, 0x02, bytes([0x03]))  # NetFn=Chassis, Cmd=Control, Payload=HardReset
    
    def get_chassis_status(self):
        """Get chassis status"""
        self.logger.info("Getting chassis status")
        return self.send_command(0x00, 0x01)  # NetFn=Chassis, Cmd=GetStatus
    
    def close(self):
        """Close socket"""
        self.socket.close()

def main():
    parser = argparse.ArgumentParser(description='Simple IPMI Client for testing')
    parser.add_argument('host', help='IPMI server host')
    parser.add_argument('--port', type=int, default=623, help='IPMI server port')
    parser.add_argument('--command', choices=['status', 'on', 'off', 'reset'], 
                       default='status', help='Command to send')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger(__name__)
    
    # Create client
    client = SimpleIPMIClient(args.host, args.port)
    
    try:
        logger.info(f"Connecting to IPMI server at {args.host}:{args.port}")
        
        # Send command based on argument
        if args.command == 'status':
            response = client.get_chassis_status()
        elif args.command == 'on':
            response = client.chassis_power_on()
        elif args.command == 'off':
            response = client.chassis_power_off()
        elif args.command == 'reset':
            response = client.chassis_reset()
        
        if response:
            logger.info("Command completed successfully")
            if len(response) > 6:
                completion_code = response[6] if len(response) > 6 else 0xFF
                logger.info(f"Completion code: 0x{completion_code:02x}")
                if completion_code == 0x00:
                    logger.info("Command executed successfully on remote VM")
                else:
                    logger.warning("Command may have failed on remote VM")
        else:
            logger.error("No response received")
            
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    main()
