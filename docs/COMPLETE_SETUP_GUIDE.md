# IPMI-VMware Bridge - Complete Setup Instructions

## 🚀 Quick Start Guide

### Option 1: Development/Testing Setup
```bash
# 1. Clone the repository
git clone <repository>
cd ipmi-vmware

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure VMware settings
cp config.ini config.ini.backup
nano config.ini

# 4. Test VMware connection
python main.py --test-vmware

# 5. Start the bridge (development mode)
python main.py
```

### Option 2: Production SystemD Setup
```bash
# 1. Clone the repository
git clone <repository>
cd ipmi-vmware

# 2. Run installation script as root
sudo ./configure-ipmi.sh install

# 3. Configure the service
ipmi-bridge config

# 4. Test VMware connection
ipmi-bridge test

# 5. Enable and start service
ipmi-bridge enable
ipmi-bridge start

# 6. Check status
ipmi-bridge status
```

## 📋 Prerequisites

### System Requirements
- **OS**: Ubuntu 18.04+ / RHEL 8+ / CentOS 8+
- **Python**: 3.6 or later
- **Memory**: 512MB minimum
- **Network**: Access to VMware vCenter and IPMI clients

### VMware Requirements
- **vCenter Server**: 6.5 or later
- **Permissions**: User with VM power management rights
- **Network**: HTTPS (443) access to vCenter

### Network Requirements
- **IPMI Port**: 623/udp (standard) or custom port
- **Firewall**: Port open for IPMI clients
- **DNS**: Hostname resolution for vCenter

## ⚙️ Configuration

### VMware Configuration
Edit `config.ini`:
```ini
[vmware]
vcenter_host = your-vcenter.domain.com
username = administrator@vsphere.local
password = your-secure-password
port = 443
ignore_ssl = true  # Set to false for production
```

### IPMI Server Configuration
```ini
[ipmi]
listen_address = 0.0.0.0  # Listen on all interfaces
listen_port = 623         # Standard IPMI port (requires root)
```

### VM Mapping Configuration
```ini
[vm_mapping]
# Map client IP addresses to VMware VM names
192.168.1.100 = production-web-server
192.168.1.101 = production-db-server
192.168.1.102 = test-environment
10.0.0.50 = development-vm
```

### Logging Configuration
```ini
[logging]
level = INFO              # DEBUG, INFO, WARNING, ERROR
file = ipmi_vmware.log   # Log file path
```

## 🧪 Testing

### Test VMware Connection
```bash
# Development mode
python main.py --test-vmware

# Production mode
ipmi-bridge test
```

### Test IPMI Commands

#### Using Built-in Test Client
```bash
# Test status
python ipmi_client.py 192.168.1.100 --port 623 --command status

# Test power operations
python ipmi_client.py 192.168.1.100 --port 623 --command on
python ipmi_client.py 192.168.1.100 --port 623 --command off
python ipmi_client.py 192.168.1.100 --port 623 --command reset
```

#### Using Standard IPMI Tools
```bash
# Install ipmitool
sudo yum install ipmitool      # RHEL/CentOS

# Test chassis commands
ipmitool -I lanplus -H <bridge_ip> -U admin -P admin chassis power status
ipmitool -I lanplus -H <bridge_ip> -U admin -P admin chassis power on
ipmitool -I lanplus -H <bridge_ip> -U admin -P admin chassis power off
ipmitool -I lanplus -H <bridge_ip> -U admin -P admin chassis power reset
```

## 🔧 Service Management

### Development Mode Commands
```bash
# Start bridge
python main.py

# Start with custom config
python main.py --config custom-config.ini

# Test only
python main.py --test-vmware

# Validate config
python main.py --validate-config
```

### Production Mode Commands
```bash
# Service control
ipmi-bridge start          # Start service
ipmi-bridge stop           # Stop service
ipmi-bridge restart        # Restart service
ipmi-bridge status         # Show status

# Boot configuration
ipmi-bridge enable         # Start at boot
ipmi-bridge disable        # Don't start at boot

# Monitoring
ipmi-bridge logs           # Show live logs
ipmi-bridge test           # Test VMware connection

# Configuration
ipmi-bridge config         # Edit config file
```

### Direct SystemD Commands
```bash
sudo systemctl start ipmi-vmware-bridge
sudo systemctl stop ipmi-vmware-bridge
sudo systemctl restart ipmi-vmware-bridge
sudo systemctl status ipmi-vmware-bridge
sudo systemctl enable ipmi-vmware-bridge
sudo systemctl disable ipmi-vmware-bridge

# Logs
sudo journalctl -u ipmi-vmware-bridge -f
sudo journalctl -u ipmi-vmware-bridge --since "1 hour ago"
```

## 🛡️ Security Best Practices

### Network Security
1. **Firewall Rules**: Only allow necessary IPMI clients
2. **IP Mapping**: Use specific IP addresses, not subnets
3. **Network Segmentation**: Isolate IPMI traffic

### VMware Security
1. **Dedicated User**: Create dedicated vSphere user
2. **Minimal Permissions**: Grant only VM power management rights
3. **SSL Verification**: Enable SSL verification in production
4. **Password Policy**: Use strong passwords

### System Security
1. **Service User**: Runs as dedicated system user (production)
2. **File Permissions**: Restricted config file permissions
3. **Log Monitoring**: Monitor for authentication failures

