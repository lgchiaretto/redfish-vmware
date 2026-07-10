# Redfish VMware Server

> **Nota:** Esta aplicação foi gerada por IA e representa uma solução de ponte Redfish-to-VMware.

Este projeto fornece um servidor **Redfish** que atua como ponte entre chamadas Redfish (API REST) e operações VMware vSphere, permitindo controlar VMs VMware através do protocolo Redfish padrão da indústria.

🎯 **VMware Redfish Bridge**

- **✅ Compatível com OpenShift Metal3 — sistema completo de tarefas assíncronas**
- **🤖 Suporte aprimorado ao Metal3 — otimizado para integração com Ironic**
- **📋 Gerenciamento dinâmico de tarefas — progresso em tempo real**
- **🚨 MONITORAMENTO DE ENDPOINTS CRÍTICOS — alertas para endpoints críticos do Metal3**
- **🏗️ ARQUITETURA MODULAR — código organizado em módulos especializados**

## 🏗️ Arquitetura Modular

Este projeto foi completamente **modularizado** para melhor manutenibilidade e escalabilidade:

### 📁 Estrutura de Diretórios

```
src/
├── redfish_server.py           # Servidor principal
├── vmware_client.py            # Cliente VMware modularizado
├── handlers/                   # Handlers Redfish especializados
│   ├── redfish_handler.py      # Handler Redfish principal
│   ├── systems_handler.py      # Gerenciamento de sistemas/VMs
│   ├── managers_handler.py     # Gerenciamento de BMC/managers
│   ├── chassis_handler.py      # Gerenciamento de chassis
│   ├── update_service_handler.py # Serviços de atualização
│   └── http_handler.py         # Handler HTTP base
├── auth/                       # Sistema de autenticação
│   └── manager.py              # Gerenciador de autenticação e sessões
├── tasks/                      # Sistema de tarefas assíncronas
│   └── manager.py              # Gerenciador de tarefas Metal3
├── utils/                      # Utilitários do sistema
│   └── logging_config.py       # Configuração de logging
└── vmware/                     # Operações VMware especializadas
    ├── connection.py           # Gerenciamento de conexão vSphere
    ├── vm_operations.py        # Operações básicas de VM
    ├── power_operations.py     # Operações de energia (ligar/desligar)
    └── media_operations.py     # Operações de mídia (ISO/CD-ROM)
```

## 🌟 Principais Funcionalidades

- **Servidor Redfish completo** — implementa endpoints Redfish padrão com HTTPS
- **Sistema dinâmico de tarefas assíncronas** — gerenciamento automático com progresso em tempo real
- **Suporte aprimorado ao Metal3** — integração otimizada para OpenShift Ironic
- **UpdateService & TaskService** — serviços de atualização de firmware e gerenciamento assíncrono de tarefas
- **EventService** — serviço de eventos para notificações e alertas do sistema
- **FirmwareInventory & SoftwareInventory** — inventário completo de firmware e software
- **Suporte RAID aprimorado** — operações RAID assíncronas com criação e remoção de volumes
- **Pronto para inspeção Metal3** — endpoints específicos para inspeção de hardware pelo OpenShift
- **Zero consultas falhadas** — sistema inteligente que previne falhas em consultas periódicas do Metal3
- **Progresso de tarefas em tempo real** — tarefas com progresso e auto-conclusão

## 🔍 Debug e Monitoramento Aprimorados

### Configuração de Debug

Configure níveis de debug usando variáveis de ambiente do systemd:

```bash
# Ativar modo debug completo
sudo systemctl edit redfish-vmware-server
# Adicionar:
[Service]
Environment=REDFISH_DEBUG=true
Environment=REDFISH_PERF_DEBUG=true
Environment=REDFISH_VMWARE_DEBUG=true

# Reiniciar serviço
sudo systemctl restart redfish-vmware-server
```

### Níveis de Debug

| Variável | Descrição | Caso de uso |
|----------|-----------|-------------|
| `REDFISH_DEBUG=true` | Logging debug completo | Rastreamento completo de requisições/respostas |
| `REDFISH_PERF_DEBUG=true` | Monitoramento de performance | Análise de gargalos de performance |
| `REDFISH_VMWARE_DEBUG=true` | Operações VMware | Troubleshooting da API VMware |
| `REDFISH_LOG_DIR=/path` | Localização customizada de logs | Logging centralizado |

