# IPMI-VMware Bridge - SystemD Installation Guide

## Overview

This guide explains how to install and configure the IPMI-VMware Bridge as a systemd service for production use.

## Quick Installation

### 1. Download and Install
```bash
# Clone or download the project
git clone <repository>
cd ipmi-vmware

# Run the installation script as root
sudo ./configure-ipmi.sh install
```

### 2. Configure the Service
```bash
# Edit configuration
ipmi-bridge config

# Test VMware connection
ipmi-bridge test

# Enable service to start at boot
ipmi-bridge enable

# Start the service
ipmi-bridge start
```

### 3. Verify Installation
```bash
# Check service status
ipmi-bridge status

# View live logs
ipmi-bridge logs

# Run installation tests
sudo ./test-installation.sh
```

## Installation Details

### What the Installation Script Does

1. **System Dependencies**: Installs Python 3, pip, venv
2. **Service User**: Creates `ipmi-bridge` system user
3. **Installation Directory**: Copies files to `/opt/ipmi-vmware`
4. **Python Environment**: Creates virtual environment with dependencies
5. **SystemD Service**: Creates and configures service file
6. **Management Script**: Installs `ipmi-bridge` command
7. **Firewall**: Opens port 623/udp
8. **Permissions**: Sets proper security permissions

### Installation Locations

| Component | Location |
|-----------|----------|
| Application Files | `/opt/ipmi-vmware/` |
| Configuration | `/opt/ipmi-vmware/config.ini` |
| Logs | `/opt/ipmi-vmware/ipmi_vmware.log` |
| SystemD Service | `/etc/systemd/system/ipmi-vmware-bridge.service` |
| Management Command | `/usr/local/bin/ipmi-bridge` |
| Python Virtual Env | `/opt/ipmi-vmware/.venv/` |

### Service User

The service runs as the `ipmi-bridge` system user with restricted permissions:
- Home directory: `/opt/ipmi-vmware`
- Shell: `/bin/false` (no login)
- Permissions: Read/write only to application directory

## Service Management

### Using the Management Command

```bash
# Service control
ipmi-bridge start           # Start service
ipmi-bridge stop            # Stop service
ipmi-bridge restart         # Restart service
ipmi-bridge status          # Show status
ipmi-bridge enable          # Enable at boot
ipmi-bridge disable         # Disable at boot

# Monitoring
ipmi-bridge logs            # Show live logs
ipmi-bridge test            # Test VMware connection

# Configuration
ipmi-bridge config          # Edit config file
```

### Using SystemD Directly

```bash
# Service control
sudo systemctl start ipmi-vmware-bridge
sudo systemctl stop ipmi-vmware-bridge
sudo systemctl restart ipmi-vmware-bridge
sudo systemctl status ipmi-vmware-bridge

# Boot behavior
sudo systemctl enable ipmi-vmware-bridge
sudo systemctl disable ipmi-vmware-bridge

# Logs
sudo journalctl -u ipmi-vmware-bridge -f
sudo journalctl -u ipmi-vmware-bridge --since "1 hour ago"
```

## Configuration

### VMware Settings

Edit `/opt/ipmi-vmware/config.ini`:

```ini
[vmware]
vcenter_host = your-vcenter.domain.com
username = administrator@vsphere.local
password = your-password
port = 443
ignore_ssl = true
```

### IPMI Settings

```ini
[ipmi]
listen_address = 0.0.0.0
listen_port = 623          # Standard IPMI port
```

**Note**: Port 623 requires root privileges. The service is configured to run as root when using the standard IPMI port.

### VM Mapping

```ini
[vm_mapping]
# Map client IP addresses to VM names
192.168.1.100 = production-server-1
192.168.1.101 = test-server-2
10.0.0.50 = development-vm
```

### Logging

```ini
[logging]
level = INFO
file = /opt/ipmi-vmware/ipmi_vmware.log
```

## Security Considerations

### Service Security

The systemd service includes security hardening:
- `NoNewPrivileges=true`
- `PrivateTmp=true`
- `ProtectSystem=strict`
- `ProtectHome=true`
- `ProtectKernelTunables=true`
- `ProtectKernelModules=true`

### Network Security

- **Firewall**: Port 623/udp is opened automatically
- **Access Control**: Consider IP-based restrictions in VM mapping
- **Credentials**: Configuration file permissions are restricted (600)

