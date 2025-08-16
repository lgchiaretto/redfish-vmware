# OpenShift BareMetalHost Testing Guide

Este guia documenta como testar a integração do servidor Redfish com o OpenShift BareMetalHost.

## Pré-requisitos

1. ✅ Servidor Redfish instalado e funcionando
2. ✅ VMs de teste configuradas (todas as 5 VMs: 3 masters + 2 workers)
3. ✅ Conectividade de rede entre OpenShift e o servidor Redfish
4. 🔄 Cluster OpenShift com Metal3 operator instalado

## ⚠️ IMPORTANTE: Configuração HTTP 

**CRÍTICO**: Para evitar erros SSL, todos os BMH files foram atualizados para usar `http://` ao invés de `redfish://`:

```yaml
bmc:
  address: 'http://bastion.chiaret.to:8441/redfish/v1/Systems/skinner-master-1'
  credentialsName: skinner-master-1-bmc-secret
  disableCertificateVerification: true
```

**Erro Corrigido**: 
- ❌ Antes: SSL: WRONG_VERSION_NUMBER - HTTPS em porta HTTP
- ✅ Agora: HTTP puro funcionando perfeitamente

## Estrutura dos Testes

### 1. Testes de Conectividade Básica

```bash
# Testar endpoints Redfish para todas as VMs
curl http://bastion.chiaret.to:8440/redfish/v1/
curl -u admin:password http://bastion.chiaret.to:8440/redfish/v1/Systems/skinner-master-0
curl -u admin:password http://bastion.chiaret.to:8441/redfish/v1/Systems/skinner-master-1  
curl -u admin:password http://bastion.chiaret.to:8442/redfish/v1/Systems/skinner-master-2
curl -u admin:password http://bastion.chiaret.to:8443/redfish/v1/Systems/skinner-worker-1
curl -u admin:password http://bastion.chiaret.to:8444/redfish/v1/Systems/skinner-worker-2
```

### 2. Testes de Power Management

```bash
# Executar script de teste automatizado
./tests/test_power_management.sh
```

### 3. Aplicação dos BareMetalHosts

```bash
# Aplicar TODAS as configurações do BMH (masters + workers)
oc apply -f openshift/skinner-master-0-bmh.yaml
oc apply -f openshift/skinner-master-1-bmh.yaml
oc apply -f openshift/skinner-master-2-bmh.yaml  
oc apply -f openshift/skinner-worker-1-bmh.yaml
oc apply -f openshift/skinner-worker-2-bmh.yaml
```

## Configurações do BareMetalHost

### Credenciais de Autenticação
- **Username**: `admin`
- **Password**: `password`
- **Tipo**: Basic Authentication

### Mapeamento de Portas
- **skinner-master-0**: http://bastion.chiaret.to:8440
- **skinner-master-1**: http://bastion.chiaret.to:8441  
- **skinner-master-2**: http://bastion.chiaret.to:8442
- **skinner-worker-1**: http://bastion.chiaret.to:8443
- **skinner-worker-2**: http://bastion.chiaret.to:8444  
- **Endereço BMC**: `redfish://bastion.chiaret.to:8444/redfish/v1/Systems/skinner-worker-2`
- **Porta**: 8444
- **MAC Address**: `00:50:56:84:8c:23`

## Estados Esperados do BareMetalHost

### Sequência Normal de Provisionamento

1. **registering** - BMH está sendo registrado
2. **inspecting** - Hardware sendo inspecionado  
3. **available** - Host disponível para provisionamento
4. **provisioning** - Host sendo provisionado
5. **provisioned** - Host provisionado com sucesso

### Comandos de Monitoramento

```bash
# Verificar status dos BMHs
oc get baremetalhosts -n openshift-machine-api

# Ver detalhes de um BMH específico
oc describe baremetalhost skinner-worker-1 -n openshift-machine-api

# Monitorar logs do metal3 operator
oc logs -f deployment/metal3-baremetal-operator -n openshift-machine-api

# Verificar eventos relacionados
oc get events -n openshift-machine-api --sort-by='.lastTimestamp'
```

## Resolução de Problemas

### 1. BMH fica em estado "registering"

```bash
# Verificar conectividade de rede
curl -v -u admin:password http://bastion.chiaret.to:8443/redfish/v1/Systems/skinner-worker-1

# Verificar logs do operator
oc logs deployment/metal3-baremetal-operator -n openshift-machine-api
```

### 2. BMH falha na inspeção

```bash
# Verificar se as VMs estão ligadas
curl -u admin:password http://bastion.chiaret.to:8443/redfish/v1/Systems/skinner-worker-1 | jq '.PowerState'

# Verificar configuração do MAC address
oc get bmh skinner-worker-1 -o yaml | grep bootMACAddress
```

### 3. Problemas de autenticação

```bash
# Verificar se o secret foi criado corretamente
oc get secret skinner-worker-1-bmc-secret -n openshift-machine-api -o yaml
```

## Validação de Sucesso

O teste será considerado bem-sucedido quando:

1. ✅ Os BareMetalHosts saem do estado "registering" 
2. ✅ Conseguem completar a inspeção (estado "inspecting" → "available")
3. ✅ Podem ser provisionados (estado "provisioning" → "provisioned")
4. ✅ O OpenShift consegue controlar o power management das VMs via Redfish

## Comandos Úteis

### Limpar e recriar BMHs
```bash
# Deletar BMHs existentes
oc delete bmh skinner-worker-1 skinner-worker-2 -n openshift-machine-api

# Recriar
oc apply -f openshift/skinner-worker-1-bmh.yaml
oc apply -f openshift/skinner-worker-2-bmh.yaml
```

### Forçar re-inspeção
```bash
# Adicionar annotation para forçar re-inspeção
oc annotate bmh skinner-worker-1 -n openshift-machine-api reboot.metal3.io/capz-remediation-
```

### Debug do servidor Redfish
```bash
# Ativar modo debug
export REDFISH_DEBUG=true
sudo systemctl restart redfish-vmware-server

# Ver logs detalhados
sudo journalctl -u redfish-vmware-server -f
```

## Próximos Passos

Após completar estes testes com sucesso:

1. Documentar todos os resultados
2. Criar templates para outros clusters OpenShift
3. Implementar monitoramento automatizado
4. Desenvolver scripts de manutenção
