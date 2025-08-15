#!/usr/bin/env python3
"""
Demo script that shows the IPMI-VMware Bridge in action
This script will test the entire workflow
"""

import time
import logging
import subprocess
import threading
import signal
import sys
from configparser import ConfigParser

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - DEMO - %(levelname)s - %(message)s'
    )

def start_server():
    """Start the IPMI server in background"""
    logger = logging.getLogger(__name__)
    logger.info("Starting IPMI-VMware Bridge server...")
    
    # Start server process
    process = subprocess.Popen([
        '/home/lchiaret/git/ipmi-vmware/.venv/bin/python', 
        'main.py'
    ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    
    # Give server time to start
    time.sleep(3)
    
    return process

def test_ipmi_commands():
    """Test IPMI commands"""
    logger = logging.getLogger(__name__)
    
    commands_to_test = [
        ('status', 'Get chassis status'),
        ('on', 'Power on VM'),
        ('status', 'Get status after power on'),
        ('off', 'Power off VM'),
        ('status', 'Get status after power off')
    ]
    
    for cmd, description in commands_to_test:
        logger.info(f"=== {description} ===")
        try:
            # We need to simulate the IP mapping, so use localhost as a source IP
            # The server will need to be modified to handle localhost mapping
            result = subprocess.run([
                '/home/lchiaret/git/ipmi-vmware/.venv/bin/python',
                'ipmi_client.py',
                'localhost',
                '--port', '6230',
                '--command', cmd
            ], capture_output=True, text=True, timeout=10)
            
            logger.info(f"Command output: {result.stdout.strip()}")
            if result.stderr:
                logger.warning(f"Command errors: {result.stderr.strip()}")
                
        except subprocess.TimeoutExpired:
            logger.error(f"Command '{cmd}' timed out")
        except Exception as e:
            logger.error(f"Error running command '{cmd}': {e}")
        
        # Wait between commands
        time.sleep(2)

def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("=== IPMI-VMware Bridge Demo ===")
    
    # First, let's add localhost mapping to config
    config = ConfigParser()
    config.read('config.ini')
    
    # Add localhost mapping for testing
    if not config.has_section('vm_mapping'):
        config.add_section('vm_mapping')
    
    config.set('vm_mapping', '127.0.0.1', 'TESTE1')
    config.set('vm_mapping', 'localhost', 'TESTE1')
    
    # Write updated config
    with open('config.ini', 'w') as f:
        config.write(f)
    
    logger.info("Updated config with localhost mapping")
    
    # Start server
    server_process = None
    
    try:
        server_process = start_server()
        
        logger.info("Server started, beginning IPMI tests...")
        
        # Test IPMI commands
        test_ipmi_commands()
        
        logger.info("Demo completed successfully!")
        
    except KeyboardInterrupt:
        logger.info("Demo interrupted by user")
    except Exception as e:
        logger.error(f"Demo failed: {e}")
    finally:
        # Clean up server
        if server_process:
            logger.info("Stopping server...")
            server_process.terminate()
            server_process.wait()

if __name__ == "__main__":
    main()
