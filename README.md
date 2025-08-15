# IPMI VMware Bridge

Um bridge IPMI que permite ao OpenShift Virtualization controlar VMs VMware como se fossem servidores físicos através do protocolo IPMI.

**⚠️ REQUISITOS:**
- **Deve rodar como root** (portas IPMI padrão 623-626)
- **IPv4 apenas** (sem suporte IPv6)
- **VMware vSphere** configurado e acessível

## 🎯 Funcionalidades

- **Protocolo IPMI completo** - Recebe comandos IPMI over LAN+ nas portas 623-626
- **Integração VMware vSphere** - Traduz comandos IPMI para chamadas da API do vSphere
- **Multi-VM Support** - Suporta múltiplas VMs em portas diferentes
- **OpenShift Ready** - Compatível com BareMetalHost (BMH) resources
- **Debug Mode** - Logging detalhado de todas as chamadas IPMI
- **IPv4 Only** - Configurado para usar apenas IPv4

## 📁 Estrutura do Projeto

```
├── ipmi-bridge              # Script principal para iniciar o serviço
├── src/
│   ├── ipmi_bridge.py      # Implementação principal do bridge IPMI
│   ├── vmware_client.py    # Cliente para integração com VMware vSphere
│   └── set_bios_mode.py    # Utilitários para configuração de BIOS
├── config/
│   ├── config.json         # Configuração principal
│   ├── config_fixed.json   # Configuração alternativa
│   └── ipmi-vmware-bridge.service  # Arquivo de serviço systemd
├── tests/
│   ├── test_*.py          # Testes Python
│   └── test_*.sh          # Scripts de teste
├── docs/                  # Documentação (movida do archive)
├── scripts/               # Scripts utilitários
├── openshift-configs/     # Configurações do OpenShift
└── archive/               # Arquivos antigos/não utilizados
```

## 🚀 Instalação e Uso

### 1. Configuração

Edite o arquivo `config/config.json` com suas credenciais VMware e VMs:

```json
{
  "vmware": {
    "host": "seu-vcenter.local",
    "user": "administrator@seu-dominio.local",
    "password": "sua-senha",
    "port": 443,
    "disable_ssl": true
  },
  "vms": [
    {
      "name": "skinner-master-0",
      "vcenter_host": "seu-vcenter.local",
      "vcenter_user": "administrator@seu-dominio.local",
      "vcenter_password": "sua-senha",
      "port": 623,
      "ipmi_user": "admin",
      "ipmi_password": "password"
    }
  ]
}
```

### 2. Executar o Bridge

```bash
# 🔥 Modo principal (portas IPMI padrão 623-626, APENAS como root)
sudo ./ipmi-bridge

# � Verificar configuração
sudo ./ipmi-bridge --test-config

# � Verificar se portas IPv4 estão livres
sudo ./ipmi-bridge --check-ports

# ⚙️ Usar configuração personalizada
sudo ./ipmi-bridge --config /path/to/config.json
```

### 3. Instalar como Serviço

```bash
# Instalar serviço systemd
sudo ./setup.sh

# Iniciar serviço
sudo systemctl start ipmi-vmware-bridge

# Habilitar na inicialização
sudo systemctl enable ipmi-vmware-bridge

# Ver status
sudo systemctl status ipmi-vmware-bridge
```

## 🔍 Debug e Monitoramento

### Logs Detalhados (Debug habilitado por padrão)

```
🚀 Starting IPMI VMware Bridge Service (IPv4 only)
✅ Running as root - can bind to IPMI standard ports
📡 Ready to receive IPMI calls from OpenShift Virtualization
🎯 IPMI REQUEST from OpenShift/BMH at 192.168.1.100:45678 → VM skinner-master-0
🟢 OpenShift requesting POWER ON for VM: skinner-master-0
⚡ Executing VMware power on for VM: skinner-master-0
✅ VM skinner-master-0 powered on successfully - OpenShift notified
```

### Monitorar Logs

