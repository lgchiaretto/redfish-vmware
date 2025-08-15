# OpenShift BareMetalHost Configuration for IPMI-VMware Bridge

Para configurar o OpenShift para usar o IPMI-VMware Bridge, você precisa:

## 1. Identificar os IPs

- **IPMI Bridge Server**: `192.168.86.168:623` (esta máquina)
- **VM que será controlada**: `willie-master-0` (no vCenter)
- **IP do OpenShift cluster**: O IP de onde o OpenShift faz as requisições IPMI

## 2. Configurar VM Mapping

No arquivo `/opt/ipmi-vmware/config.ini`, adicione o mapeamento do IP do cluster OpenShift:

```ini
[vm_mapping]
# Mapeie o IP do cluster OpenShift para a VM desejada
<IP_DO_OPENSHIFT_CLUSTER> = willie-master-0
```

## 3. BareMetalHost YAML

Configure o BareMetalHost no OpenShift apontando para o IPMI Bridge:

```yaml
apiVersion: metal3.io/v1alpha1
kind: BareMetalHost
metadata:
  name: willie-master-0
  namespace: openshift-machine-api
spec:
  online: true
  bmc:
    address: ipmi://192.168.86.168:623
    credentialsName: willie-master-0-bmc-secret
  bootMACAddress: "00:50:56:xx:xx:xx"  # MAC da VM
  hardwareProfile: default
---
apiVersion: v1
kind: Secret
metadata:
  name: willie-master-0-bmc-secret
  namespace: openshift-machine-api
type: Opaque
data:
  username: YWRtaW4=        # "admin" em base64
  password: cGFzc3dvcmQ=    # "password" em base64
```

## 4. Teste de Conectividade

Para testar se o OpenShift consegue acessar:

```bash
# Do cluster OpenShift ou de uma máquina que simule o OpenShift:
ipmitool -I lanplus -H 192.168.86.168 -p 623 -U admin -P password chassis power status
```

## 5. Monitoramento

Para ver as requisições do OpenShift chegando:

```bash
# Logs em tempo real
sudo journalctl -u ipmi-vmware-bridge -f

# Status do serviço
ipmi-bridge status

# Ver mapeamentos ativos
sudo grep -A 10 "\[vm_mapping\]" /opt/ipmi-vmware/config.ini
```

## 6. Troubleshooting

Se aparecer erro "No VM mapped for IP X.X.X.X":

1. Identifique o IP do OpenShift nos logs:
   ```bash
   sudo journalctl -u ipmi-vmware-bridge | grep "No VM mapped"
   ```

2. Adicione o IP à configuração:
   ```bash
   sudo nano /opt/ipmi-vmware/config.ini
   # Adicione: IP_DO_OPENSHIFT = nome-da-vm
   ```

3. Reinicie o serviço:
   ```bash
   sudo systemctl restart ipmi-vmware-bridge
   ```

## 7. Status Atual

✅ RMCP Ping funcionando
✅ Chassis commands funcionando  
✅ Server ouvindo em 192.168.86.168:623
✅ VM willie-master-0 mapeada para 192.168.110.50

## Próximos Passos

1. Identifique o IP real do cluster OpenShift que está fazendo as requisições
2. Atualize o mapeamento em `/opt/ipmi-vmware/config.ini`
3. Configure o BareMetalHost com `address: ipmi://192.168.86.168:623`
4. Teste a conectividade do OpenShift
