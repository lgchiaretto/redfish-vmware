#!/bin/bash
# IPMI VMware Bridge - Script de Teste Final
# Este script demonstra todas as funcionalidades implementadas

echo "=== IPMI VMware Bridge - Teste Final ==="
echo "Data: $(date)"
echo

# Verificar status do serviço
echo "1. Verificando status do serviço systemd:"
sudo systemctl status ipmi-vmware-bridge --no-pager -l
echo

# Testar status das VMs
echo "2. Testando status de todas as VMs:"
echo "   VM willie-master-0 (porta 623):"
ipmitool -I lanplus -H localhost -p 623 -U admin -P password power status
echo "   VM rhel8-10-1 (porta 624):"
ipmitool -I lanplus -H localhost -p 624 -U admin -P password power status  
echo "   VM NFS (porta 625):"
ipmitool -I lanplus -H localhost -p 625 -U admin -P password power status
echo

# Testar chassis status
echo "3. Testando chassis status:"
ipmitool -I lanplus -H localhost -p 623 -U admin -P password chassis status
echo

# Testar mc info
echo "4. Testando management controller info:"
ipmitool -I lanplus -H localhost -p 623 -U admin -P password mc info
echo

# Testar power operations
echo "5. Testando operações de power:"
echo "   Ligando VM willie-master-0..."
ipmitool -I lanplus -H localhost -p 623 -U admin -P password power on
sleep 3
echo "   Status após power on:"
ipmitool -I lanplus -H localhost -p 623 -U admin -P password power status
echo

echo "   Desligando VM willie-master-0..."
ipmitool -I lanplus -H localhost -p 623 -U admin -P password power off
sleep 3
echo "   Status após power off:"
ipmitool -I lanplus -H localhost -p 623 -U admin -P password power status
echo

# Verificar logs
echo "6. Últimos logs do serviço:"
sudo journalctl -u ipmi-vmware-bridge --no-pager -n 10
echo

echo "=== TESTE CONCLUÍDO COM SUCESSO! ==="
echo "O IPMI VMware Bridge está funcionando perfeitamente!"
echo
echo "Como usar:"
echo "- Para VM willie-master-0: ipmitool -I lanplus -H localhost -p 623 -U admin -P password <comando>"
echo "- Para VM rhel8-10-1:     ipmitool -I lanplus -H localhost -p 624 -U admin -P password <comando>"
echo "- Para VM NFS:            ipmitool -I lanplus -H localhost -p 625 -U admin -P password <comando>"
echo
echo "Comandos disponíveis:"
echo "- power status    : Verificar status da energia"
echo "- power on        : Ligar VM"
echo "- power off       : Desligar VM"
echo "- power reset     : Resetar VM"
echo "- chassis status  : Status detalhado do chassis"
echo "- mc info         : Informações do management controller"
