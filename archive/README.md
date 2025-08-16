# Redfish VMware Server

Este projeto fornece um servidor **Redfish** que atua como bridge entre chamadas Redfish (REST API) e operações VMware vSphere, permitindo controlar VMs VMware através do protocolo Redfish padrão da indústria.

## 🎯 Funcionalidades

- **Servidor Redfish completo** - Implementa endpoints Redfish padrão
- **Controle de Power Management** - Liga, desliga, reinicia VMs 
- **Múltiplas VMs simultâneas** - Cada VM em uma porta diferente
- **Integração com systemd** - Controle de serviço nativo do Linux
- **Compatível com OpenShift** - Funciona como BMC para bare metal provisioning
- **Logging detalhado** - Suporte a debug mode para troubleshooting
- **Auto-descoberta** - Lista sistemas disponíveis dinamicamente

## 🏗️ Arquitetura

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Redfish       │    │   Redfish        │    │   VMware        │
│   Client        │───▶│   VMware         │───▶│   vSphere       │
│ (OpenShift/curl)│    │   Server         │    │   API           │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Componentes

- **redfish_server.py** - Servidor HTTP principal com endpoints Redfish
- **vmware_client.py** - Cliente VMware vSphere para operações nas VMs
- **config.json** - Configuração das VMs e credenciais
- **systemd service** - Integração nativa com systemd
- **setup.sh** - Script de instalação e configuração

## 📋 Pré-requisitos

- **Python 3.8+**
- **VMware vCenter/ESXi** - Acesso à API do vSphere
- **Linux com systemd** - Para controle de serviço
- **Acesso root** - Para configuração de systemd e firewall

## 🚀 Instalação

### 1. Clonagem e Configuração

```bash
cd /home/lchiaret/git/ipmi-vmware/redfish
chmod +x setup.sh
```

### 2. Configuração das VMs

Edite o arquivo `config/config.json`:

```json
{
  "vmware": {
    "host": "seu-vcenter.dominio.com",
    "user": "administrator@vsphere.local", 
    "password": "sua-senha",
    "port": 443,
    "disable_ssl": true
  },
  "vms": [
    {
      "name": "vm-master-0",
      "vcenter_host": "seu-vcenter.dominio.com",
      "vcenter_user": "administrator@vsphere.local",
      "vcenter_password": "sua-senha",
      "redfish_port": 8443,
      "redfish_user": "admin",
      "redfish_password": "password",
      "disable_ssl": true
    }
  ]
}
```

### 3. Instalação Automática

```bash
sudo ./setup.sh
```

O script irá:
- ✅ Instalar dependências Python
- ✅ Testar conectividade VMware
- ✅ Configurar serviço systemd
- ✅ Configurar firewall
- ✅ Iniciar o serviço

## 🔧 Uso

### Controle do Serviço

```bash
# Status do serviço
sudo systemctl status redfish-vmware-server

# Iniciar serviço
sudo systemctl start redfish-vmware-server

# Parar serviço
sudo systemctl stop redfish-vmware-server

# Reiniciar serviço
sudo systemctl restart redfish-vmware-server

# Logs em tempo real
sudo journalctl -u redfish-vmware-server -f
```

### Operações Redfish

#### Descoberta de Sistemas

```bash
# Service Root
curl http://localhost:8443/redfish/v1/

# Lista de sistemas disponíveis
curl http://localhost:8443/redfish/v1/Systems

# Informações de sistema específico
curl http://localhost:8443/redfish/v1/Systems/vm-master-0
```

#### Controle de Power

```bash
# Ligar VM
curl -X POST -H "Content-Type: application/json" \
     -d '{"ResetType": "On"}' \
     http://localhost:8443/redfish/v1/Systems/vm-master-0/Actions/ComputerSystem.Reset

# Desligar VM (força)
curl -X POST -H "Content-Type: application/json" \
     -d '{"ResetType": "ForceOff"}' \
     http://localhost:8443/redfish/v1/Systems/vm-master-0/Actions/ComputerSystem.Reset

# Desligamento gracioso
curl -X POST -H "Content-Type: application/json" \
     -d '{"ResetType": "GracefulShutdown"}' \
     http://localhost:8443/redfish/v1/Systems/vm-master-0/Actions/ComputerSystem.Reset

# Reiniciar VM
curl -X POST -H "Content-Type: application/json" \
     -d '{"ResetType": "ForceRestart"}' \
     http://localhost:8443/redfish/v1/Systems/vm-master-0/Actions/ComputerSystem.Reset

# Ciclo de power
curl -X POST -H "Content-Type: application/json" \
     -d '{"ResetType": "PowerCycle"}' \
     http://localhost:8443/redfish/v1/Systems/vm-master-0/Actions/ComputerSystem.Reset
```

