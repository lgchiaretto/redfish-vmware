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

The `@track_vmware_operation` decorator on VMwareClient methods catches session expiry (`vim.fault.NotAuthenticated`), socket resets, and broken pipe errors, calls `connection.reconnect()`, refreshes sub-module references, and retries once.

## Step 1: Add to Existing Module or Create New

Choose the right module:
- `power_operations.py` - Power on/off/reset/shutdown
- `vm_operations.py` - VM discovery, info, folder listing
- `media_operations.py` - ISO upload, mount/unmount, boot order, datastore delete

```python
def new_operation(self, vm_name):
    try:
        vm = self.vm_operations.get_vm(vm_name)
        if not vm:
            logger.error(f"VM '{vm_name}' not found")
            return False

        logger.info(f"Performing operation on VM '{vm_name}'")
        task = vm.ReconfigVM_Task(spec)
        result = self._wait_for_task(task)
        return result
    except vim.fault.NotAuthenticated:
        raise  # CRITICAL: allows track_vmware_operation to reconnect and retry
    except Exception as e:
        logger.error(f"Error in operation for VM '{vm_name}': {e}")
        return False
```

## Step 2: Expose via VMwareClient Facade

In `src/vmware_client.py`:

```python
@track_vmware_operation("new_operation")
def new_operation(self, vm_name):
    return self.power_ops.new_operation(vm_name)
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
3. **Use `_wait_for_task()`** for async pyVmomi tasks; `_wait_for_task_with_questions()` when vSphere may prompt (CD eject)
4. **Re-raise `vim.fault.NotAuthenticated`** before broad `except Exception` in every public method
5. **Use the decorator** `@track_vmware_operation("name")` on facade methods
6. **Log**: intent before, result after, errors with exception

## Testing

```bash
# Quick VMware connectivity check
python3 -c "
from src.vmware_client import VMwareClient
client = VMwareClient('vcenter.host', 'user', 'pass')
print(client.get_vm_info('vm-name'))
"

# Add regression test if handler behaviour changes
PYTHONPATH=. python3 -m unittest tests.test_redfish_server
```
