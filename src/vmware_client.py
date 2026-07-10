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

from pyVmomi import vim

from vmware.connection import VMwareConnection
from vmware.vm_operations import VMOperations
from vmware.power_operations import PowerOperations
from vmware.media_operations import MediaOperations
from utils.logging_config import log_performance_metric, create_debug_context

logger = logging.getLogger(__name__)


def _is_connection_error(exc):
    """Return True when an exception indicates a dead or expired vSphere session."""
    if isinstance(exc, vim.fault.NotAuthenticated):
        return True
    err_str = str(exc)
    return (
        'NotAuthenticated' in err_str
        or 'not authenticated' in err_str.lower()
        or 'connection reset by peer' in err_str.lower()
        or 'broken pipe' in err_str.lower()
        or 'connection refused' in err_str.lower()
        or 'connection aborted' in err_str.lower()
        or 'Socket is closed' in err_str
    )


def _record_health(vm_name, operation_name, success, duration):
    """Record VMware operation metrics for the health endpoint."""
    try:
        from utils.health_monitor import health_monitor
        health_monitor.record_vm_operation(vm_name, operation_name, success=success, duration=duration)
    except Exception as e:
        logger.debug(f"Could not record health stats: {e}")


def track_vmware_operation(operation_name):
    """Decorator to track VMware operations with timing, logging and auto-reconnect on connection loss."""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            start_time = time.time()
            vm_name = args[0] if args and isinstance(args[0], str) else 'unknown'

            logger.info(f"🔧 [{operation_name}] Starting for VM: {vm_name}")
            logger.debug(f"📋 [{operation_name}] Args: {args}, Kwargs: {kwargs}")

            def _execute():
                return func(self, *args, **kwargs)

            try:
                self.connection.ensure_authenticated()
                result = _execute()
                duration = time.time() - start_time
                if result is False:
                    logger.error(f"❌ [{operation_name}] Failed for VM: {vm_name} after {duration:.3f}s")
                    log_performance_metric(logger, operation_name, duration, False, vm_name=vm_name)
                    _record_health(vm_name, operation_name, False, duration)
                    return result
                logger.info(f"✅ [{operation_name}] Completed for VM: {vm_name} in {duration:.3f}s")
                log_performance_metric(logger, operation_name, duration, True, vm_name=vm_name)
                _record_health(vm_name, operation_name, True, duration)
                return result

            except Exception as e:
                if not _is_connection_error(e):
                    duration = time.time() - start_time
                    logger.error(f"❌ [{operation_name}] Failed for VM: {vm_name} after {duration:.3f}s: {e}")
                    log_performance_metric(logger, operation_name, duration, False,
                                         vm_name=vm_name, error=str(e))
                    _record_health(vm_name, operation_name, False, duration)
                    raise

                logger.warning(f"⚠️ [{operation_name}] Connection lost ({e}), reconnecting and retrying...")
                try:
                    self.connection.reconnect()
                    self._refresh_module_connections()
                    result = _execute()
                    duration = time.time() - start_time
                    if result is False:
                        logger.error(f"❌ [{operation_name}] Failed after reconnect for VM: {vm_name} after {duration:.3f}s")
                        log_performance_metric(logger, operation_name, duration, False, vm_name=vm_name)
                        _record_health(vm_name, operation_name, False, duration)
                        return result
                    logger.info(f"✅ [{operation_name}] Completed after reconnect for VM: {vm_name} in {duration:.3f}s")
                    log_performance_metric(logger, operation_name, duration, True, vm_name=vm_name)
                    _record_health(vm_name, operation_name, True, duration)
                    return result
                except Exception as retry_e:
                    duration = time.time() - start_time
                    logger.error(f"❌ [{operation_name}] Failed after reconnect for VM: {vm_name} after {duration:.3f}s: {retry_e}")
                    log_performance_metric(logger, operation_name, duration, False,
                                         vm_name=vm_name, error=str(retry_e))
                    _record_health(vm_name, operation_name, False, duration)
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
        self.host = host
        self.user = user
        self.port = port

        if disable_ssl is not None:
            disable_ssl_verification = disable_ssl
        elif disable_ssl_verification is None:
            disable_ssl_verification = True

        self.disable_ssl_verification = disable_ssl_verification

        logger.info(f"🔗 Initializing VMware client for {host}:{port}")
        logger.info(f"👤 User: {user}, SSL Verification: {'Disabled' if disable_ssl_verification else 'Enabled'}")

        try:
            with create_debug_context()('VMware Connection Initialization'):
                self.connection = VMwareConnection(host, user, password, port, disable_ssl_verification)
                self.vm_ops = VMOperations(self.connection)
                self.power_ops = PowerOperations(self.connection, self.vm_ops)
                self.media_ops = MediaOperations(self.connection, self.vm_ops)

            logger.info(f"✅ VMware client initialized successfully for {host}")

        except Exception as e:
            logger.error(f"❌ Failed to initialize VMware client for {host}: {e}")
            logger.debug("📍 Connection error details:", exc_info=True)
            raise

    def _refresh_module_connections(self):
        """Propagate a new connection object to all operation modules after reconnect."""
        self.vm_ops.connection = self.connection
        self.power_ops.connection = self.connection
        self.media_ops.connection = self.connection

    def disconnect(self):
        """Disconnect from VMware vSphere"""
        logger.info(f"🔌 Disconnecting from VMware host: {self.host}")
        try:
            self.connection.disconnect()
            logger.info(f"✅ Successfully disconnected from {self.host}")
        except Exception as e:
            logger.warning(f"⚠️ Error during disconnection from {self.host}: {e}")

    def is_connected(self):
        """Check if connection is active"""
        try:
            return self.connection.is_connection_alive()
        except Exception as e:
            logger.warning(f"⚠️ Error checking connection status for {self.host}: {e}")
            return False

    @track_vmware_operation("List VMs")
    def list_vms(self):
        """List all virtual machines"""
        vms = self.vm_ops.list_vms()
        logger.info(f"📊 Found {len(vms)} VMs on {self.host}")
        return vms

    @track_vmware_operation("Get VM Info")
    def get_vm_info(self, vm_name):
        """Get detailed VM information"""
        vm_info = self.vm_ops.get_vm_info(vm_name)
        if vm_info:
            logger.info(f"✅ VM info retrieved for {vm_name}: Power={vm_info.get('power_state', 'unknown')}")
        else:
            logger.warning(f"⚠️ VM not found: {vm_name}")
        return vm_info

    @track_vmware_operation("Power On VM")
    def power_on_vm(self, vm_name):
        """Power on a virtual machine"""
        return self.power_ops.power_on_vm(vm_name)

    @track_vmware_operation("Power Off VM")
    def power_off_vm(self, vm_name):
        """Power off a virtual machine (hard power off)"""
        return self.power_ops.power_off_vm(vm_name)

    @track_vmware_operation("Reset VM")
    def reset_vm(self, vm_name):
        """Reset a virtual machine (hard reset)"""
        return self.power_ops.reset_vm(vm_name)

    @track_vmware_operation("Shutdown VM")
    def shutdown_vm(self, vm_name):
        """Gracefully shutdown a virtual machine using VMware Tools"""
        return self.power_ops.shutdown_vm(vm_name)

    @track_vmware_operation("Restart VM")
    def restart_vm(self, vm_name):
        """Gracefully restart a virtual machine using VMware Tools"""
        return self.power_ops.restart_vm(vm_name)

    @track_vmware_operation("Set VM Boot Order")
    def set_vm_boot_order(self, vm_name, boot_order):
        """Set VM boot order"""
        return self.media_ops.set_vm_boot_order(vm_name, boot_order)

    @track_vmware_operation("Mount ISO")
    def mount_iso(self, vm_name, iso_path):
        """Mount ISO to VM's CD/DVD drive"""
        return self.media_ops.mount_iso(vm_name, iso_path)

    @track_vmware_operation("Upload ISO")
    def upload_iso_to_datastore(self, source_url: str, datastore_path: str) -> bool:
        """Download an ISO from source_url and upload it to the vSphere datastore."""
        return self.media_ops.upload_iso_to_datastore(source_url, datastore_path)

    @track_vmware_operation("Unmount ISO")
    def unmount_iso(self, vm_name, force=False):
        """Unmount ISO from VM's CD/DVD drive"""
        return self.media_ops.unmount_iso(vm_name, force=force)

    @track_vmware_operation("Delete Datastore File")
    def delete_datastore_file(self, datastore_path: str) -> bool:
        """Delete a file from a vSphere datastore."""
        return self.media_ops.delete_datastore_file(datastore_path)

    def datastore_file_exists(self, datastore_path: str) -> bool:
        """Check whether a file exists on a vSphere datastore."""
        return self.media_ops.datastore_file_exists(datastore_path)

    @track_vmware_operation("Get ISO Status")
    def get_iso_status(self, vm_name):
        """Get ISO mount status"""
        return self.media_ops.get_iso_status(vm_name)

    def get_connection_stats(self):
        """Get connection statistics and health information"""
        try:
            stats = {
                'host': self.host,
                'port': self.port,
                'user': self.user,
                'ssl_verification_disabled': self.disable_ssl_verification,
                'connected': self.is_connected(),
            }
            logger.debug(f"📊 Connection stats: {stats}")
            return stats
        except Exception as e:
            logger.error(f"❌ Failed to get connection stats: {e}")
            return {'error': str(e)}