```bash
# Logs em tempo real
sudo tail -f /var/log/ipmi-vmware-bridge.log

# Ou via systemd
sudo journalctl -u ipmi-vmware-bridge -f
```

## 🔍 Debug e Monitoramento

### Logs Detalhados

Com debug habilitado, você verá logs como:

```
🚀 Starting IPMI VMware Bridge Service
📡 This bridge will receive IPMI calls from OpenShift Virtualization BMH
🎯 IPMI REQUEST from OpenShift/BMH at 192.168.1.100:12345 → VM skinner-master-0
🟢 OpenShift requesting POWER ON for VM: skinner-master-0
⚡ Executing VMware power on for VM: skinner-master-0
✅ VM skinner-master-0 powered on successfully - OpenShift notified
```

### Monitorar Logs

```bash
# Logs em tempo real
tail -f /var/log/ipmi-vmware-bridge.log

# Ou via systemd
sudo journalctl -u ipmi-vmware-bridge -f
```

## 🔧 OpenShift Integration

### BareMetalHost Example

```yaml
apiVersion: metal3.io/v1alpha1
kind: BareMetalHost
metadata:
  name: skinner-master-0
spec:
  bmc:
    address: ipmi://192.168.1.10:623
    credentialsName: skinner-master-0-bmc-secret
  bootMACAddress: "00:50:56:xx:xx:xx"
  online: true
```

### BMC Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: skinner-master-0-bmc-secret
type: Opaque
data:
  username: YWRtaW4=  # admin
  password: cGFzc3dvcmQ=  # password
```

## 🧪 Testes

```bash
# Executar todos os testes
cd tests/
python3 test_installation.py

# Teste específico de IPMI
ipmitool -I lanplus -H localhost -p 623 -U admin -P password chassis power status
```

## 📊 Funcionalidades Suportadas

### Comandos IPMI
- ✅ **Power On/Off/Reset** - Controle de energia completo
- ✅ **Get Chassis Status** - Status de energia e boot
- ✅ **Set Boot Device** - Boot por network, disk, cdrom
- ✅ **ISO Mounting** - Montagem de ISOs via CDROM
- ✅ **Serial Over LAN (SOL)** - Console access

### Integração VMware
- ✅ **vSphere API** - Controle total das VMs
- ✅ **Power Management** - On/Off/Reset/Suspend
- ✅ **Boot Control** - Ordem de boot e devices
- ✅ **CDROM Management** - Mount/Unmount ISOs
- ✅ **VM Discovery** - Identificação automática de VMs

## 🐛 Troubleshooting

### Problemas Comuns

1. **VM não encontrada**
   ```
   ❌ VM 'nome-da-vm' not found in vCenter
   ```
   Verifique se o nome da VM está correto no config.json

2. **Erro de conexão VMware**
   ```
   ❌ Failed to connect to vCenter
   ```
   Verifique credenciais e conectividade de rede

3. **OpenShift não consegue conectar**
   ```
   Connection refused on port 623
   ```
   Verifique se o bridge está rodando e as portas estão abertas

### Debug Avançado

Para debug máximo, use:

```bash
export IPMI_DEBUG=true
export PYTHONPATH=/home/lchiaret/git/ipmi-vmware/src
python3 -m pdb src/ipmi_bridge.py
```

## 📚 Documentação Adicional

- `docs/` - Documentação técnica detalhada
- `archive/docs/` - Documentação histórica do projeto
- `scripts/` - Scripts utilitários para setup e manutenção

## ⚡ Performance

- **Latência**: < 1 segundo para operações de energia
- **Throughput**: Suporta múltiplas conexões simultâneas
- **Escalabilidade**: Sem limite artificial de VMs (limitado pelo vCenter)

## 🔐 Segurança

- Credenciais VMware armazenadas em configuração
- Autenticação IPMI por VM
- Logs não expõem senhas
- Suporte a SSL/TLS para vCenter

---

**Desenvolvido para OpenShift Virtualization + VMware vSphere**
