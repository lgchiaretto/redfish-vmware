#!/bin/bash

# Script para gerar certificados SSL auto-assinados para o Redfish Server
# Para uso em ambiente de teste/desenvolvimento

set -e

SSL_DIR="/home/lchiaret/git/ipmi-vmware/config/ssl"
cd "$SSL_DIR"

# VMs configuradas
VMS=("skinner-master-0" "skinner-master-1" "skinner-master-2" "skinner-worker-1" "skinner-worker-2")

echo "🔐 Gerando certificados SSL auto-assinados para o Redfish Server..."

for VM in "${VMS[@]}"; do
    echo "📜 Gerando certificado para $VM..."
    
    # Gerar chave privada
    openssl genrsa -out "${VM}.key" 2048
    
    # Gerar certificado auto-assinado
    openssl req -new -x509 -key "${VM}.key" -out "${VM}.crt" -days 365 -subj "/C=BR/ST=SP/L=SaoPaulo/O=RedFish/OU=IT/CN=localhost"
    
    # Definir permissões apropriadas
    chmod 600 "${VM}.key"
    chmod 644 "${VM}.crt"
    
    echo "✅ Certificado gerado para $VM"
done

echo "🎉 Todos os certificados SSL foram gerados com sucesso!"
echo "📁 Localização: $SSL_DIR"
echo "🔒 Os certificados são válidos por 365 dias"
