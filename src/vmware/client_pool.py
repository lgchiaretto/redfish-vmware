#!/usr/bin/env python3
"""
VMware Client Pool

Shares VMwareClient instances across VMs that use the same vCenter credentials.
"""

import logging
import threading
from typing import Dict, Optional, Tuple

from vmware_client import VMwareClient

logger = logging.getLogger(__name__)

PoolKey = Tuple[str, str, str, int, bool]


class VMwareClientPool:
    """Pool of shared VMwareClient instances keyed by vCenter connection details."""

    def __init__(self, config: Optional[Dict] = None):
        self._config = config or {}
        self._clients: Dict[PoolKey, VMwareClient] = {}
        self._lock = threading.Lock()

    @staticmethod
    def pool_key_for_vm(vm_config: Dict, config: Optional[Dict] = None) -> PoolKey:
        """Build a hashable pool key from VM and global config."""
        config = config or {}
        vmware_global = config.get('vmware', {})

        host = vm_config.get('vcenter_host') or vmware_global.get('host')
        user = vm_config.get('vcenter_user') or vmware_global.get('user')
        password = vm_config.get('vcenter_password') or vmware_global.get('password')
        port = vm_config.get('vcenter_port', vmware_global.get('port', 443))

        disable_ssl = vm_config.get('disable_ssl')
        if disable_ssl is None:
            disable_ssl = config.get('disable_ssl', vmware_global.get('disable_ssl', True))

        if not host or not user or not password:
            raise ValueError(
                f"Missing vCenter credentials for VM '{vm_config.get('name', 'unknown')}'"
            )

        return host, user, password, int(port), bool(disable_ssl)

    def sync_vm_clients(self, vm_configs: Dict[str, Dict], config: Optional[Dict] = None) -> Dict[str, VMwareClient]:
        """
        Build a vm_name -> VMwareClient mapping, reusing pooled clients where possible.

        Clients whose pool keys are no longer referenced by any VM are disconnected
        and removed from the pool.
        """
        if config is not None:
            self._config = config

        vmware_clients: Dict[str, VMwareClient] = {}
        active_keys = set()

        with self._lock:
            for vm_name, vm_config in vm_configs.items():
                try:
                    key = self.pool_key_for_vm(vm_config, self._config)
                    active_keys.add(key)

                    if key not in self._clients:
                        host, user, password, port, disable_ssl = key
                        self._clients[key] = VMwareClient(
                            host,
                            user,
                            password,
                            port=port,
                            disable_ssl=disable_ssl,
                        )
                        logger.info(
                            "✅ Pooled VMware client created for %s:%s (user: %s)",
                            host,
                            port,
                            user,
                        )

                    vmware_clients[vm_name] = self._clients[key]
                except Exception as e:
                    logger.error(f"❌ Failed to get pooled VMware client for {vm_name}: {e}")

            stale_keys = [key for key in self._clients if key not in active_keys]
            for key in stale_keys:
                client = self._clients.pop(key)
                host = key[0]
                try:
                    client.disconnect()
                    logger.info(f"🔌 Disconnected unused pooled VMware client for {host}")
                except Exception as e:
                    logger.warning(f"⚠️ Error disconnecting pooled VMware client for {host}: {e}")

        unique_clients = len({id(client) for client in vmware_clients.values()})
        logger.info(
            "🔗 VMware client pool: %d VM(s) mapped to %d shared connection(s)",
            len(vmware_clients),
            unique_clients,
        )
        return vmware_clients

    def disconnect_all(self):
        """Disconnect and remove all pooled VMware clients."""
        with self._lock:
            for key, client in list(self._clients.items()):
                host = key[0]
                try:
                    client.disconnect()
                    logger.info(f"🔌 Disconnected pooled VMware client for {host}")
                except Exception as e:
                    logger.warning(f"⚠️ Error disconnecting pooled VMware client for {host}: {e}")
            self._clients.clear()

    @property
    def pooled_client_count(self) -> int:
        """Return the number of active pooled VMware connections."""
        with self._lock:
            return len(self._clients)
