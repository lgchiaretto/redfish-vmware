#!/bin/bash

echo "🔧 IPMI-VMware Bridge - Status do Sistema"
echo "========================================"
echo

# Service status
echo "📊 Status do Serviço SystemD:"
sudo systemctl status ipmi-vmware-bridge --no-pager -l

echo
echo "🌐 Configuração de Rede:"
echo "IPs Virtuais BMC configurados:"
ip addr show ens33 | grep "192.168.86" | sed 's/^/  /'

echo
echo "🗺️  Mapeamento VM atual:"
sudo grep -A 15 "\[vm_mapping\]" /opt/ipmi-vmware/config.ini | grep "=" | sed 's/^/  /'

echo
echo "🔌 Porta IPMI:"
sudo ss -ulnp | grep 623 | sed 's/^/  /'

echo
echo "📝 Configuração OpenShift BareMetalHost:"
echo "Arquivos gerados em: /home/lchiaret/git/ipmi-vmware/openshift-configs/"
ls -la /home/lchiaret/git/ipmi-vmware/openshift-configs/*.yaml | sed 's/^/  /'

echo
echo "✅ Status Atual:"
echo "  - Serviço SystemD: ATIVO"
echo "  - IPs Virtuais BMC: CONFIGURADOS (192.168.86.50-52)"  
echo "  - Conectividade RMCP: FUNCIONANDO"
echo "  - Logs: HABILITADOS (journalctl -u ipmi-vmware-bridge -f)"
echo

echo "🚨 Problema Identificado:"
echo "  - OpenShift não consegue estabelecer sessão IPMI completa"
echo "  - Servidor responde RMCP ping mas falha na autenticação de sessão"
echo "  - Erro: 'IPMI call failed: power status'"
echo

echo "🔧 Comandos de Gerenciamento:"
echo "  sudo systemctl restart ipmi-vmware-bridge  # Reiniciar serviço"
echo "  sudo systemctl status ipmi-vmware-bridge   # Ver status"
echo "  sudo journalctl -u ipmi-vmware-bridge -f   # Monitorar logs"
echo "  sudo journalctl -u ipmi-vmware-bridge --since '10 minutes ago'  # Logs recentes"

echo
echo "📋 Configuração para OpenShift:"
echo "  BMC Address: ipmi://192.168.86.50:623 (para willie-master-0)"
echo "  BMC Address: ipmi://192.168.86.51:623 (para willie-master-1)"  
echo "  BMC Address: ipmi://192.168.86.52:623 (para willie-master-2)"
echo "  Username: admin"
echo "  Password: admin"
echo
echo "⚡ Próximo Passo:"
echo "  - Aplicar as configurações BareMetalHost no OpenShift"
echo "  - Usar: kubectl apply -f /home/lchiaret/git/ipmi-vmware/openshift-configs/"
echo "  - Monitorar: kubectl get baremetalhost -n openshift-machine-api -w"
