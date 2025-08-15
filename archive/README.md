# IPMI VMware Bridge

A Python application that creates a bridge between IPMI commands and VMware vSphere operations. This allows you to manage virtual machines using standard IPMI tools like `ipmitool`, treating VMs as if they were physical servers with BMCs (Baseboard Management Controllers).

## Features

- **IPMI Protocol Support**: Receives and processes standard IPMI commands
- **VMware Integration**: Translates IPMI commands to VMware vSphere API calls
- **Multi-VM Support**: Manages multiple VMs simultaneously with different IPMI endpoints
- **Systemd Integration**: Runs as a proper system service
- **Security**: Configurable authentication and SSL options
- **Logging**: Comprehensive logging for monitoring and debugging

## Supported IPMI Commands

- **Power Control**: Power on, power off, reset, power cycle
- **Chassis Status**: Get power state and system information
- **Boot Device**: Set boot order (disk, network, CD-ROM)
- **Sensor Reading**: Simulated sensor data (temperature, voltage, fan speed)
- **System Information**: Hardware and firmware details

## Prerequisites

- Python 3.7 or higher
- VMware vSphere/ESXi environment
- Network connectivity to vCenter/ESXi host
- Root access for installation (service management)

## Installation

### 1. Quick Installation

Run the configuration script as root:

```bash
sudo ./configure-ipmi.sh
```

This will:
- Install Python dependencies
- Create system user and directories
- Copy files to appropriate locations
- Configure systemd service
- Set up firewall rules

### 2. Manual Installation

If you prefer manual installation:

```bash
# Install Python dependencies
pip3 install -r requirements.txt

# Create directories
sudo mkdir -p /opt/ipmi-vmware-bridge
sudo mkdir -p /etc/ipmi-vmware-bridge

# Copy files
sudo cp *.py /opt/ipmi-vmware-bridge/
sudo cp config.json /etc/ipmi-vmware-bridge/
sudo cp ipmi-vmware-bridge.service /etc/systemd/system/

# Create service user
sudo useradd --system --home /opt/ipmi-vmware-bridge ipmi

# Set permissions
sudo chown -R ipmi:ipmi /opt/ipmi-vmware-bridge
sudo chown -R ipmi:ipmi /etc/ipmi-vmware-bridge

# Enable service
sudo systemctl daemon-reload
sudo systemctl enable ipmi-vmware-bridge
```

## Configuration

### 1. VMware Configuration

Edit `/etc/ipmi-vmware-bridge/config.json`:

```json
{
  "vmware": {
    "host": "chiaretto-vcsa01.chiaret.to",
    "user": "administrator@chiaretto.local",
    "password": "VMware1!VMware1!",
    "port": 443,
    "disable_ssl": true
  }
}
```

### 2. VM Configuration

Configure each VM that should have an IPMI interface:

```json
{
  "vms": [
    {
      "vm_name": "test-vm-01",
      "ipmi_address": "0.0.0.0",
      "ipmi_port": 623,
      "ipmi_user": "admin",
      "ipmi_password": "password"
    }
  ]
}
```

**Configuration Parameters:**
- `vm_name`: Exact name of the VM in vSphere
- `ipmi_address`: IP address to bind to (0.0.0.0 for all interfaces)
- `ipmi_port`: UDP port for IPMI (standard is 623, use different ports for multiple VMs)
- `ipmi_user`: Username for IPMI authentication
- `ipmi_password`: Password for IPMI authentication

## Usage

### Starting the Service

```bash
# Start the service
sudo systemctl start ipmi-vmware-bridge

# Check status
sudo systemctl status ipmi-vmware-bridge

# View logs
sudo journalctl -u ipmi-vmware-bridge -f
```

### Using IPMI Commands

Once the service is running, you can use standard IPMI tools:

