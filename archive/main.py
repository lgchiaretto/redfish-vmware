#!/usr/bin/env python3
"""
IPMI-VMware Bridge
Main application that simulates IPMI and controls VMware VMs
"""

import sys
import logging
import configparser
import argparse
import signal
import os
from ipmi_server import IPMIServer
from vmware_client import VMwareClient

def setup_logging(config):
    """Configure logging system"""
    log_level = config.get('logging', 'level', fallback='INFO')
    log_file = config.get('logging', 'file', fallback='ipmi_vmware.log')
    
    # Create logs directory if it doesn't exist
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )

def load_config(config_file='config.ini'):
    """Load configuration from config file"""
    config = configparser.ConfigParser()
    
    # Try to read config file
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    
    config.read(config_file)
    return config

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger = logging.getLogger(__name__)
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    sys.exit(0)

def validate_config(config):
    """Validate configuration parameters"""
    logger = logging.getLogger(__name__)
    
    # Check required VMware settings
    required_vmware = ['vcenter_host', 'username', 'password']
    for setting in required_vmware:
        if not config.get('vmware', setting, fallback=None):
            raise ValueError(f"Missing required VMware setting: {setting}")
    
    # Check IPMI port
    port = config.getint('ipmi', 'listen_port', fallback=623)
    if port < 1 or port > 65535:
        raise ValueError(f"Invalid IPMI port: {port}")
    
    # Warn about privileged ports
    if port < 1024 and os.geteuid() != 0:
        logger.warning(f"Port {port} requires root privileges. Consider using port > 1024")
    
    # Check if VM mapping exists
    if not config.has_section('vm_mapping'):
        logger.warning("No VM mapping configured. Service will start but won't handle any requests.")
    
    logger.info("Configuration validation passed")

def main():
    parser = argparse.ArgumentParser(description='IPMI-VMware Bridge')
    parser.add_argument('--config', default='config.ini', help='Configuration file')
    parser.add_argument('--test-vmware', action='store_true', help='Test VMware connection')
    parser.add_argument('--validate-config', action='store_true', help='Validate configuration and exit')
    parser.add_argument('--daemon', action='store_true', help='Run as daemon (systemd mode)')
    args = parser.parse_args()
    
    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Load configuration
        config = load_config(args.config)
        setup_logging(config)
        
        logger = logging.getLogger(__name__)
        logger.info("Starting IPMI-VMware Bridge...")
        
        # Validate configuration
        validate_config(config)
        
        if args.validate_config:
            logger.info("Configuration is valid")
            return 0
        
        # Create VMware client
        vmware_client = VMwareClient(config)
        
        if args.test_vmware:
            vmware_client.test_connection()
            logger.info("VMware connection test completed")
            return 0
        
        # Start IPMI server
        logger.info("Starting IPMI server...")
        ipmi_server = IPMIServer(config, vmware_client)
        
        if args.daemon:
            logger.info("Running in daemon mode")
        
        # This will block until interrupted
        ipmi_server.start()
        
    except KeyboardInterrupt:
        logger.info("Stopping application (user interrupt)...")
        return 0
    except FileNotFoundError as e:
        print(f"Configuration error: {e}")
        return 1
    except ValueError as e:
        print(f"Configuration error: {e}")
        return 1
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Fatal error: {e}")
        return 1
    finally:
        logger = logging.getLogger(__name__)
        logger.info("Application stopped")

if __name__ == "__main__":
    sys.exit(main())
