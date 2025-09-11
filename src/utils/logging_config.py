#!/usr/bin/env python3
"""
Enhanced Logging Configuration Module
Provides comprehensive logging configuration for the Redfish VMware Server
with advanced debugging capabilities and performance monitoring.
"""

import logging
import logging.handlers
import os
import sys
import threading
import time
from datetime import datetime


class PerformanceFilter(logging.Filter):
    """Filter to add performance metrics to log records"""
    
    def __init__(self):
        super().__init__()
        self.start_time = time.time()
        self.request_count = 0
        self.lock = threading.Lock()
    
    def filter(self, record):
        with self.lock:
            self.request_count += 1
            record.uptime = time.time() - self.start_time
            record.request_count = self.request_count
            record.thread_name = threading.current_thread().name
        return True


class VmwareContextFilter(logging.Filter):
    """Filter to add VMware operation context to log records"""
    
    def filter(self, record):
        # Add context information if available
        if hasattr(record, 'vm_name'):
            record.msg = f"[VM: {record.vm_name}] {record.msg}"
        if hasattr(record, 'operation'):
            record.msg = f"[OP: {record.operation}] {record.msg}"
        return True


def setup_logging():
    """Setup enhanced logging configuration with advanced debugging features"""
    # Get configuration from environment
    debug_env = os.getenv('REDFISH_DEBUG', 'false').lower()
    debug_enabled = debug_env in ['true', '1', 'yes', 'on']
    
    # Get additional debug options
    performance_debug = os.getenv('REDFISH_PERF_DEBUG', 'false').lower() in ['true', '1', 'yes', 'on']
    vmware_debug = os.getenv('REDFISH_VMWARE_DEBUG', 'false').lower() in ['true', '1', 'yes', 'on']
    
    # Set log level based on debug settings
    if debug_enabled:
        log_level = logging.DEBUG
    elif vmware_debug:
        log_level = logging.INFO  # Moderate logging for VMware operations
    else:
        log_level = logging.INFO
    
    # Print startup information
    print(f"🐛 Debug Environment Variables:")
    print(f"   REDFISH_DEBUG={debug_env} (General debug: {debug_enabled})")
    print(f"   REDFISH_PERF_DEBUG={os.getenv('REDFISH_PERF_DEBUG', 'false')} (Performance debug: {performance_debug})")
    print(f"   REDFISH_VMWARE_DEBUG={os.getenv('REDFISH_VMWARE_DEBUG', 'false')} (VMware debug: {vmware_debug})")
    print(f"� Log Level: {logging.getLevelName(log_level)}")
    print(f"🔍 Enhanced debugging capabilities enabled")
    print(f"� Performance monitoring: {'ON' if performance_debug else 'OFF'}")
    print(f"⚡ VMware operation tracking: {'ON' if vmware_debug else 'OFF'}")

    # Setup log file paths with rotation
    log_dir = os.getenv('REDFISH_LOG_DIR', '/var/log')
    log_paths = [
        os.path.join(log_dir, 'redfish-vmware-server.log'),
        os.path.expanduser('~/redfish-vmware-server.log'),
        './redfish-vmware-server.log'
    ]

    log_file = None
    for path in log_paths:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'a') as f:
                pass
            log_file = path
            break
        except (PermissionError, FileNotFoundError, OSError):
            continue

    # Create handlers
    handlers = []
    
    # Console handler with color support
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    handlers.append(console_handler)
    
    # File handler with rotation if log file is available
    if log_file:
        # Use rotating file handler to prevent large log files
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, 
            maxBytes=50*1024*1024,  # 50MB
            backupCount=5
        )
        file_handler.setLevel(logging.DEBUG if debug_enabled else logging.INFO)
        handlers.append(file_handler)

    # Enhanced log formats
    if debug_enabled:
        log_format = (
            '%(asctime)s - %(levelname)s - %(name)s - '
            '[%(filename)s:%(lineno)d] - [%(thread_name)s] - '
            '[Uptime: %(uptime).1fs] - [Req: %(request_count)d] - %(message)s'
        )
    elif performance_debug:
        log_format = (
            '%(asctime)s - %(levelname)s - [%(thread_name)s] - '
            '[Uptime: %(uptime).1fs] - %(message)s'
        )
    else:
        log_format = '%(asctime)s - %(levelname)s - %(message)s'

    # Configure formatters
    formatter = logging.Formatter(log_format)
    for handler in handlers:
        handler.setFormatter(formatter)
        
        # Add filters for enhanced debugging
        if performance_debug or debug_enabled:
            handler.addFilter(PerformanceFilter())
        if vmware_debug or debug_enabled:
            handler.addFilter(VmwareContextFilter())

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        handlers=handlers,
        format=log_format
    )

    # Get main logger
    logger = logging.getLogger(__name__)

    # Log startup information
    if log_file:
        logger.info(f"📝 Logging to: {log_file}")
        if isinstance(handlers[1], logging.handlers.RotatingFileHandler):
            logger.info(f"🔄 Log rotation enabled: 50MB max, 5 backups")

    # Log debug mode status
    if debug_enabled:
        logger.info("🐛 FULL DEBUG MODE ENABLED - All operations will be logged in detail")
        logger.info("📊 Performance metrics included in logs")
        logger.info("🔍 VMware operations context included")
    elif performance_debug:
        logger.info("📊 PERFORMANCE DEBUG MODE - Performance metrics enabled")
    elif vmware_debug:
        logger.info("⚡ VMWARE DEBUG MODE - VMware operations tracking enabled")
    else:
        logger.info("📋 PRODUCTION MODE - Standard logging enabled")

    # Configure third-party library logging
    configure_third_party_logging(debug_enabled, vmware_debug)

    return logger


