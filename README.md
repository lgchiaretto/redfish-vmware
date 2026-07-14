# Redfish VMware Server

> **Note:** This application is AI-generated and represents a Redfish-to-VMware bridge solution.

This project provides a **Redfish** server that acts as a bridge between Redfish (REST API) calls and VMware vSphere operations, allowing you to control VMware VMs through the industry-standard Redfish protocol.

🎯 **VMware Redfish Bridge**

- **✅ Compatible with OpenShift Metal3 - Complete asynchronous task system**
- **� Metal3 Enhanced Support - Optimized for Ironic integration**
- **📋 Dynamic Task Management - Dynamic task system with real-time progress**
- **🚨 CRITICAL ENDPOINT MONITORING - Alerts for critical Metal3 endpoints**
- **🏗️ MODULAR ARCHITECTURE - Code organized in specialized modules**

## 🏗️ Modular Architecture

This project has been completely **modularized** for better maintainability and scalability:

### 📁 Directory Structure

```
src/
├── redfish_server.py           # Main server (191 lines)
├── vmware_client.py            # Modularized VMware client (120 lines)
├── handlers/                   # Specialized Redfish handlers
│   ├── redfish_handler.py      # Main Redfish handler
│   ├── systems_handler.py      # System/VM management
│   ├── managers_handler.py     # BMC manager management
│   ├── chassis_handler.py      # Chassis management
│   ├── update_service_handler.py # Update services
│   └── http_handler.py         # Base HTTP handler
├── auth/                       # Authentication system
│   └── manager.py              # Authentication and session manager
├── tasks/                      # Asynchronous task system
│   └── manager.py              # Metal3 task manager
├── utils/                      # System utilities
│   └── logging_config.py       # Logging configuration
└── vmware/                     # Specialized VMware operations
    ├── connection.py           # vSphere connection management
    ├── vm_operations.py        # Basic VM operations
    ├── power_operations.py     # Power operations (on/off)
    └── media_operations.py     # Media operations (ISO/CD-ROM)
```

## 🌟 Main Features

- **Complete Redfish server** - Implements standard Redfish endpoints with HTTPS
- **Dynamic Asynchronous Task System** - Automatic task management with real-time progress
- **Metal3 Enhanced Support** - Optimized integration for OpenShift Ironic
- **UpdateService & TaskService** - Firmware update services and asynchronous task management
- **EventService** - Event service for system notifications and alerts
- **FirmwareInventory & SoftwareInventory** - Complete inventory of firmware and software components
- **Enhanced RAID Support** - Asynchronous RAID operations with volume creation and deletion
- **Metal3 Inspection Ready** - Specific endpoints for hardware inspection by OpenShift
- **Zero Failed Queries** - Smart system that prevents failures in Metal3 periodic queries
- **Real-time Task Progress** - Tasks with real-time progress and auto-completion

## � Enhanced Debugging and Monitoring

### Debug Configuration

Configure debug levels using systemd environment variables:

```bash
# Enable full debug mode
sudo systemctl edit redfish-vmware-server
# Add:
[Service]
Environment=REDFISH_DEBUG=true
Environment=REDFISH_PERF_DEBUG=true
Environment=REDFISH_VMWARE_DEBUG=true

# Restart service
sudo systemctl restart redfish-vmware-server
```

### Debug Levels

| Variable | Description | Use Case |
|----------|-------------|----------|
| `REDFISH_DEBUG=true` | Full debug logging | Complete request/response tracing |
| `REDFISH_PERF_DEBUG=true` | Performance monitoring | Performance bottleneck analysis |
| `REDFISH_VMWARE_DEBUG=true` | VMware operations | VMware API troubleshooting |
| `REDFISH_LOG_DIR=/path` | Custom log location | Centralized logging |

### Monitoring Endpoints

```bash
# Health and statistics
curl http://localhost:8443/redfish/v1/health

# View logs in real-time
sudo journalctl -u redfish-vmware-server -f

# Performance monitoring
tail -f /var/log/redfish-vmware-server.log | grep "📊"
```

### Log Analysis

- **🚀** - Request start
- **✅** - Successful operation  
- **❌** - Failed operation
- **📊** - Performance metrics
- **🔧** - VMware operations
- **⚠️** - Warnings and issues

## �📋 Prerequisites

- **Python 3.11+**
- **VMware vCenter/ESXi** - Access to vSphere API
- **Linux with systemd** - For service control
- **Root access** - For systemd and firewall configuration

## 🚀 Quick Installation

```bash
# Clone the project
git clone <repo-url>
cd redfish-vmware

# Automatic installation
sudo ./setup.sh

# Verify functionality
./tests/test_redfish.sh
```

## ⚙️ Configuration

### 1. Configure VMs in vCenter

Edit `config/config.json`. The server listens on a single port and uses the `{ID}` in the path to select VMs:

```json
{
  "vmware": {
    "host": "your-vcenter.domain.com",
    "user": "administrator@vsphere.local", 
    "password": "your-password",
    "port": 443,
    "disable_ssl": true
  },
  "redfish_port": 8443,
  "disable_ssl": true,
  "vms": [
    {
      "name": "worker-vm-1",
      "vcenter_host": "your-vcenter.domain.com",
      "vcenter_user": "administrator@vsphere.local",
      "vcenter_password": "your-password",
      "redfish_user": "admin",
      "redfish_password": "password"
    },
    {
      "name": "worker-vm-2",
      "vcenter_host": "your-vcenter.domain.com",
      "vcenter_user": "administrator@vsphere.local",
      "vcenter_password": "your-password",
      "redfish_user": "admin",
      "redfish_password": "password"
    }
  ]
}
```

**Key differences from multi-server setup:**
- Single `redfish_port` at the top level (all VMs on same port)
- Top-level `disable_ssl` flag applies to the single server
- VM selection via URL path: `/redfish/v1/Systems/{vm_name}` where `{vm_name}` is from the config

### 1b. Auto-discover VMs from vCenter Folders (Optional)

You can automatically discover and manage all VMs in specific vCenter datacenter folders by adding a `datacenter_folders` section:

```json
{
  "vmware": {
    "host": "your-vcenter.domain.com",
    "user": "administrator@vsphere.local", 
    "password": "your-password",
    "port": 443,
    "disable_ssl": true
  },
  "redfish_port": 8443,
  "disable_ssl": true,
  "vms": [
    {
      "name": "manually-configured-vm",
      "vcenter_host": "your-vcenter.domain.com",
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
    },
    {
      "datacenter": "Datacenter1",
      "folder_path": "vm/staging"
    }
  ]
}
```

**Features:**
- ✅ Automatically discovers all VMs in specified folders (recursive)
- ✅ Skips VMs already manually configured (no duplicates)
- ✅ Uses global vCenter credentials from `vmware` section
- ✅ Marks discovered VMs in logs with `discovered=true` and folder source
- ✅ Mix manual and auto-discovered VMs in the same deployment
- ✅ All discovered VMs get default Redfish credentials (`admin:password`)

**Folder Path Format:**
- `vm` - All VMs in the datacenter root folder
- `vm/prod` - VMs in the `prod` subfolder
- `vm/prod/kubernetes` - VMs in nested folders (recursive search)

### 2. Run Setup

```bash
sudo ./setup.sh
```

The script will:
- ✅ Install Python dependencies
- ✅ Test VMware connectivity
- ✅ Configure systemd service
- ✅ Configure firewall
- ✅ Start the service

## 🔐 Authentication

The Redfish server uses HTTP Basic authentication:

- **Username**: `admin`
- **Password**: `password`

### Public Endpoints (no authentication):
- `/redfish/v1/` - Service Root
- `/redfish/v1/Systems` - Systems Collection

## ✨ Basic Usage

### Public Endpoints (no authentication)
```bash
# Service Root
curl http://localhost:8443/redfish/v1/

# Systems Collection (all VMs)
curl http://localhost:8443/redfish/v1/Systems
```

### Authenticated Endpoints (HTTP Basic: admin:password)
```bash
# System Information (select VM by name in URL)
curl -u admin:password http://localhost:8443/redfish/v1/Systems/worker-vm-1

# Power On System
curl -u admin:password -X POST -H "Content-Type: application/json" \
     -d '{"ResetType": "On"}' \
     http://localhost:8443/redfish/v1/Systems/worker-vm-1/Actions/ComputerSystem.Reset

# Power Off System
curl -u admin:password -X POST -H "Content-Type: application/json" \
     -d '{"ResetType": "ForceOff"}' \
     http://localhost:8443/redfish/v1/Systems/worker-vm-1/Actions/ComputerSystem.Reset

# Boot Configuration (ISO boot for deployment)
curl -u admin:password -X PATCH -H "Content-Type: application/json" \
     -d '{"Boot": {"BootSourceOverrideTarget": "Cd", "BootSourceOverrideEnabled": "Once"}}' \
     http://localhost:8443/redfish/v1/Systems/worker-vm-1
```

### For HTTPS (when certificates are configured)
```bash
# Add -k flag to ignore self-signed certificates during testing
curl -k https://localhost:8443/redfish/v1/
```

### Service Control

```bash
# Service status
sudo systemctl status redfish-vmware-server

# Start/stop/restart
sudo systemctl start redfish-vmware-server
sudo systemctl stop redfish-vmware-server
sudo systemctl restart redfish-vmware-server

# Real-time logs
sudo journalctl -u redfish-vmware-server -f
```

## 🏗️ Architecture

```
    ┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
    │   OpenShift     │     │   Redfish        │     │   VMware        │
    │   Metal3        │───▶│   VMware         │───▶│   vSphere       │
    │ (BareMetalHost) │     │   Server         │     │   API           │
    └─────────────────┘     └──────────────────┘     └─────────────────┘
```

### Components

