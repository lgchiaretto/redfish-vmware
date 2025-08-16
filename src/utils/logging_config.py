#!/usr/bin/env python3
"""
Logging Configuration Module
Provides centralized logging configuration for the Redfish VMware Server.
"""

import logging
import os


def setup_logging():
    """Setup logging configuration"""
    # Configure logging with enhanced DEBUG level for detailed communication tracking
    debug_env = os.getenv('REDFISH_DEBUG', 'true').lower()  # Default to debug mode
    debug_enabled = debug_env in ['true', '1', 'yes', 'on']
    log_level = logging.DEBUG if debug_enabled else logging.INFO

    print(f"🐛 Debug Environment Variable: REDFISH_DEBUG={debug_env}")
    print(f"🐛 Debug Enabled: {debug_enabled}")
    print(f"🐛 Log Level: {log_level}")
    print(f"🔍 Enhanced Metal3/Ironic compatibility logging enabled")

    # Setup log file path - try multiple locations
    log_paths = [
        '/var/log/redfish-vmware-server.log',  # System log (requires root)
        os.path.expanduser('~/redfish-vmware-server.log'),  # User home
        './redfish-vmware-server.log'  # Current directory
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

    logger = logging.getLogger(__name__)

    if log_file:
        logger.info(f"📝 Logging to: {log_file}")

    if debug_enabled:
        logger.info("🐛 DEBUG MODE ENABLED - All Redfish calls will be logged in detail")
    else:
        logger.info("📋 PRODUCTION MODE - Limited logging enabled")

    return logger


def get_logger(name):
    """Get a logger with the given name"""
    return logging.getLogger(name)