```bash
# Get chassis status
ipmitool -I lanplus -H localhost -p 623 -U admin -P password chassis status

# Power on VM
ipmitool -I lanplus -H localhost -p 623 -U admin -P password power on

# Power off VM
ipmitool -I lanplus -H localhost -p 623 -U admin -P password power off

# Reset VM
ipmitool -I lanplus -H localhost -p 623 -U admin -P password power reset

# Get sensor readings
ipmitool -I lanplus -H localhost -p 623 -U admin -P password sensor list

# Set boot device to network
ipmitool -I lanplus -H localhost -p 623 -U admin -P password chassis bootdev pxe

# Set boot device to disk
ipmitool -I lanplus -H localhost -p 623 -U admin -P password chassis bootdev disk
```

### Remote Access

To access from remote machines, replace `localhost` with the server's IP address:

```bash
ipmitool -I lanplus -H 192.168.1.100 -p 623 -U admin -P password chassis status
```

## Testing

Run the test suite to verify installation:

```bash
python3 test_installation.py
```

This will test:
- Configuration file validity
- VMware connectivity
- Python dependencies
- IPMI port availability
- File permissions

## Troubleshooting

### Common Issues

1. **Connection Refused**
   ```
   Error: Unable to establish IPMI v2 / RMCP+ session
   ```
   - Check if service is running: `systemctl status ipmi-vmware-bridge`
   - Verify port is not blocked by firewall
   - Check if port is already in use: `netstat -ulpn | grep 623`

2. **VMware Authentication Failed**
   ```
   Error connecting to VMware: Login failed
   ```
   - Verify VMware credentials in config.json
   - Check network connectivity to vCenter/ESXi
   - Ensure user has sufficient privileges

3. **VM Not Found**
   ```
   VM test-vm-01 not found
   ```
   - Check VM name spelling in config.json
   - Verify VM exists in vSphere inventory
   - Check if VM is in the correct datacenter/folder

4. **Permission Denied**
   ```
   Permission denied on port 623
   ```
   - Ports below 1024 require root privileges
   - Service should run as root or with CAP_NET_BIND_SERVICE capability
   - Check systemd service configuration

### Logging

Logs are available in multiple locations:

```bash
# Service logs
journalctl -u ipmi-vmware-bridge -f

# Application logs
tail -f /var/log/ipmi-vmware-bridge.log

# System logs
tail -f /var/log/syslog | grep ipmi
```

### Debug Mode

For verbose logging, edit the configuration:

```json
{
  "logging": {
    "level": "DEBUG"
  }
}
```

## Security Considerations

- **Network Security**: IPMI traffic is unencrypted by default
- **Authentication**: Use strong passwords for IPMI users
- **Firewall**: Restrict access to IPMI ports (623-630/udp)
- **SSL**: Enable SSL verification for VMware connections in production
- **User Isolation**: Service runs as unprivileged user with minimal permissions

## Advanced Configuration

### Multiple VMs with Port Mapping

```json
{
  "vms": [
    {
      "vm_name": "master-01",
      "ipmi_port": 623,
      "ipmi_user": "admin",
      "ipmi_password": "secret1"
    },
    {
      "vm_name": "master-02", 
      "ipmi_port": 624,
      "ipmi_user": "admin",
      "ipmi_password": "secret2"
    },
    {
      "vm_name": "worker-01",
      "ipmi_port": 625,
      "ipmi_user": "admin",
      "ipmi_password": "secret3"
    }
  ]
}
```

### Custom Sensor Configuration

The bridge simulates hardware sensors. You can customize sensor readings by modifying the `VMwareBMC` class in `ipmi_vmware_bridge.py`.

### Boot Device Mapping

The bridge supports setting boot devices:
- `disk`: Boot from hard disk
- `pxe`/`network`: PXE network boot
- `cdrom`: Boot from CD-ROM/ISO
- `bios`: Enter BIOS setup

## Integration with OpenShift/Kubernetes

This bridge is particularly useful for OpenShift bare metal deployments where you need BMC functionality for virtual machines. Configure your BareMetalHost resources to point to the IPMI endpoints provided by this bridge.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review the logs for error messages
3. Test connectivity with the provided test script
4. Open an issue with detailed information about your environment