- **src/redfish_server.py** - Main HTTP server with complete Redfish endpoints
- **src/vmware_client.py** - VMware vSphere client for VM operations
- **config/config.json** - VM configuration and credentials
- **config/*.service** - systemd files for redfish-vmware-server
- **setup.sh** - Automatic installation and configuration script
- **openshift/** - BareMetalHost configurations for OpenShift

## 🔧 Supported Redfish Endpoints

### Power Management
- `POST /redfish/v1/Systems/{id}/Actions/ComputerSystem.Reset`
  - ResetType: On, ForceOff, GracefulShutdown, GracefulRestart, ForceRestart, PushPowerButton, PowerCycle

### Boot Configuration
- `PATCH /redfish/v1/Systems/{id}` - Boot source override
  - BootSourceOverrideTarget: None, Pxe, Floppy, Cd, Usb, Hdd, BiosSetup, Utilities, Diags, UefiShell, UefiTarget
  - BootSourceOverrideEnabled: Disabled, Once, Continuous

### Virtual Media Management
- `GET /redfish/v1/Managers/{id}/VirtualMedia` - Collection of virtual devices
- `POST /redfish/v1/Managers/{id}/VirtualMedia/{device_id}/Actions/VirtualMedia.InsertMedia`
- `POST /redfish/v1/Managers/{id}/VirtualMedia/{device_id}/Actions/VirtualMedia.EjectMedia`

### Hardware Inventory & Inspection
- `GET /redfish/v1/Systems/{id}` - Detailed system information
- `GET /redfish/v1/Systems/{id}/Processors` - Processor collection
- `GET /redfish/v1/Systems/{id}/Memory` - Memory modules collection
- `GET /redfish/v1/Systems/{id}/EthernetInterfaces` - Network interfaces

### RAID & Storage Management
- `GET /redfish/v1/Systems/{id}/Storage` - Storage collection
- `POST /redfish/v1/Systems/{id}/Storage/{storage_id}/Volumes` - Create RAID volume
- `DELETE /redfish/v1/Systems/{id}/Storage/{storage_id}/Volumes/{vol_id}` - Remove volume

### BIOS & Security
- `GET /redfish/v1/Systems/{id}/Bios` - BIOS settings
- `PATCH /redfish/v1/Systems/{id}/Bios` - Update BIOS settings
- `GET /redfish/v1/Systems/{id}/SecureBoot` - SecureBoot settings

### Update & Task Services
- `GET /redfish/v1/UpdateService` - Update service
- `GET /redfish/v1/UpdateService/FirmwareInventory` - Firmware inventory
- `POST /redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate`
- `GET /redfish/v1/TaskService` - Task service
- `GET /redfish/v1/TaskService/Tasks` - Tasks collection (60+ tasks)

## 🌍 Metal3/OpenShift Compatibility

This project implements Redfish endpoints compatible with Metal3/Ironic for complete integration with OpenShift. All BareMetalHost lifecycle operations are supported:

### Supported Features
- ✅ **Power Management**: On/Off/Reset/ForceOff
- ✅ **Boot Source Override**: PXE, ISO, HDD, UEFI Shell
- ✅ **Firmware Management**: BIOS, BMC, NIC updates
- ✅ **Hardware Inventory**: CPU, Memory, Storage, Network
- ✅ **RAID Configuration**: Storage controllers and drives
- ✅ **SecureBoot**: Configuration and control
- ✅ **Async Operations**: Task tracking and status
- ✅ **ISO Boot**: Mounting and boot via virtual media

## � Troubleshooting

### SystemD Debug Control

Debug logging can be controlled through systemd:

```bash
# Enable debug logging
sudo systemctl edit redfish-vmware-server
# Add: Environment=REDFISH_DEBUG=true
sudo systemctl restart redfish-vmware-server

# View logs
sudo journalctl -u redfish-vmware-server -f
```

- 🔍 **All HTTP requests** with source IP and User-Agent
- 🤖 **Automatic detection** of Metal3/Ironic requests
- 🔧 **Inspection endpoints** specific (UpdateService, TaskService, FirmwareInventory)
- 💾 **RAID operations** and storage controller queries
- 📋 **Asynchronous task tracking**
- 🔄 **Firmware update simulation** for compatibility

```

## 🗑️ Uninstallation

To completely remove the server:

```bash
# Complete uninstallation
sudo ./uninstall.sh

# Force without confirmation
sudo ./uninstall.sh --force
```

## Running from a Docker/Podman Container

It is also possible to run this application from within a container. 

Start by building the new image:

```
podman build -f Docker/Containerfile -t <registry server>/<project>/redfish-vmware:latest .
```

```
podman run -p 8443:8443 -v ./config:/app/config:Z <registry server>/<project>/redfish-vmware:latest
```

## 🤝 Contributing

1. Fork the repository
2. Create a branch for your feature
3. Implement and test your changes
4. Submit a Pull Request

## 📄 License

This project is under open source license.

---

**Redfish VMware Server** - Control your VMware VMs through standard REST APIs! 🚀