def configure_third_party_logging(debug_enabled, vmware_debug):
    """Configure logging for third-party libraries"""
    # Reduce noise from third-party libraries unless in full debug mode
    if not debug_enabled:
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('requests').setLevel(logging.WARNING)
        logging.getLogger('pyVmomi').setLevel(logging.WARNING)
        logging.getLogger('suds').setLevel(logging.WARNING)
    
    # VMware-specific logging
    if vmware_debug or debug_enabled:
        logging.getLogger('vmware').setLevel(logging.DEBUG)
        logging.getLogger('pyVim').setLevel(logging.INFO)
    else:
        logging.getLogger('vmware').setLevel(logging.WARNING)
        logging.getLogger('pyVim').setLevel(logging.WARNING)


def get_logger(name):
    """Get a logger with the given name and add contextual information"""
    logger = logging.getLogger(name)
    return logger


def log_vmware_operation(logger, operation, vm_name=None, **kwargs):
    """Log VMware operations with context"""
    extra = {'operation': operation}
    if vm_name:
        extra['vm_name'] = vm_name
    
    # Add additional context
    for key, value in kwargs.items():
        extra[key] = value
    
    return logger


def log_performance_metric(logger, operation, duration, success=True, **kwargs):
    """Log performance metrics for operations"""
    status = "✅" if success else "❌"
    message = f"{status} {operation} completed in {duration:.3f}s"
    
    if kwargs:
        details = ", ".join(f"{k}={v}" for k, v in kwargs.items())
        message += f" ({details})"
    
    logger.info(message)


def create_debug_context():
    """Create a context manager for debug operations"""
    class DebugContext:
        def __init__(self, operation_name):
            self.operation_name = operation_name
            self.start_time = None
            self.logger = get_logger(__name__)
        
        def __enter__(self):
            self.start_time = time.time()
            self.logger.debug(f"🔧 Starting operation: {self.operation_name}")
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            duration = time.time() - self.start_time
            if exc_type is None:
                self.logger.debug(f"✅ Operation completed: {self.operation_name} ({duration:.3f}s)")
            else:
                self.logger.error(f"❌ Operation failed: {self.operation_name} ({duration:.3f}s) - {exc_val}")
    
    return DebugContext
