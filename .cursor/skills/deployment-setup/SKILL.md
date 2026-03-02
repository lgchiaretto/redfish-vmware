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

```bash
# Full automated setup (installs deps, configures systemd, firewall)
sudo ./setup.sh

# Config-only (skip systemd and firewall)
sudo ./setup.sh --config-only

# Test VMware connectivity only
sudo ./setup.sh --test-only

# Debug connectivity test
sudo ./setup.sh --debug-test
```

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
  "ssl": {
    "cert_path": "/etc/letsencrypt/live/host.example.com/fullchain.pem",
    "key_path": "/etc/letsencrypt/live/host.example.com/privkey.pem"
  },
  "vms": [
    {
      "name": "vm-master-0",
      "vcenter_host": "vcenter.example.com",
      "vcenter_user": "administrator@vsphere.local",
      "vcenter_password": "your-password",
      "redfish_port": 8440,
      "redfish_user": "admin",
      "redfish_password": "password",
      "disable_ssl": true
    }
  ]
}
```

### Key Config Rules

- Each VM MUST have a unique `redfish_port`
- `name` must match the VM name in vCenter exactly
- `disable_ssl: true` → HTTP mode (recommended for dev and Metal3)
- `ssl` section only needed when `disable_ssl: false`
- `redfish_user`/`redfish_password` default to `admin`/`password`
- **Never commit** `config.json` to git (contains credentials)

## systemd Service Management

```bash
# Start/stop/restart
sudo systemctl start redfish-vmware-server
sudo systemctl stop redfish-vmware-server
sudo systemctl restart redfish-vmware-server

# Status
sudo systemctl status redfish-vmware-server

# Enable on boot
sudo systemctl enable redfish-vmware-server

# View logs
sudo journalctl -u redfish-vmware-server -f

# Edit environment (debug, etc.)
sudo systemctl edit redfish-vmware-server
# Add:
# [Service]
# Environment=REDFISH_DEBUG=true
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REDFISH_DEBUG` | `false` | Full debug logging |
| `REDFISH_PERF_DEBUG` | `false` | Performance metrics |
| `REDFISH_VMWARE_DEBUG` | `false` | VMware operation details |
| `REDFISH_LOG_DIR` | `/var/log` | Log file directory |

## Firewall Configuration

```bash
# firewalld (RHEL/Fedora)
sudo firewall-cmd --permanent --add-port=8440-8444/tcp
sudo firewall-cmd --reload

# ufw (Ubuntu)
sudo ufw allow 8440:8444/tcp

# iptables
sudo iptables -A INPUT -p tcp --dport 8440:8444 -j ACCEPT
```

## SSL/TLS Setup

For HTTPS mode, provide Let's Encrypt or custom certs:

```json
{
  "ssl": {
    "cert_path": "/etc/letsencrypt/live/host.example.com/fullchain.pem",
    "key_path": "/etc/letsencrypt/live/host.example.com/privkey.pem"
  },
  "vms": [
    { "disable_ssl": false, ... }
  ]
}
```

When using SSL with OpenShift BMH, the address format changes:
- HTTP: `http://host:port/redfish/v1/Systems/vm-name`
- HTTPS: `redfish://host:port/redfish/v1/Systems/vm-name`

Recommended: use HTTP (`disable_ssl: true`) to avoid certificate issues with Metal3.

## Uninstall

```bash
sudo ./uninstall.sh          # Interactive
sudo ./uninstall.sh --force  # Non-interactive
```

## Adding a New VM

1. Add entry to `config/config.json` `vms` array with unique port
2. Open firewall port if needed
3. Restart the service: `sudo systemctl restart redfish-vmware-server`
4. Test: `curl http://localhost:NEW_PORT/redfish/v1/`
