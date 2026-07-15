---
name: deployment-setup
description: Guide for deploying, configuring, and managing the Redfish-VMware bridge server. Use when the user wants to install, configure, deploy, manage the systemd service, set up SSL, or configure the application.
---

# Deployment and Setup

## Prerequisites

- Python 3.11+
- Access to VMware vCenter
- Network connectivity between server and vCenter
- Linux with systemd (RHEL/Fedora/CentOS recommended)

## Quick Start (Development)

```bash
# 1. Install dependencies
pip3 install -r requirements.txt

# 2. Create config from template
cp config/config.json.example config/config.json
# Edit config/config.json with your vCenter and VM details

# 3. Run
python3 src/redfish_server.py --config config/config.json

# 4. With debug
REDFISH_DEBUG=true python3 src/redfish_server.py --config config/config.json
```

## Production Installation

Use `setup.sh` — it configures Python env, systemd, firewall, and validates VMware connectivity:

```bash
sudo ./setup.sh              # Full automated setup
sudo ./setup.sh --config-only  # Skip systemd and firewall
sudo ./setup.sh --test-only    # Test VMware connectivity only
```

Ensure `config/config.json` contains top-level `redfish_port` (or set `REDFISH_PORT` in the systemd unit).

## Configuration (`config/config.json`)

```json
{
  "vmware": {
    "host": "vcenter.example.com",
    "user": "administrator@vsphere.local",
    "password": "your-password",
    "port": 443,
    "disable_ssl": true
  },
  "vms": [
    {
      "name": "vm-master-0",
      "vcenter_host": "vcenter.example.com",
      "vcenter_user": "administrator@vsphere.local",
      "vcenter_password": "your-password",
      "redfish_user": "admin",
      "redfish_password": "password"
    }
  ],
  "datacenter_folders": [
    {
      "datacenter": "Datacenter1",
      "folder_path": "vm/prod/kubernetes"
    }
  ],
  "redfish_port": 8443,
  "disable_ssl": true,
  "datacenter_folder_refresh_interval_seconds": 300,
  "virtual_media_datastore": "DatastoreName",
  "delete_on_eject": false,
  "ssl": {
    "cert_path": "/etc/letsencrypt/live/host.example.com/fullchain.pem",
    "key_path": "/etc/letsencrypt/live/host.example.com/privkey.pem"
  }
}
```

### Key Config Rules

- **Single server port**: top-level `redfish_port` (default 8443) — NOT per-VM ports
- Config must contain `vms` and/or `datacenter_folders` (or both)
- `name` must match the VM name in vCenter exactly
- `disable_ssl: true` → HTTP mode (recommended for dev and Metal3)
- `datacenter_folders` enables auto-discovery; refresh interval defaults to 300 seconds
- `virtual_media_datastore` — datastore for ISO uploads during InsertMedia
- `delete_on_eject: false` — set true to auto-delete ISO from datastore on eject
- Per-VM `redfish_user`/`redfish_password` supported; legacy `admin:password` always accepted
- **Never commit** `config.json` to git (contains credentials)

### Datacenter Folder Discovery

Folder path format (case-sensitive):
- `vm` — all VMs in datacenter root
- `vm/prod` — VMs in `prod` subfolder
- `vm/prod/kubernetes` — nested folder (recursive)

Discovered VMs get `"discovered": true` metadata and default credentials. Stale VMs are pruned on refresh.

## systemd Service Management

```bash
sudo systemctl start redfish-vmware-server
sudo systemctl status redfish-vmware-server
sudo journalctl -u redfish-vmware-server -f

# Debug via environment override
sudo systemctl edit redfish-vmware-server
# [Service]
# Environment=REDFISH_DEBUG=true
# Environment=REDFISH_PORT=8443
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REDFISH_DEBUG` | `false` | Full debug logging |
| `REDFISH_PERF_DEBUG` | `false` | Performance metrics |
| `REDFISH_VMWARE_DEBUG` | `false` | VMware operation details |
| `REDFISH_PORT` | from config | Override server port |
| `REDFISH_LOG_DIR` | `/var/log` | Log file directory |

## Firewall Configuration

Only one port needed (the top-level `redfish_port`):

```bash
# firewalld
sudo firewall-cmd --permanent --add-port=8443/tcp
sudo firewall-cmd --reload

# ufw
sudo ufw allow 8443/tcp
```

## SSL/TLS Setup

- Production: Let's Encrypt certs from `/etc/letsencrypt/live/<hostname>/`
- **Auto-generation**: missing cert paths trigger self-signed RSA 2048 cert (365 days, SANs for localhost/127.0.0.1/hostname)
- SSL wrapping applied in `RedfishHTTPServer.server_bind()` BEFORE `super().server_bind()`
- Development: `"disable_ssl": true` for HTTP-only

BMH address format:
- HTTP: `http://host:8443/redfish/v1/Systems/vm-name`
- HTTPS: `redfish://host:8443/redfish/v1/Systems/vm-name`

**Always use HTTP for Metal3** to avoid certificate issues.

## Adding a New VM

**Manual**: add entry to `vms` array in `config/config.json`, restart service.

**Auto-discovery**: add VM to a configured `datacenter_folders` path in vCenter; it will appear on next refresh (default 5 min) or restart.

```bash
sudo systemctl restart redfish-vmware-server
curl http://localhost:8443/redfish/v1/Systems/new-vm-name
```

## Uninstall

```bash
sudo ./uninstall.sh          # Interactive
sudo ./uninstall.sh --force  # Non-interactive
```
