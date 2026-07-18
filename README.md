# Redfish-VMware Bridge

Redfish REST API bridge for VMware vSphere. Translates Metal3/Ironic Redfish calls into pyVmomi operations so OpenShift can manage VMware VMs as bare metal hosts.

Architecture priorities Metal3 compatibility over generic Redfish compliance.

## Architecture

One Redfish HTTP(S) server serves all VMs on a single port (`redfish_port`, default `8443`). VM selection is by URI path:

```text
https://bmc-host:8443/redfish/v1/Systems/<vcenter-vm-name>
```

Optional `datacenter_folders` in config enables periodic auto-discovery from vCenter folder paths.

## Quick start (Podman)

This is the recommended deployment method (used in production BMC VMs).

### 1. Prepare directories

```bash
mkdir -p /root/redfish-vmware/config /etc/redfish-vmware/ssl
```

### 2. Create config

```bash
cp config/config.json.example /root/redfish-vmware/config/config.json
# Edit vCenter credentials, VM list, SSL paths, datastore
```

See [Configuration](#configuration).

### 3. TLS certificates

Metal3 rejects `http://` BMC addresses (webhook). Use TLS:

```bash
# Example self-signed cert for lab use
openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
  -keyout /etc/redfish-vmware/ssl/server.key \
  -out /etc/redfish-vmware/ssl/server.crt \
  -subj "/CN=gil-bare-bmc.example.com"
```

Set in `config.json`:

```json
{
  "disable_ssl": false,
  "ssl": {
    "cert_path": "/etc/redfish-vmware/ssl/server.crt",
    "key_path": "/etc/redfish-vmware/ssl/server.key"
  },
  "redfish_port": 8443
}
```

On BareMetalHost, set `disableCertificateVerification: true` when using self-signed certs.

### 4. Build and run

From the repository root:

```bash
podman build -t localhost/redfish-vmware:latest -f Containerfile .

podman rm -f redfish-vmware 2>/dev/null || true
podman run -d \
  --name redfish-vmware \
  --restart=always \
  -p 8443:8443 \
  -v /root/redfish-vmware/config:/app/config:Z \
  -v /etc/redfish-vmware/ssl:/etc/redfish-vmware/ssl:Z \
  localhost/redfish-vmware:latest
```

### 5. Verify

```bash
curl -sk -u admin:password \
  https://127.0.0.1:8443/redfish/v1/Systems/<vcenter-vm-name> | python3 -m json.tool

podman logs -f redfish-vmware
```

### Useful Podman commands

```bash
podman restart redfish-vmware
podman logs --tail 100 redfish-vmware
podman exec -it redfish-vmware cat /app/config/config.json
# Rebuild after code changes
podman build -t localhost/redfish-vmware:latest -f Containerfile .
podman rm -f redfish-vmware
# then podman run ... as above
```

## Configuration

Copy `config/config.json.example` to `config/config.json` (never commit real credentials).

| Key | Purpose |
|-----|---------|
| `vmware` | Default vCenter host/user/password |
| `vms` | Explicit VM list; `name` must match vCenter **exactly** |
| `datacenter_folders` | Optional auto-discovery of VMs under folder paths |
| `redfish_port` | Listen port (default `8443`) |
| `disable_ssl` | `false` for HTTPS (required for Metal3) |
| `ssl.cert_path` / `ssl.key_path` | TLS material paths inside the container |
| `virtual_media_datastore` | Datastore path for uploaded ISOs, e.g. `[vsanDatastore] iso/` |
| `delete_on_eject` | Delete ISO from datastore after eject |
| `datacenter_folder_refresh_interval_seconds` | Folder re-scan interval (default `300`) |

Environment overrides (all default **off** / production-quiet):

| Variable | Purpose |
|----------|---------|
| `REDFISH_PORT` | Override listen port |
| `REDFISH_DEBUG=true` | Verbose request/access logging (use only while troubleshooting) |
| `REDFISH_PERF_DEBUG=true` | Performance metrics |
| `REDFISH_VMWARE_DEBUG=true` | VMware operation details |

Production containers and systemd units leave these unset/`false`. For investigation on a BMC VM:

```bash
podman run -d ... -e REDFISH_DEBUG=true localhost/redfish-vmware:latest
# or: sudo systemctl edit redfish-vmware-server  →  Environment=REDFISH_DEBUG=true
```

## OpenShift Metal3 integration

### BMC address format

Always use virtual media scheme (not `http://`):

```text
redfish-virtualmedia://<bmc-fqdn>:8443/redfish/v1/Systems/<vcenter-vm-name>
```

Example BareMetalHost fragment:

```yaml
spec:
  bmc:
    address: redfish-virtualmedia://gil-bare-bmc.example.com:8443/redfish/v1/Systems/lchiaret-gil-bare-worker-0
    credentialsName: gil-bare-bmc-secret
    disableCertificateVerification: true
  bootMACAddress: "00:50:56:af:77:cc"
  bootMode: UEFI
  automatedCleaningMode: metadata   # OCP 4.22: only metadata|disabled
```

### Naming rule

The Redfish System ID must equal the **vCenter VM name**. Provisioner blank VMs are often created as `{username}-{name}` (e.g. `lchiaret-gil-bare-worker-0`). Put that exact string in `config.json` `vms[].name` and in the BMH BMC path.

### Credentials

Default / legacy: `admin` / `password`. Per-VM pairs from `redfish_user` / `redfish_password` in config are also accepted.

### What Metal3 uses on this bridge

- Power: `ComputerSystem.Reset` (On, ForceOff, GracefulShutdown, ...)
- Boot override: `PATCH /Systems/{id}` (`Cd`, `Hdd`, `Pxe`)
- Virtual media: InsertMedia / EjectMedia on Managers `{id}-bmc`
- Inspection stubs: SecureBoot GET, Bios GET, Storage, EthernetInterfaces, UpdateService, TaskService

Disk cleaning during deprovision is performed by Ironic IPA inside the VM, not by this bridge. On OCP 4.22, BMH `automatedCleaningMode` supports only `metadata` and `disabled` (not `full`).

## Alternative: systemd (host Python)

For non-container installs, `./setup.sh` can install a venv and systemd unit. Prefer Podman for BMC VMs.

```bash
sudo ./setup.sh
sudo systemctl enable --now redfish-vmware-server
sudo journalctl -u redfish-vmware-server -f
```

Debug via drop-in:

```bash
sudo systemctl edit redfish-vmware-server
# [Service]
# Environment=REDFISH_DEBUG=true
sudo systemctl restart redfish-vmware-server
```

## Development

```bash
# Local run
python3 src/redfish_server.py --config config/config.json

# Tests
PYTHONPATH=. python3 -m unittest tests.test_redfish_server
```

### Repository layout

```text
src/
  redfish_server.py      # Entry point
  vmware_client.py       # VMware facade (info cache, auto-reconnect)
  handlers/              # Redfish routers
  vmware/                # pyVmomi operations
  auth/ tasks/ models/ utils/
config/
  config.json.example
Containerfile            # Podman/Docker image
tests/
  test_redfish_server.py
openshift/               # BMH examples
```

## Troubleshooting

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| Webhook: `Unknown BMC type 'http'` | Using `http://` BMC URL | Use `redfish-virtualmedia://` |
| `HTTPS on HTTP port` / SSL errors | `disable_ssl: true` or missing `ssl` section | Enable TLS; mount certs; restart container |
| Redfish 404 on System | Name mismatch | System ID must match vCenter VM name exactly |
| BMH stuck `registering` | Network / TLS / auth | `curl -sk -u admin:password https://bmc:8443/redfish/v1/Systems/...` from masters |
| Slow eject / deprovision | vSAN CD question / timeout | Check `podman logs redfish-vmware`; eject retries up to 60s |
| Power state lag in BMH | Poll vs vCenter | Bridge caches VM info for 5s; power ops invalidate cache |
| Port in use | Another process on 8443 | `ss -tlnp \| grep 8443` |

## License / notes

AI-generated codebase intended for Metal3 lab and production-style bare metal workflows on VMware. Not a full Redfish compliance suite.