#### Tipos de Reset Suportados

| Tipo | Descrição | Ação VMware |
|------|-----------|-------------|
| `On` | Liga o sistema | `PowerOnVM_Task()` |
| `ForceOff` | Desliga força | `PowerOffVM_Task()` |
| `GracefulShutdown` | Desligamento gracioso | `ShutdownGuest()` |
| `GracefulRestart` | Reinício gracioso | `RebootGuest()` |
| `ForceRestart` | Reinício forçado | `ResetVM_Task()` |
| `PowerCycle` | Ciclo de power | Power Off + Power On |

## 🧪 Testes

### Teste de Conectividade

```bash
# Teste básico de conectividade VMware
python3 tests/test_connectivity.py
```

### Teste Completo dos Endpoints

```bash
# Executar todos os testes
./tests/test_redfish.sh

# Apenas teste de power cycle
./tests/test_redfish.sh power

# Verificar status do serviço
./tests/test_redfish.sh status

# Monitorar logs
./tests/test_redfish.sh logs
```

## 🐛 Debug

### Ativar Modo Debug

```bash
# Ativar debug permanente
export REDFISH_DEBUG=true
sudo systemctl restart redfish-vmware-server

# Ou editar o service file
sudo systemctl edit redfish-vmware-server
```

Adicionar:
```ini
[Service]
Environment=REDFISH_DEBUG=true
```

### Logs Detalhados

```bash
# Logs do serviço
sudo journalctl -u redfish-vmware-server -f

# Logs com maior detalhamento
sudo journalctl -u redfish-vmware-server --since "1 hour ago" -o verbose
```

## 🔒 Segurança

### Firewall

O script de setup configura automaticamente as regras de firewall para as portas configuradas:

```bash
# Firewalld (RHEL/CentOS/Fedora)
sudo firewall-cmd --permanent --add-port=8443/tcp
sudo firewall-cmd --reload

# UFW (Ubuntu/Debian)
sudo ufw allow 8443/tcp

# Iptables (manual)
sudo iptables -I INPUT -p tcp --dport 8443 -j ACCEPT
```

### Autenticação

Atualmente implementa autenticação básica simples. Para produção, considere:
- Implementar autenticação real com validação de credenciais
- Adicionar suporte a HTTPS/TLS
- Implementar rate limiting
- Adicionar logs de auditoria

## 📊 Monitoramento

### Status do Serviço

```bash
# Verificar se está executando
systemctl is-active redfish-vmware-server

# Informações detalhadas
systemctl status redfish-vmware-server

# Uso de recursos
top -p $(pgrep -f redfish_server.py)
```

### Métricas de Rede

```bash
# Portas em uso
netstat -tlnp | grep python3

# Conexões ativas
ss -tulpn | grep :844
```

## ⚡ Performance

### Configurações Recomendadas

Para ambientes de produção:

1. **Múltiplas Workers**: Considere usar gunicorn ao invés do servidor HTTP built-in
2. **Load Balancer**: Para múltiplas instâncias
3. **Cache**: Implementar cache para respostas de status
4. **Connection Pooling**: Para conexões VMware

### Limites

- **Conexões simultâneas**: Limitado pelo GIL do Python
- **VMs por instância**: Recomendado máximo 50 VMs
- **Timeout**: 60 segundos para operações VMware

## 🔄 Comparação com IPMI

| Aspecto | IPMI | Redfish |
|---------|------|---------|
| Protocolo | Binário sobre UDP | REST API sobre HTTP |
| Autenticação | Session-based | HTTP Auth |
| Descoberta | Broadcast | Service Discovery |
| Dados | Proprietary | JSON padronizado |
| Ferramentas | ipmitool | curl, REST clients |
| Firewall | Porta 623 | Portas HTTP custom |