### Endpoints de Monitoramento

```bash
# Saúde e estatísticas
curl http://localhost:8443/redfish/v1/health

# Ver logs em tempo real
sudo journalctl -u redfish-vmware-server -f

# Monitoramento de performance
tail -f /var/log/redfish-vmware-server.log | grep "📊"
```

### Análise de Logs

- **🚀** — Início de requisição
- **✅** — Operação bem-sucedida
- **❌** — Operação falhou
- **📊** — Métricas de performance
- **🔧** — Operações VMware
- **⚠️** — Avisos e problemas

## 📋 Pré-requisitos

- **Python 3.11+**
- **VMware vCenter/ESXi** — acesso à API vSphere
- **Linux com systemd** — para controle do serviço
- **Acesso root** — para configuração de systemd e firewall

## 🚀 Instalação Rápida

```bash
# Clonar o projeto
git clone <repo-url>
cd redfish-vmware

# Instalação automática
sudo ./setup.sh

# Verificar funcionamento
./tests/test_redfish.sh
```

## ⚙️ Configuração

### 1. Configurar VMs no vCenter

Edite `config/config.json`. O servidor escuta em uma única porta e usa o `{ID}` no caminho para selecionar VMs:

```json
{
  "vmware": {
    "host": "seu-vcenter.dominio.com",
    "user": "administrator@vsphere.local",
    "password": "sua-senha",
    "port": 443,
    "disable_ssl": true
  },
  "redfish_port": 8443,
  "disable_ssl": true,
  "vms": [
    {
      "name": "worker-vm-1",
      "vcenter_host": "seu-vcenter.dominio.com",
      "vcenter_user": "administrator@vsphere.local",
      "vcenter_password": "sua-senha",
      "redfish_user": "admin",
      "redfish_password": "password"
    },
    {
      "name": "worker-vm-2",
      "vcenter_host": "seu-vcenter.dominio.com",
      "vcenter_user": "administrator@vsphere.local",
      "vcenter_password": "sua-senha",
      "redfish_user": "admin",
      "redfish_password": "password"
    }
  ]
}
```

**Diferenças em relação ao modelo multi-servidor:**
- Porta `redfish_port` única no nível superior (todas as VMs na mesma porta)
- Flag `disable_ssl` no nível superior aplica-se ao servidor único
- Seleção de VM via caminho da URL: `/redfish/v1/Systems/{vm_name}` onde `{vm_name}` vem da config

### 1b. Auto-descoberta de VMs em pastas do vCenter (Opcional)

Você pode descobrir e gerenciar automaticamente todas as VMs em pastas específicas do datacenter do vCenter adicionando uma seção `datacenter_folders`:

```json
{
  "vmware": {
    "host": "seu-vcenter.dominio.com",
    "user": "administrator@vsphere.local",
    "password": "sua-senha",
    "port": 443,
    "disable_ssl": true
  },
  "redfish_port": 8443,
  "disable_ssl": true,
  "vms": [
    {
      "name": "vm-configurada-manualmente",
      "vcenter_host": "seu-vcenter.dominio.com",
      "vcenter_user": "administrator@vsphere.local",
      "vcenter_password": "sua-senha",
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

**Recursos:**
- ✅ Descobre automaticamente todas as VMs em pastas especificadas (recursivo)
- ✅ Ignora VMs já configuradas manualmente (sem duplicatas)
- ✅ Usa credenciais globais do vCenter da seção `vmware`
- ✅ Marca VMs descobertas nos logs com `discovered=true` e origem da pasta
- ✅ Mistura VMs manuais e autodescobertas na mesma implantação
- ✅ Todas as VMs descobertas recebem credenciais Redfish padrão (`admin:password`)

**Formato do caminho da pasta:**
- `vm` — todas as VMs na pasta raiz do datacenter
- `vm/prod` — VMs na subpasta `prod`
- `vm/prod/kubernetes` — VMs em pastas aninhadas (busca recursiva)

### 2. Executar o setup

```bash
sudo ./setup.sh
```

O script irá:
- ✅ Instalar dependências Python
- ✅ Testar conectividade VMware
- ✅ Configurar serviço systemd
- ✅ Configurar firewall
- ✅ Iniciar o serviço

## 🔐 Autenticação

O servidor Redfish usa autenticação HTTP Basic:

- **Usuário**: `admin`
- **Senha**: `password`

### Endpoints públicos (sem autenticação):
- `/redfish/v1/` — Service Root
- `/redfish/v1/Systems` — Coleção de Systems

## ✨ Uso Básico

### Endpoints públicos (sem autenticação)

```bash
# Service Root
curl http://localhost:8443/redfish/v1/

