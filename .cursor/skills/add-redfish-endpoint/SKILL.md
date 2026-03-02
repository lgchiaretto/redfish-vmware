---
name: add-redfish-endpoint
description: Step-by-step guide to add new Redfish REST API endpoints to the bridge. Use when the user wants to add a new endpoint, route, resource, or API path to the Redfish server.
---

# Adding a New Redfish Endpoint

## Quick Reference

Files to modify (in order):
1. `src/models/redfish_schemas.py` - Add response model
2. `src/handlers/<resource>_handler.py` - Add handler logic (or create new handler)
3. `src/handlers/redfish_handler.py` - Register route

## Step 1: Define the Response Model

Add a static method to `RedfishModels` in `src/models/redfish_schemas.py`:

```python
@staticmethod
def get_new_resource(resource_id: str) -> Dict:
    return {
        '@odata.type': '#ResourceType.v1_0_0.ResourceType',
        '@odata.id': f'/redfish/v1/NewResource/{resource_id}',
        'Id': resource_id,
        'Name': f'Resource {resource_id}',
        # Add resource-specific fields
    }
```

Every response MUST have `@odata.type` and `@odata.id`.

## Step 2: Add Handler Logic

### Option A: Add to existing handler

Add a method to the appropriate handler in `src/handlers/`:

```python
def _handle_new_resource_get(self, request_handler, vm_name: str, path: str):
    data = RedfishModels.get_new_resource(vm_name)
    self._send_json_response(request_handler, 200, data)
```

Then route to it in the handler's `handle_get()`:

```python
elif '/NewResource' in path:
    self._handle_new_resource_get(request_handler, vm_name, path)
```

### Option B: Create a new handler

Create `src/handlers/new_handler.py` following the pattern in `systems_handler.py`:

```python
class NewHandler:
    def __init__(self, vm_configs: Dict, vmware_clients: Dict, task_manager=None):
        self.vm_configs = vm_configs
        self.vmware_clients = vmware_clients
        self.task_manager = task_manager

    def handle_get(self, request_handler, path: str):
        # Parse path and dispatch
        ...

    def _send_json_response(self, request_handler, status_code, data):
        response = json.dumps(data, indent=2)
        request_handler.send_response(status_code)
        request_handler.send_header('Content-Type', 'application/json')
        request_handler.send_header('Content-Length', str(len(response)))
        request_handler.end_headers()
        request_handler.wfile.write(response.encode())

    def _send_error_response(self, request_handler, status_code, message):
        error_data = {"error": {"code": f"Base.1.0.{status_code}", "message": message}}
        self._send_json_response(request_handler, status_code, error_data)
```

## Step 3: Register the Route

In `src/handlers/redfish_handler.py`:

1. Import the new handler (if new file)
2. Instantiate in `__init__()` (if new handler)
3. Add routing in `_route_get_request()`:

```python
elif path.startswith('/redfish/v1/NewResource'):
    if not self._check_auth(request_handler):
        return
    self.new_handler.handle_get(request_handler, path)
```

Add similar routing in `_route_post_request()` and `_route_patch_request()` if needed.

## Step 4: Test

```bash
# Public endpoint (no auth)
curl http://localhost:8443/redfish/v1/NewResource

# Authenticated endpoint
curl -u admin:password http://localhost:8443/redfish/v1/NewResource/vm-name

# POST action
curl -u admin:password -X POST -H "Content-Type: application/json" \
  -d '{"param": "value"}' \
  http://localhost:8443/redfish/v1/NewResource/vm-name/Actions/Action.Name
```

## Metal3 Compatibility Checklist

- [ ] Response includes `@odata.type` and `@odata.id`
- [ ] Collection responses include `Members@odata.count` and `Members` array
- [ ] Error responses use the standard Redfish error format
- [ ] Endpoint is accessible when auth is required (Metal3 sends Basic auth)
- [ ] Endpoint handles missing VMs with 404
