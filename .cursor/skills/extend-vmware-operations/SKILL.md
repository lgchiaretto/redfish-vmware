---
name: extend-vmware-operations
description: Guide to add new VMware vSphere operations to the bridge. Use when the user wants to add VM management capabilities, new VMware API calls, or extend the VMware client.
---

# Extending VMware Operations

## Architecture

```
VMwareClient (facade)  →  PowerOperations   →  VMwareConnection
                       →  VMOperations       →  VMwareConnection
                       →  MediaOperations    →  VMwareConnection
                       →  [YourNewModule]    →  VMwareConnection
```

## Step 1: Add to Existing Module or Create New

### Adding to an existing module

Choose the right module:
- `power_operations.py` - Power on/off/reset/shutdown
- `vm_operations.py` - VM discovery, info, listing
- `media_operations.py` - ISO mount/unmount, boot order

```python
def new_operation(self, vm_name):
    try:
        vm = self.vm_operations.get_vm(vm_name)
        if not vm:
            logger.error(f"VM '{vm_name}' not found")
            return False

        logger.info(f"Performing operation on VM '{vm_name}'")

        # pyVmomi operation
        task = vm.ReconfigVM_Task(spec)
        result = self._wait_for_task(task)

        if result:
            logger.info(f"Successfully completed on VM '{vm_name}'")
        return result
    except Exception as e:
        logger.error(f"Error in operation for VM '{vm_name}': {e}")
        return False
```

### Creating a new module

Create `src/vmware/new_operations.py`:

```python
#!/usr/bin/env python3
"""New VMware Operations"""

import logging

logger = logging.getLogger(__name__)

class NewOperations:
    def __init__(self, connection, vm_operations):
        self.connection = connection
        self.vm_operations = vm_operations

    def _wait_for_task(self, task, timeout=120):
        """Wait for vSphere task completion"""
        import time
        start = time.time()
        while task.info.state not in ['success', 'error']:
            if time.time() - start > timeout:
                logger.error("Task timed out")
                return False
            time.sleep(1)
        return task.info.state == 'success'
```

## Step 2: Expose via VMwareClient Facade

In `src/vmware_client.py`:

```python
from vmware.new_operations import NewOperations

class VMwareClient:
    def __init__(self, host, username, password, ...):
        # ... existing init ...
        self.new_ops = NewOperations(self.connection, self.vm_ops)

    @track_vmware_operation("new_operation")
    def new_operation(self, vm_name):
        return self.new_ops.new_operation(vm_name)
```

## Step 3: Call from Handler

In the appropriate handler (e.g. `systems_handler.py`):

```python
vmware_client = self.vmware_clients.get(vm_name)
if vmware_client:
    success = vmware_client.new_operation(vm_name)
    if success:
        self._send_json_response(request_handler, 200, {"status": "ok"})
    else:
        self._send_error_response(request_handler, 500, "Operation failed")
else:
    self._send_error_response(request_handler, 503, "VMware client unavailable")
```

## Key Rules

1. **Always return bool** from VMware operations
2. **Always handle `None` VM** (vm not found)
3. **Use `_wait_for_task()`** for async pyVmomi tasks
4. **Log**: intent before, result after, errors with exception
5. **Use the decorator** `@track_vmware_operation("name")` on facade methods

## Common pyVmomi Patterns

```python
from pyVmomi import vim

# Reconfigure VM
spec = vim.vm.ConfigSpec()
spec.numCPUs = 4
task = vm.ReconfigVM_Task(spec=spec)

# Get VM property
power_state = vm.runtime.powerState  # 'poweredOn', 'poweredOff', 'suspended'
memory_mb = vm.config.hardware.memoryMB
num_cpus = vm.config.hardware.numCPU
guest_id = vm.config.guestId

# List devices
for device in vm.config.hardware.device:
    if isinstance(device, vim.vm.device.VirtualDisk):
        # disk operations
```

## Testing

```bash
# Quick VMware connectivity check
python3 -c "
from src.vmware_client import VMwareClient
client = VMwareClient('vcenter.host', 'user', 'pass')
print(client.get_vm_info('vm-name'))
"
```