# Coleção de Systems (todas as VMs)
curl http://localhost:8443/redfish/v1/Systems
```

### Endpoints autenticados (HTTP Basic: admin:password)

```bash
# Informações do sistema (seleciona VM pelo nome na URL)
curl -u admin:password http://localhost:8443/redfish/v1/Systems/worker-vm-1

# Ligar sistema
curl -u admin:password -X POST -H "Content-Type: application/json" \
     -d '{"ResetType": "On"}' \
     http://localhost:8443/redfish/v1/Systems/worker-vm-1/Actions/ComputerSystem.Reset

# Desligar sistema
curl -u admin:password -X POST -H "Content-Type: application/json" \
     -d '{"ResetType": "ForceOff"}' \
     http://localhost:8443/redfish/v1/Systems/worker-vm-1/Actions/ComputerSystem.Reset

# Configuração de boot (boot ISO para deployment)
curl -u admin:password -X PATCH -H "Content-Type: application/json" \
     -d '{"Boot": {"BootSourceOverrideTarget": "Cd", "BootSourceOverrideEnabled": "Once"}}' \
     http://localhost:8443/redfish/v1/Systems/worker-vm-1
```

### Para HTTPS (quando certificados estiverem configurados)

```bash
# Adicionar flag -k para ignorar certificados auto-assinados durante testes
curl -k https://localhost:8443/redfish/v1/
```

### Controle do serviço

```bash
# Status do serviço
sudo systemctl status redfish-vmware-server

# Iniciar/parar/reiniciar
sudo systemctl start redfish-vmware-server
sudo systemctl stop redfish-vmware-server
sudo systemctl restart redfish-vmware-server

# Logs em tempo real
sudo journalctl -u redfish-vmware-server -f
```

## 🏗️ Arquitetura

```
    ┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
    │   OpenShift     │     │   Redfish        │     │   VMware        │
    │   Metal3        │───▶│   VMware         │───▶│   vSphere       │
    │ (BareMetalHost) │     │   Server         │     │   API           │
    └─────────────────┘     └──────────────────┘     └─────────────────┘
