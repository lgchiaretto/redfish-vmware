# Guia Rápido: Configuração PXE para OpenShift na Rede 110

## Situação Atual
- ✅ IPMI Bridge funcionando (4 nodes)
- ✅ OpenShift cluster na rede **192.168.110.0/24**
- ✅ skinner-worker-1 preso em "inspecting" (precisa PXE boot)

## Solução: PXE Server na Rede 110

### Passo 1: Configurar Rede Persistente
```bash
# Configure a interface ens35 com IP fixo na rede 110
sudo ./scripts/setup-persistent-network.sh
```

**O que faz:**
- Adiciona IP **192.168.110.10** na interface **ens35**
- Torna a configuração permanente (sobrevive a reboots)
- Testa conectividade com o cluster OpenShift

### Passo 2: Instalar Infraestrutura PXE
```bash
# Instala e configura DHCP/TFTP/HTTP na rede 110
sudo ./scripts/setup-pxe-infrastructure.sh
```

**O que faz:**
- Instala dnsmasq (DHCP/TFTP server)
- Configura Apache HTTP server
- Baixa Ironic Python Agent (IPA) images
- Configura firewall
- Serve DHCP no range **192.168.110.100-200**

### Passo 3: Configurar VM para PXE Boot
```bash
# Configura skinner-worker-1 para fazer PXE boot
./scripts/configure-vm-pxe.sh skinner-worker-1
```

**O que faz:**
- Adiciona interface de rede na VM
- Configura boot order para Network primeiro
- Gera notas de configuração manual

### Passo 4: Monitorar Inspeção
```bash
# Monitora o progresso da inspeção
oc get baremetalhosts skinner-worker-1 -n openshift-machine-api -w

# Verifica logs do Metal3
oc logs -n openshift-machine-api deployment/metal3-baremetal-operator -f

# Verifica DHCP leases
sudo cat /var/lib/dhcp/dhcpd.leases
```

## Arquitetura da Solução

```
┌─────────────────────┐    ┌──────────────────────┐    ┌─────────────────┐
│   OpenShift Cluster │    │   Bastion (ens35)    │    │   VMware VMs    │
│   192.168.110.x     │◄──►│   192.168.110.10     │◄──►│   DHCP Clients  │
│   Metal3/Ironic     │    │   PXE/DHCP/TFTP      │    │                 │
└─────────────────────┘    └──────────────────────┘    └─────────────────┘
         │                           │                           │
         │                  ┌─────────────────┐                │
         └──────────────────►│  IPMI Bridge    │◄───────────────┘
                            │  4 BMC Instances│
                            └─────────────────┘
```

## Fluxo de Adição de Node

1. **BareMetalHost criado** → Metal3 inicia inspeção
2. **IPMI power on** → Bridge liga VM via VMware
3. **VM faz PXE boot** → Busca DHCP na rede 110
4. **DHCP responde** → IP 192.168.110.100-200
5. **TFTP download** → IPA kernel/initramfs
6. **IPA executa** → Coleta informações de hardware
7. **Inspeção completa** → Node fica "available"

## Verificações de Conectividade

```bash
# Teste conectividade rede 110
ping 192.168.110.1

# Teste servidor PXE
curl http://192.168.110.10/

# Teste TFTP
tftp 192.168.110.10 -c get pxelinux.0

# Verifica DHCP funcionando
sudo journalctl -f -u dnsmasq
```

## Troubleshooting

### VM não pega IP
- Verificar se VM tem interface na rede 110
- Verificar se boot order está Network primeiro
- Verificar logs do dnsmasq

### IPA não baixa
- Verificar conectividade HTTP: `curl http://192.168.110.10/images/`
- Verificar firewall: `sudo firewall-cmd --list-all`
- Verificar permissões TFTP: `ls -la /var/lib/tftpboot/`

### Inspeção falha
- Verificar Metal3 logs
- Verificar se IPA consegue conectar no Ironic
- Aumentar timeout de inspeção se necessário

## Após Sucesso

Uma vez que skinner-worker-1 complete a inspeção:
- Status mudará para "available"
- Poderá ser provisionado normalmente
- Mesmo processo serve para novos nodes
- Infraestrutura PXE ficará disponível permanentemente
