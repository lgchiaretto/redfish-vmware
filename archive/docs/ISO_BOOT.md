# IPMI ISO Boot Functionality

This document describes the ISO boot functionality added to the IPMI-VMware Bridge.

## Overview

The IPMI-VMware Bridge now supports IPMI boot device selection commands, allowing you to:
- Set VM boot device to CD/DVD, Hard Disk, PXE, or No Override
- Mount ISO images to VMs when booting from CD/DVD
- Control boot order through standard IPMI commands
- Use with any IPMI-compatible tool (ipmitool, OpenIPMI, etc.)

## Configuration

Add the following section to your `config.ini`:

```ini
[iso]
# Default ISO to mount when boot from CD/DVD is requested
default_iso_path = iso/ubuntu-22.04.3-live-server-amd64.iso
datastore = datastore1
# Alternative: full datastore path like [datastore1] iso/ubuntu-22.04.3-live-server-amd64.iso
```

### Configuration Options

- `default_iso_path`: Path to the ISO file on the datastore
- `datastore`: Name of the VMware datastore containing the ISO

## Usage Examples

### Using ipmitool

```bash
# Set boot device to CD/DVD (one-time boot)
ipmitool -I lanplus -H 192.168.1.100 -U admin -P password chassis bootdev cdrom

# Set boot device to Hard Disk (one-time boot)  
ipmitool -I lanplus -H 192.168.1.100 -U admin -P password chassis bootdev disk

# Set boot device to PXE (one-time boot)
ipmitool -I lanplus -H 192.168.1.100 -U admin -P password chassis bootdev pxe

# Clear boot override
ipmitool -I lanplus -H 192.168.1.100 -U admin -P password chassis bootdev none

# Get current boot device
ipmitool -I lanplus -H 192.168.1.100 -U admin -P password chassis bootparam get 5

# Power cycle to boot from new device
ipmitool -I lanplus -H 192.168.1.100 -U admin -P password chassis power cycle
```

### Using the Test Script

```bash
# Run full test sequence
python3 tests/test_iso_boot.py

# Test with specific host
python3 tests/test_iso_boot.py --host 192.168.1.100

# Set boot device to CD/DVD
python3 tests/test_iso_boot.py --device cdrom

# Set persistent boot device to Hard Disk
python3 tests/test_iso_boot.py --device hdd --persistent

# Get current boot device
python3 tests/test_iso_boot.py --get

# Power control
python3 tests/test_iso_boot.py --power on
python3 tests/test_iso_boot.py --power off
python3 tests/test_iso_boot.py --power reset
```

## Supported Boot Devices

| IPMI Device | VMware Action | Description |
|-------------|---------------|-------------|
| `none` | Clear override | Default boot order (usually HDD first) |
| `disk`/`hdd` | Boot from HDD | Set hard disk as first boot device |
| `cdrom` | Boot from CD/DVD | Mount ISO and set CD/DVD as first boot device |
| `pxe` | Boot from PXE | Set network boot (not implemented yet) |

## How It Works

### CD/DVD Boot Process

1. IPMI command received to boot from CD/DVD
2. Bridge sets VM boot order to CD/DVD first
3. Bridge mounts the configured ISO file to VM's CD/DVD drive
4. VM will boot from ISO on next startup

### Hard Disk Boot Process

1. IPMI command received to boot from HDD
2. Bridge sets VM boot order to Hard Disk first  
3. Bridge unmounts any mounted ISO
4. VM will boot from hard disk on next startup

### Clear Override Process

1. IPMI command received to clear boot override
2. Bridge resets VM to default boot order
3. Bridge unmounts any mounted ISO
4. VM will use default boot sequence

## VMware API Functions

The following VMware operations are performed:

### ISO Management
- `mount_iso(vm_name, iso_path, datastore)` - Mount ISO to VM's CD/DVD drive
- `unmount_iso(vm_name)` - Unmount ISO from VM's CD/DVD drive

### Boot Order Management
- `set_boot_order(vm_name, boot_from_cdrom=True/False)` - Set VM boot device priority

### VM Information
- `get_vm_info(vm_name)` - Get VM details including mounted ISOs

## IPMI Command Details

### Set System Boot Options (0x08)

**Request:**
- NetFn: 0x00 (Chassis)
- Command: 0x08
- Parameter: 0x05 (Boot device selector)
- Data: Boot device code with flags

**Boot Device Codes:**
- 0x00: No override
- 0x08: Hard Disk
- 0x14: CD/DVD
- 0x04: PXE

**Data Byte Format:**
- Bit 7: Valid bit (1 = valid)
- Bit 6: Persistent bit (1 = persistent across reboots)
- Bits 5-2: Boot device selector
- Bits 1-0: Reserved

### Get System Boot Options (0x09)

**Request:**
- NetFn: 0x00 (Chassis)
- Command: 0x09
- Parameter: 0x05 (Boot device selector)

**Response:**
- Completion Code: 0x00 = success
- Parameter Version: 0x01
- Parameter Selector: 0x05
- Boot device data byte
- Instance ID: 0x00

## Error Handling

The bridge handles various error conditions:

- **VM not found**: Returns IPMI error completion code
- **VMware connection issues**: Logged and returns error
- **ISO file not found**: Logged, continues without mounting
- **Invalid boot device**: Returns "parameter not supported" error
- **VMware API errors**: Logged with detailed error messages

## Logging

Boot operations are logged with INFO level:

```
INFO - Setting VM TESTE1 to boot from CD/DVD
INFO - Mounting ISO iso/ubuntu-22.04.3-live-server-amd64.iso to TESTE1
INFO - Boot order set successfully for VM TESTE1
```

## Troubleshooting

### Common Issues

1. **ISO not mounting**
   - Check ISO path in configuration
   - Verify datastore name is correct
   - Ensure ISO file exists on datastore

2. **Boot order not changing**
   - Check VMware permissions
   - Verify VM is not a template
   - Check vCenter connectivity

3. **IPMI commands failing**
   - Verify VM mapping in configuration
   - Check IPMI server logs
   - Ensure correct NetFn/Command codes

### Debug Mode

Enable debug logging in `config.ini`:

```ini
[logging]
level = DEBUG
```

This will show detailed IPMI packet information and VMware API calls.

## Limitations

- PXE boot setting changes VM configuration but actual PXE boot depends on VM network configuration
- ISO files must be accessible to vCenter on the specified datastore
- Boot device changes require VM restart to take effect
- Only one ISO can be mounted at a time per VM

## Security Considerations

- ISO mounting requires VMware administrative privileges
- Boot device changes can affect VM security posture
- Consider restricting ISO file access to trusted administrators
- Monitor boot device change events for security compliance
