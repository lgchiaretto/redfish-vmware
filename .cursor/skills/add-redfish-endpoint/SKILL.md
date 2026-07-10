---
name: add-redfish-endpoint
description: Step-by-step guide to add new Redfish REST API endpoints to the bridge. Use when the user wants to add a new endpoint, route, resource, or API path to the Redfish server.
---

# Adding a New Redfish Endpoint

## Quick Reference

Files to modify (in order):
1. `src/models/redfish_schemas.py` - Add response model
2. `src/handlers/<resource>_handler.py` - Add handler logic (or create new handler)
3. `src/handlers/redfish_handler.py` - Register route in `_route_get_request()` / `_route_post_request()` / `_route_patch_request()`
4. `tests/test_redfish_server.py` - Add regression test

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
    }
```

Every response MUST have `@odata.type` and `@odata.id`.

## Step 2: Add Handler Logic

Handlers receive `(request_handler, path)` and extract VM name from the `{ID}` path segment under `/Systems/{ID}`.

Add a method to the appropriate handler in `src/handlers/`:

```python
def _handle_new_resource_get(self, request_handler, vm_name: str, path: str):
    data = RedfishModels.get_new_resource(vm_name)
    self._send_json_response(request_handler, 200, data)
```

For a new handler file, follow the pattern in `systems_handler.py` and instantiate in `RedfishHandler.__init__()`.

## Step 3: Register the Route

In `src/handlers/redfish_handler.py`:

```python
elif path.startswith('/redfish/v1/NewResource'):
    if not self._check_auth(request_handler):
        return
    self.new_handler.handle_get(request_handler, path)
```

Add similar routing in `_route_post_request()` and `_route_patch_request()` if needed.

## Step 4: Add Regression Test

In `tests/test_redfish_server.py`, add a test class or method covering the new endpoint:

```bash
PYTHONPATH=. python3 -m unittest tests.test_redfish_server
```

## Step 5: Manual Test

```bash
# All VMs on single port — select VM via path
curl -u admin:password http://localhost:8443/redfish/v1/NewResource/vm-name
```

## Metal3 Compatibility Checklist

- [ ] Response includes `@odata.type` and `@odata.id`
- [ ] Collection responses include `Members@odata.count` and `Members` array
- [ ] Error responses use the standard Redfish error format
- [ ] Endpoint accessible with Basic auth (Metal3 sends credentials from BMH Secret)
- [ ] Endpoint handles missing VMs with 404
- [ ] Regression test added and passing