```

### Componentes

- **src/redfish_server.py** — servidor HTTP principal com endpoints Redfish completos
- **src/vmware_client.py** — cliente VMware vSphere para operações em VMs
- **config/config.json** — configuração de VMs e credenciais
- **config/*.service** — arquivos systemd para redfish-vmware-server
- **setup.sh** — script de instalação e configuração automática
- **openshift/** — configurações BareMetalHost para OpenShift

## 🔧 Endpoints Redfish Suportados

### Gerenciamento de energia

- `POST /redfish/v1/Systems/{id}/Actions/ComputerSystem.Reset`
  - ResetType: On, ForceOff, GracefulShutdown, GracefulRestart, ForceRestart, PushPowerButton, PowerCycle

### Configuração de boot

- `PATCH /redfish/v1/Systems/{id}` — override de fonte de boot
  - BootSourceOverrideTarget: None, Pxe, Floppy, Cd, Usb, Hdd, BiosSetup, Utilities, Diags, UefiShell, UefiTarget
  - BootSourceOverrideEnabled: Disabled, Once, Continuous

### Gerenciamento de mídia virtual

- `GET /redfish/v1/Managers/{id}/VirtualMedia` — coleção de dispositivos virtuais
- `POST /redfish/v1/Managers/{id}/VirtualMedia/{device_id}/Actions/VirtualMedia.InsertMedia`
- `POST /redfish/v1/Managers/{id}/VirtualMedia/{device_id}/Actions/VirtualMedia.EjectMedia`

### Inventário e inspeção de hardware

- `GET /redfish/v1/Systems/{id}` — informações detalhadas do sistema
- `GET /redfish/v1/Systems/{id}/Processors` — coleção de processadores
- `GET /redfish/v1/Systems/{id}/Memory` — coleção de módulos de memória
- `GET /redfish/v1/Systems/{id}/EthernetInterfaces` — interfaces de rede

### RAID e armazenamento

- `GET /redfish/v1/Systems/{id}/Storage` — coleção de storage
- `POST /redfish/v1/Systems/{id}/Storage/{storage_id}/Volumes` — criar volume RAID
- `DELETE /redfish/v1/Systems/{id}/Storage/{storage_id}/Volumes/{vol_id}` — remover volume

### BIOS e segurança

- `GET /redfish/v1/Systems/{id}/Bios` — configurações BIOS
- `PATCH /redfish/v1/Systems/{id}/Bios` — atualizar configurações BIOS
- `GET /redfish/v1/Systems/{id}/SecureBoot` — configurações SecureBoot

### Update e Task Services

- `GET /redfish/v1/UpdateService` — serviço de atualização
- `GET /redfish/v1/UpdateService/FirmwareInventory` — inventário de firmware
- `POST /redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate`
- `GET /redfish/v1/TaskService` — serviço de tarefas
- `GET /redfish/v1/TaskService/Tasks` — coleção de tarefas (60+ tarefas)

## 🌍 Compatibilidade Metal3/OpenShift

Este projeto implementa endpoints Redfish compatíveis com Metal3/Ironic para integração completa com OpenShift. Todas as operações de ciclo de vida de BareMetalHost são suportadas:

### Funcionalidades suportadas

- ✅ **Gerenciamento de energia**: On/Off/Reset/ForceOff
- ✅ **Boot Source Override**: PXE, ISO, HDD, UEFI Shell
- ✅ **Gerenciamento de firmware**: atualizações BIOS, BMC, NIC
- ✅ **Inventário de hardware**: CPU, memória, storage, rede
- ✅ **Configuração RAID**: controladores e drives de storage
- ✅ **SecureBoot**: configuração e controle
- ✅ **Operações assíncronas**: rastreamento e status de tarefas
- ✅ **Boot ISO**: montagem e boot via mídia virtual

## 🐛 Troubleshooting

### Controle de debug via SystemD

O logging de debug pode ser controlado pelo systemd:

```bash
# Ativar logging de debug
sudo systemctl edit redfish-vmware-server
# Adicionar: Environment=REDFISH_DEBUG=true
sudo systemctl restart redfish-vmware-server

# Ver logs
sudo journalctl -u redfish-vmware-server -f
```

- 🔍 **Todas as requisições HTTP** com IP de origem e User-Agent
- 🤖 **Detecção automática** de requisições Metal3/Ironic
- 🔧 **Endpoints de inspeção** específicos (UpdateService, TaskService, FirmwareInventory)
- 💾 **Operações RAID** e consultas de controladores de storage
- 📋 **Rastreamento de tarefas** assíncronas
- 🔄 **Simulação de atualização de firmware** para compatibilidade

## 🗑️ Desinstalação

Para remover completamente o servidor:

```bash
# Desinstalação completa
sudo ./uninstall.sh

# Forçar sem confirmação
sudo ./uninstall.sh --force
```

## Executando em container Docker/Podman

Também é possível executar esta aplicação dentro de um container.

Comece construindo a imagem:

```
podman build -f Docker/Containerfile -t registry.xphyrlab.net/markd/redfish-vmware:latest .
```

```
podman run -p 8443:8443 -v ./config:/app/config:Z registry.xphyrlab.net/markd/redfish-vmware:latest
```

## 🤝 Contribuindo

1. Faça fork do repositório
2. Crie um branch para sua funcionalidade
3. Implemente e teste suas alterações
4. Envie um Pull Request

## 📄 Licença

Este projeto está sob licença open source.

---

**Redfish VMware Server** — controle suas VMs VMware através de APIs REST padrão! 🚀