### VMware Security

- **SSL Verification**: Set `ignore_ssl = false` for production
- **Least Privilege**: Use dedicated vSphere user with minimal permissions
- **Password Security**: Consider using environment variables for passwords

## Monitoring and Troubleshooting

### Log Files

```bash
# Application logs
tail -f /opt/ipmi-vmware/ipmi_vmware.log

# SystemD logs
journalctl -u ipmi-vmware-bridge -f

# View recent errors
journalctl -u ipmi-vmware-bridge --since "1 hour ago" -p err
```

### Common Issues

#### Service Won't Start

```bash
# Check configuration
ipmi-bridge test

# Check service status
systemctl status ipmi-vmware-bridge

# Check logs
journalctl -u ipmi-vmware-bridge --since "10 minutes ago"
```

#### Port Permission Issues

If using port 623 with permission errors:

```bash
# Check if port is available
sudo netstat -ulnp | grep 623

# Verify service runs as root (for port 623)
systemctl show ipmi-vmware-bridge | grep User
```

#### VMware Connection Issues

```bash
# Test connection manually
ipmi-bridge test

# Check network connectivity
ping your-vcenter.domain.com

# Check credentials
# Edit config: ipmi-bridge config
```

### Performance Monitoring

```bash
# Service resource usage
systemctl status ipmi-vmware-bridge

# Process information
ps aux | grep ipmi

# Network connections
sudo netstat -ulnp | grep 623
```

## Backup and Recovery

### Configuration Backup

```bash
# Backup configuration
sudo cp /opt/ipmi-vmware/config.ini /opt/ipmi-vmware/config.ini.backup

# Backup entire installation
sudo tar -czf ipmi-bridge-backup.tar.gz /opt/ipmi-vmware
```

### Disaster Recovery

```bash
# Restore from backup
sudo tar -xzf ipmi-bridge-backup.tar.gz -C /

# Reload systemd
sudo systemctl daemon-reload

# Restart service
ipmi-bridge restart
```

## Uninstallation

```bash
# Stop and disable service
ipmi-bridge stop
ipmi-bridge disable

# Run uninstall script
sudo ./configure-ipmi.sh uninstall

# This removes:
# - Service files
# - Installation directory
# - Service user
# - Management command
```

## Advanced Configuration

### Custom Service Configuration

If you need to modify the systemd service:

```bash
# Edit service file
sudo systemctl edit ipmi-vmware-bridge

# Reload after changes
sudo systemctl daemon-reload
sudo systemctl restart ipmi-vmware-bridge
```

### Multiple Instances

To run multiple instances (different ports/configs):

```bash
# Copy service file
sudo cp /etc/systemd/system/ipmi-vmware-bridge.service \
        /etc/systemd/system/ipmi-vmware-bridge-2.service

# Edit new service file to use different config
sudo nano /etc/systemd/system/ipmi-vmware-bridge-2.service

# Enable and start
sudo systemctl enable ipmi-vmware-bridge-2
sudo systemctl start ipmi-vmware-bridge-2
```

## Testing the Installation

### Automated Tests

```bash
# Run comprehensive installation tests
sudo ./test-installation.sh

# Check current status
./test-installation.sh status
```

### Manual Testing

```bash
# Test VMware connection
ipmi-bridge test

# Test IPMI commands (from another machine)
ipmitool -I lanplus -H <bridge_ip> -U admin -P admin chassis power status

# Test with included client
python3 /opt/ipmi-vmware/ipmi_client.py <target_ip> --port 623 --command status
```

## Support and Maintenance

### Regular Maintenance

```bash
# Check service health
ipmi-bridge status

# Review logs for errors
journalctl -u ipmi-vmware-bridge --since "24 hours ago" -p err

# Update Python dependencies (if needed)
sudo /opt/ipmi-vmware/.venv/bin/pip install --upgrade -r /opt/ipmi-vmware/requirements.txt
```

### Log Rotation

SystemD automatically handles log rotation for journal logs. For application logs:

```bash
# Set up logrotate for application logs
sudo nano /etc/logrotate.d/ipmi-vmware-bridge
```

Add:
```
/opt/ipmi-vmware/ipmi_vmware.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
```

The IPMI-VMware Bridge is now ready for production use with full systemd integration!