### Migração do IPMI

Se você já usa o servidor IPMI deste projeto:

1. **Paralelo**: Execute ambos simultaneamente
2. **Gradual**: Migre VMs aos poucos
3. **Teste**: Valide funcionalidade antes de desativar IPMI
4. **OpenShift**: Atualize BMH configs para usar Redfish

## 🚨 Troubleshooting

### Problemas Comuns

#### Serviço não inicia

```bash
# Verificar logs
sudo journalctl -u redfish-vmware-server --since "5 minutes ago"

# Verificar configuração
python3 -m json.tool config/config.json

# Testar conectividade VMware
python3 tests/test_connectivity.py
```

#### Conexão VMware falha

```bash
# Verificar credenciais
# Verificar conectividade de rede
ping seu-vcenter.dominio.com

# Testar SSL
openssl s_client -connect seu-vcenter.dominio.com:443
```

#### Porta ocupada

```bash
# Verificar portas em uso
netstat -tlnp | grep :8443

# Matar processo usando a porta
sudo fuser -k 8443/tcp
```

#### VM não encontrada

```bash
# Listar VMs disponíveis no vCenter
python3 -c "
import sys; sys.path.insert(0, 'src')
from vmware_client import VMwareClient
import json
config = json.load(open('config/config.json'))
vm = config['vms'][0]
client = VMwareClient(vm['vcenter_host'], vm['vcenter_user'], vm['vcenter_password'])
for vm in client.list_vms():
    print(vm.name)
"
```

## 📝 Logs

### Localização dos Logs

- **Journal**: `sudo journalctl -u redfish-vmware-server`
- **Arquivo**: `/var/log/redfish-vmware-server.log` (se root)
- **Home**: `~/redfish-vmware-server.log` (se usuário)
- **Local**: `./redfish-vmware-server.log`

### Níveis de Log

- **INFO**: Operações normais
- **DEBUG**: Detalhes de protocolo (com REDFISH_DEBUG=true)
- **WARNING**: Problemas não críticos
- **ERROR**: Erros que impedem operação

## 🔮 Roadmap

### Próximas Funcionalidades

- [ ] **Boot Device Control** - Suporte a configuração de boot order
- [ ] **Virtual Media** - Mount/unmount de ISOs via Redfish
- [ ] **Sensor Data** - Exposição de métricas de hardware virtual
- [ ] **Event Subscriptions** - Notificações de mudanças de estado
- [ ] **HTTPS/TLS** - Comunicação segura
- [ ] **Authentication** - Sistema de autenticação robusto
- [ ] **Multi-tenant** - Suporte a múltiplos vCenters
- [ ] **Chassis Management** - Endpoints de chassis e cooling

### Melhorias de Performance

- [ ] **Async/Await** - Conversão para programação assíncrona
- [ ] **Connection Pooling** - Reutilização de conexões VMware
- [ ] **Caching** - Cache de status e informações
- [ ] **Metrics** - Integração com Prometheus

## 🤝 Contribuição

Para contribuir com o projeto:

1. Fork o repositório
2. Crie uma branch para sua feature
3. Implemente e teste suas mudanças
4. Submeta um Pull Request

### Estrutura do Código

```
redfish/
├── src/
│   ├── redfish_server.py    # Servidor HTTP principal
│   └── vmware_client.py     # Cliente VMware
├── config/
│   ├── config.json          # Configuração das VMs
│   └── *.service           # Arquivos systemd
├── tests/
│   ├── test_redfish.sh     # Testes funcionais
│   └── test_connectivity.py # Testes de conectividade
├── setup.sh                # Script de instalação
├── requirements.txt        # Dependências Python
└── README.md              # Esta documentação
```

## 📄 Licença

Este projeto está sob a mesma licença do projeto IPMI original.

## 🆘 Suporte

Para suporte e dúvidas:

1. **Logs**: Sempre inclua logs relevantes
2. **Configuração**: Sanitize e inclua config.json
3. **Ambiente**: Descreva SO, Python version, VMware version
4. **Reprodução**: Passos para reproduzir o problema

---

**Redfish VMware Server** - Controle suas VMs VMware através de APIs REST padrão! 🚀
