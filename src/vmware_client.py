#!/usr/bin/env python3
"""
VMware vSphere Client - First Version (AI-Generated)

Note: This application is AI-generated.

This module provides a client interface to VMware vSphere for VM operations.
Used by the Redfish server to perform actual VM management operations.
"""

import logging
from vmware.connection import VMwareConnection
from vmware.vm_operations import VMOperations
from vmware.power_operations import PowerOperations
from vmware.media_operations import MediaOperations

logger = logging.getLogger(__name__)


class VMwareClient:
    """
    VMware vSphere client for VM operations - Modularized version
    """
    
    def __init__(self, host, user, password, port=443, disable_ssl_verification=None, disable_ssl=None):
        """
        Initialize VMware client
        
        Args:
            host: vCenter/ESXi host
            user: Username
            password: Password
            port: Connection port
            disable_ssl_verification: Disable SSL verification (deprecated)
            disable_ssl: Disable SSL verification (new name)
        """
        # Handle both parameter names for backward compatibility
        if disable_ssl is not None:
            disable_ssl_verification = disable_ssl
        elif disable_ssl_verification is not None:
            pass  # Use the provided value
        else:
            disable_ssl_verification = True
        
        # Initialize connection
        self.connection = VMwareConnection(host, user, password, port, disable_ssl_verification)
        
        # Initialize operation modules
        self.vm_ops = VMOperations(self.connection)
        self.power_ops = PowerOperations(self.connection, self.vm_ops)
        self.media_ops = MediaOperations(self.connection, self.vm_ops)
        
        logger.info(f"✅ VMware client initialized for {host}")
    
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
