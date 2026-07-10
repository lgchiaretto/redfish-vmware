#!/usr/bin/env python3
"""
Server health monitoring for VMware operation statistics.
"""

import logging
import threading
import time

logger = logging.getLogger(__name__)


class ServerHealthMonitor:
    """Monitor server health and VMware operation performance metrics."""

    def __init__(self):
        self.start_time = time.time()
        self.vm_stats = {}
        self.error_count = 0
        self.lock = threading.Lock()

    def record_vm_operation(self, vm_name, operation, success=True, duration=0):
        """Record VM operation statistics."""
        with self.lock:
            if vm_name not in self.vm_stats:
                self.vm_stats[vm_name] = {
                    'total_operations': 0,
                    'successful_operations': 0,
                    'failed_operations': 0,
                    'average_response_time': 0,
                    'last_operation': None,
                    'last_operation_time': None,
                }

            stats = self.vm_stats[vm_name]
            stats['total_operations'] += 1
            stats['last_operation'] = operation
            stats['last_operation_time'] = time.time()

            if success:
                stats['successful_operations'] += 1
            else:
                stats['failed_operations'] += 1
                self.error_count += 1

            if stats['average_response_time'] == 0:
                stats['average_response_time'] = duration
            else:
                stats['average_response_time'] = (stats['average_response_time'] + duration) / 2

    def get_health_stats(self):
        """Get comprehensive health statistics."""
        with self.lock:
            uptime = time.time() - self.start_time
            total_operations = sum(vm['total_operations'] for vm in self.vm_stats.values())
            total_successful = sum(vm['successful_operations'] for vm in self.vm_stats.values())

            request_statistics = {}
            try:
                from handlers.http_handler import get_request_statistics
                request_statistics = get_request_statistics()
            except Exception as e:
                logger.debug(f"Could not load request statistics: {e}")

            return {
                'uptime_seconds': uptime,
                'uptime_human': self._format_uptime(uptime),
                'total_operations': total_operations,
                'successful_operations': total_successful,
                'failed_operations': self.error_count,
                'success_rate': (total_successful / total_operations * 100) if total_operations > 0 else 0,
                'operations_per_minute': (total_operations / uptime) * 60 if uptime > 0 else 0,
                'vm_statistics': self.vm_stats.copy(),
                'request_statistics': request_statistics,
            }

    def _format_uptime(self, seconds):
        """Format uptime in human readable format."""
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"


health_monitor = ServerHealthMonitor()
