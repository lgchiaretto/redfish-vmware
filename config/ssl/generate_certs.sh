#!/bin/bash

# Script to generate self-signed SSL certificates for the Redfish Server
# For use in test/development environment

set -e

SSL_DIR="/home/lchiaret/git/ipmi-vmware/config/ssl"
cd "$SSL_DIR"

# Configured VMs
VMS=("skinner-master-0" "skinner-master-1" "skinner-master-2" "skinner-worker-1" "skinner-worker-2")

echo "🔐 Generating self-signed SSL certificates for Redfish Server..."

for VM in "${VMS[@]}"; do
    echo "📜 Generating certificate for $VM..."
    
    # Generate private key
    openssl genrsa -out "${VM}.key" 2048
    
    # Generate self-signed certificate
    openssl req -new -x509 -key "${VM}.key" -out "${VM}.crt" -days 365 -subj "/C=US/ST=CA/L=SanFrancisco/O=RedFish/OU=IT/CN=localhost"
    
    # Set appropriate permissions
    chmod 600 "${VM}.key"
    chmod 644 "${VM}.crt"
    
    echo "✅ Certificate generated for $VM"
done

echo "🎉 All SSL certificates generated successfully!"
echo "📁 Location: $SSL_DIR"
echo "🔒 Certificates are valid for 365 days"