## 📊 Monitoring and Alerting

### Log Monitoring
```bash
# Monitor application logs
tail -f /opt/ipmi-vmware/ipmi_vmware.log

# Monitor systemd logs
journalctl -u ipmi-vmware-bridge -f

# Check for errors
journalctl -u ipmi-vmware-bridge --since "1 hour ago" -p err
```

### Health Checks
```bash
# Service health
ipmi-bridge status

# Connection test
ipmi-bridge test

# Process check
ps aux | grep ipmi

# Port check
sudo netstat -ulnp | grep 623
```

### Performance Monitoring
```bash
# Resource usage
systemctl status ipmi-vmware-bridge

# Memory usage
ps -o pid,rss,vsz,comm -p $(pgrep -f main.py)

# Network connections
sudo ss -ulnp | grep 623
```

## 🔧 Troubleshooting

### Common Issues

#### Service Won't Start
```bash
# Check service status
systemctl status ipmi-vmware-bridge

# Check configuration
ipmi-bridge test

# Check logs
journalctl -u ipmi-vmware-bridge --since "10 minutes ago"

# Validate configuration
python3 /opt/ipmi-vmware/main.py --validate-config
```

#### Permission Denied on Port 623
```bash
# Option 1: Run as root (production)
sudo ./configure-ipmi.sh install

# Option 2: Use non-privileged port (development)
# Edit config.ini: listen_port = 6230
```

#### VMware Connection Failed
```bash
# Test network connectivity
ping your-vcenter.domain.com
telnet your-vcenter.domain.com 443

# Check credentials
ipmi-bridge config

# Test connection
ipmi-bridge test
```

#### VM Not Found
```bash
# List all VMs
python3 list_vms.py

# Check VM mapping
ipmi-bridge config

# Verify VM names are exact
```

#### IPMI Commands Timeout
```bash
# Check service is running
ipmi-bridge status

# Check firewall
sudo ufw status  # Ubuntu
sudo firewall-cmd --list-all  # CentOS/RHEL

# Test connectivity
telnet <bridge_ip> 623
```

### Debug Mode
```bash
# Enable debug logging
# Edit config.ini: level = DEBUG

# Restart service
ipmi-bridge restart

# View detailed logs
ipmi-bridge logs
```

## 🔄 Backup and Recovery

### Configuration Backup
```bash
# Backup configuration
sudo cp /opt/ipmi-vmware/config.ini /opt/ipmi-vmware/config.ini.backup.$(date +%Y%m%d)

# Backup entire installation
sudo tar -czf ipmi-bridge-backup-$(date +%Y%m%d).tar.gz /opt/ipmi-vmware
```

### Recovery
```bash
# Restore configuration
sudo cp /opt/ipmi-vmware/config.ini.backup.20250812 /opt/ipmi-vmware/config.ini

# Restart service
ipmi-bridge restart

# Verify
ipmi-bridge test
```

## 📈 Scaling and Performance

### Single Instance Limits
- **Concurrent Connections**: ~100 simultaneous IPMI clients
- **VM Operations**: Limited by vCenter API performance
- **Memory Usage**: ~50-100MB typical

### Multiple Instances
```bash
# Different ports for different VM groups
cp /opt/ipmi-vmware/config.ini /opt/ipmi-vmware/config-group2.ini

# Edit port and VM mapping
nano /opt/ipmi-vmware/config-group2.ini

# Run second instance
/opt/ipmi-vmware/.venv/bin/python /opt/ipmi-vmware/main.py --config /opt/ipmi-vmware/config-group2.ini
```

### Load Balancing
- Use multiple bridge instances behind a load balancer
- Different instances can handle different IP ranges
- Each instance connects to the same vCenter

## 🚀 Production Deployment Checklist

### Pre-Deployment
- [ ] VMware connectivity tested
- [ ] All target VMs identified and mapped
- [ ] Firewall rules configured
- [ ] SSL certificates validated (if using SSL verification)
- [ ] Service user created and tested
- [ ] Backup procedures in place

### Deployment
- [ ] Install using `configure-ipmi.sh install`
- [ ] Configure production settings
- [ ] Test VMware connection
- [ ] Test IPMI commands from client machines
- [ ] Enable service for boot startup
- [ ] Configure monitoring/alerting

### Post-Deployment
- [ ] Monitor logs for errors
- [ ] Verify IPMI clients can connect
- [ ] Test VM power operations
- [ ] Document IP-to-VM mappings
- [ ] Train operations team

## 📚 Additional Resources

### Files and Locations
- **Application**: `/opt/ipmi-vmware/` (production) or current directory (development)
- **Configuration**: `config.ini`
- **Logs**: `ipmi_vmware.log` and systemd journal
- **Service**: `/etc/systemd/system/ipmi-vmware-bridge.service`
- **Management**: `/usr/local/bin/ipmi-bridge`

### Commands Reference
```bash
# Installation
sudo ./configure-ipmi.sh install
sudo ./configure-ipmi.sh uninstall

# Testing
./test-installation.sh test
./test-installation.sh status

# Service management
ipmi-bridge {start|stop|restart|status|enable|disable|logs|test|config}

# Manual testing
python ipmi_client.py <ip> --port <port> --command {status|on|off|reset}
```

The IPMI-VMware Bridge is now ready for production deployment with full systemd integration!
