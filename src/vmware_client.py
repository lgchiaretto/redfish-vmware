#!/usr/bin/env python3
"""
Enhanced VMware vSphere Client

This module provides an enhanced client interface to VMware vSphere for VM operations
with detailed logging, performance monitoring, and operation tracking.
Used by the Redfish server to perform actual VM management operations.
"""

import logging
import time
from functools import wraps

from vmware.connection import VMwareConnection
from vmware.vm_operations import VMOperations
from vmware.power_operations import PowerOperations
from vmware.media_operations import MediaOperations
from utils.logging_config import log_vmware_operation, log_performance_metric, create_debug_context

logger = logging.getLogger(__name__)


def track_vmware_operation(operation_name):
    """Decorator to track VMware operations with timing and logging"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            start_time = time.time()
            vm_name = getattr(self, '_current_vm_name', 'unknown')
            
            # Log operation start
            logger.info(f"🔧 [{operation_name}] Starting for VM: {vm_name}")
            logger.debug(f"📋 [{operation_name}] Args: {args}, Kwargs: {kwargs}")
            
            try:
                # Execute the operation
                result = func(self, *args, **kwargs)
                
                # Log success
                duration = time.time() - start_time
                logger.info(f"✅ [{operation_name}] Completed for VM: {vm_name} in {duration:.3f}s")
                log_performance_metric(logger, operation_name, duration, True, vm_name=vm_name)
                
                return result
                
            except Exception as e:
                # Log failure
                duration = time.time() - start_time
                logger.error(f"❌ [{operation_name}] Failed for VM: {vm_name} after {duration:.3f}s: {e}")
                log_performance_metric(logger, operation_name, duration, False, 
                                     vm_name=vm_name, error=str(e))
                raise
        
        return wrapper
    return decorator


class VMwareClient:
    """
    Enhanced VMware vSphere client for VM operations with comprehensive debugging
    """
    
    def __init__(self, host, user, password, port=443, disable_ssl_verification=None, disable_ssl=None):
        """
        Initialize Enhanced VMware client
        
        Args:
            host: vCenter/ESXi host
            user: Username
            password: Password (will be masked in logs)
            port: Connection port
            disable_ssl_verification: Disable SSL verification (deprecated)
            disable_ssl: Disable SSL verification (new name)
        """
        self._current_vm_name = None
        self.host = host
        self.user = user
        self.port = port
        
        # Handle both parameter names for backward compatibility
        if disable_ssl is not None:
            disable_ssl_verification = disable_ssl
        elif disable_ssl_verification is not None:
            pass
        else:
            disable_ssl_verification = True
        
        self.disable_ssl_verification = disable_ssl_verification
        
        logger.info(f"🔗 Initializing VMware client for {host}:{port}")
        logger.info(f"👤 User: {user}, SSL Verification: {'Disabled' if disable_ssl_verification else 'Enabled'}")
        
        try:
            with create_debug_context()('VMware Connection Initialization'):
                # Initialize connection
                self.connection = VMwareConnection(host, user, password, port, disable_ssl_verification)
                
                # Initialize operation modules
                self.vm_ops = VMOperations(self.connection)
                self.power_ops = PowerOperations(self.connection, self.vm_ops)
                self.media_ops = MediaOperations(self.connection, self.vm_ops)
                
            logger.info(f"✅ VMware client initialized successfully for {host}")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize VMware client for {host}: {e}")
            logger.debug(f"📍 Connection error details:", exc_info=True)
            raise
    
    def set_current_vm(self, vm_name):
        """Set the current VM name for logging context"""
        self._current_vm_name = vm_name
        logger.debug(f"🎯 Current VM context set to: {vm_name}")
    
    @track_vmware_operation("VMware Disconnect")
    def disconnect(self):
        """Disconnect from VMware vSphere with enhanced logging"""
        logger.info(f"🔌 Disconnecting from VMware host: {self.host}")
        try:
            self.connection.disconnect()
            logger.info(f"✅ Successfully disconnected from {self.host}")
        except Exception as e:
            logger.warning(f"⚠️ Error during disconnection from {self.host}: {e}")
    
    def is_connected(self):
        """Check if connection is active with enhanced logging"""
        try:
            connected = self.connection.is_connected()
            logger.debug(f"🔍 Connection status for {self.host}: {'Connected' if connected else 'Disconnected'}")
            return connected
        except Exception as e:
            logger.warning(f"⚠️ Error checking connection status for {self.host}: {e}")
            return False
    
    @track_vmware_operation("List VMs")
    def list_vms(self):
        """List all VMs with enhanced logging"""
        logger.debug(f"📋 Listing all VMs on {self.host}")
        try:
            vms = self.vm_ops.list_vms()
            logger.info(f"📊 Found {len(vms)} VMs on {self.host}")
            
            # Log VM details in debug mode
            for vm in vms:
                logger.debug(f"  📦 VM: {vm}")
            
            return vms
        except Exception as e:
            logger.error(f"❌ Failed to list VMs on {self.host}: {e}")
            raise
    
    @track_vmware_operation("Get VM Info")
    def get_vm_info(self, vm_name):
        """Get VM information with enhanced logging"""
        self.set_current_vm(vm_name)
        logger.debug(f"🔍 Getting info for VM: {vm_name}")
        
        try:
            vm_info = self.vm_ops.get_vm_info(vm_name)
            if vm_info:
                logger.info(f"✅ VM info retrieved for {vm_name}: Power={vm_info.get('power_state', 'unknown')}")
                logger.debug(f"📋 Full VM info for {vm_name}: {vm_info}")
            else:
                logger.warning(f"⚠️ VM not found: {vm_name}")
            return vm_info
        except Exception as e:
            logger.error(f"❌ Failed to get VM info for {vm_name}: {e}")
            raise
    
    @track_vmware_operation("Power On VM")
    def power_on_vm(self, vm_name):
        """Power on VM with enhanced logging"""
        self.set_current_vm(vm_name)
        logger.info(f"⚡ Powering on VM: {vm_name}")
        
        try:
            result = self.power_ops.power_on(vm_name)
            logger.info(f"✅ Power on command sent for VM: {vm_name}")
            return result
        except Exception as e:
            logger.error(f"❌ Failed to power on VM {vm_name}: {e}")
            raise
    
    @track_vmware_operation("Power Off VM")
    def power_off_vm(self, vm_name):
        """Power off VM with enhanced logging"""
        self.set_current_vm(vm_name)
        logger.info(f"🔌 Powering off VM: {vm_name}")
        
        try:
            result = self.power_ops.power_off(vm_name)
            logger.info(f"✅ Power off command sent for VM: {vm_name}")
            return result
        except Exception as e:
            logger.error(f"❌ Failed to power off VM {vm_name}: {e}")
            raise
    
    @track_vmware_operation("Reset VM")
    def reset_vm(self, vm_name):
        """Reset VM with enhanced logging"""
        self.set_current_vm(vm_name)
        logger.info(f"🔄 Resetting VM: {vm_name}")
        
        try:
            result = self.power_ops.reset(vm_name)
            logger.info(f"✅ Reset command sent for VM: {vm_name}")
            return result
        except Exception as e:
            logger.error(f"❌ Failed to reset VM {vm_name}: {e}")
            raise
    
    @track_vmware_operation("Shutdown VM")
    def shutdown_vm(self, vm_name):
        """Gracefully shutdown VM with enhanced logging"""
        self.set_current_vm(vm_name)
        logger.info(f"🛑 Gracefully shutting down VM: {vm_name}")
        
        try:
            result = self.power_ops.shutdown(vm_name)
            logger.info(f"✅ Shutdown command sent for VM: {vm_name}")
            return result
        except Exception as e:
            logger.error(f"❌ Failed to shutdown VM {vm_name}: {e}")
            raise
    
    @track_vmware_operation("Mount ISO")
    def mount_iso(self, vm_name, iso_path):
        """Mount ISO with enhanced logging"""
        self.set_current_vm(vm_name)
        logger.info(f"💿 Mounting ISO for VM {vm_name}: {iso_path}")
        
        try:
            result = self.media_ops.mount_iso(vm_name, iso_path)
            logger.info(f"✅ ISO mounted successfully for VM {vm_name}")
            return result
        except Exception as e:
            logger.error(f"❌ Failed to mount ISO for VM {vm_name}: {e}")
            raise
    
    @track_vmware_operation("Unmount ISO")
    def unmount_iso(self, vm_name):
        """Unmount ISO with enhanced logging"""
        self.set_current_vm(vm_name)
        logger.info(f"💿 Unmounting ISO for VM: {vm_name}")
        
        try:
            result = self.media_ops.unmount_iso(vm_name)
            logger.info(f"✅ ISO unmounted successfully for VM {vm_name}")
            return result
        except Exception as e:
            logger.error(f"❌ Failed to unmount ISO for VM {vm_name}: {e}")
            raise
    
    @track_vmware_operation("Get ISO Status")
    def get_iso_status(self, vm_name):
        """Get ISO mount status with enhanced logging"""
        self.set_current_vm(vm_name)
        logger.debug(f"🔍 Checking ISO status for VM: {vm_name}")
        
        try:
            status = self.media_ops.get_iso_status(vm_name)
            logger.debug(f"📋 ISO status for VM {vm_name}: {status}")
            return status
        except Exception as e:
            logger.error(f"❌ Failed to get ISO status for VM {vm_name}: {e}")
            raise
    
    def get_connection_stats(self):
        """Get connection statistics and health information"""
        try:
            stats = {
                'host': self.host,
                'port': self.port,
                'user': self.user,
                'ssl_verification_disabled': self.disable_ssl_verification,
                'connected': self.is_connected(),
                'current_vm_context': self._current_vm_name
            }
            
            logger.debug(f"📊 Connection stats: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"❌ Failed to get connection stats: {e}")
            return {'error': str(e)}
    
    # Connection methods
    def disconnect(self):
        """Disconnect from VMware vSphere"""
        self.connection.disconnect()
    
    def is_connected(self):
        """Check if connection is active"""
        return self.connection.is_connected()
    
    # VM discovery and information methods
    def get_vm(self, vm_name):
        """Get VM object by name"""
        return self.vm_ops.get_vm(vm_name)
    
    def list_vms(self):
        """List all virtual machines"""
        return self.vm_ops.list_vms()
    
    def get_vm_info(self, vm_name):
        """Get detailed VM information"""
        return self.vm_ops.get_vm_info(vm_name)
    
    def get_vm_power_state(self, vm_name):
        """Get VM power state"""
        return self.vm_ops.get_vm_power_state(vm_name)
    
    # Power management methods
    def power_on_vm(self, vm_name):
        """Power on a virtual machine"""
        return self.power_ops.power_on_vm(vm_name)
    
    def power_off_vm(self, vm_name):
        """Power off a virtual machine (hard power off)"""
        return self.power_ops.power_off_vm(vm_name)
    
    def reset_vm(self, vm_name):
        """Reset a virtual machine (hard reset)"""
        return self.power_ops.reset_vm(vm_name)
    
    def shutdown_vm(self, vm_name):
        """Gracefully shutdown a virtual machine using VMware Tools"""
        return self.power_ops.shutdown_vm(vm_name)
    
    def restart_vm(self, vm_name):
        """Gracefully restart a virtual machine using VMware Tools"""
        return self.power_ops.restart_vm(vm_name)
    
    # Virtual media methods
    def set_vm_boot_order(self, vm_name, boot_order):
        """Set VM boot order"""
        return self.media_ops.set_vm_boot_order(vm_name, boot_order)
    
    def mount_iso(self, vm_name, iso_path):
        """Mount ISO to VM's CD/DVD drive"""
        return self.media_ops.mount_iso(vm_name, iso_path)
    
    def unmount_iso(self, vm_name):
        """Unmount ISO from VM's CD/DVD drive"""
        return self.media_ops.unmount_iso(vm_name)
    
    # Legacy method support for backward compatibility
    def _wait_for_task(self, task):
        """Wait for a vCenter task to complete (legacy support)"""
        return self.power_ops._wait_for_task(task)
