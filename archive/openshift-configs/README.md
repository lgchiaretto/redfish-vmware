# OpenShift BareMetalHost Configuration

## Virtual BMC Mapping

| Node Name | BMC IP | OpenShift Node IP | VM Name |
|-----------|--------|-------------------|---------|
| skinner-master-0 | 192.168.86.50 | 192.168.110.50 | skinner-master-0 |
| skinner-master-1 | 192.168.86.51 | 192.168.110.51 | skinner-master-1 |
| skinner-master-2 | 192.168.86.52 | 192.168.110.52 | skinner-master-2 |

## Deployment Commands

Apply the BareMetalHost configurations:

```bash
# Apply all configurations
kubectl apply -f /home/lchiaret/git/ipmi-vmware/openshift-configs/

# Or apply individually
kubectl apply -f skinner-master-0-bmh.yaml
kubectl apply -f skinner-master-1-bmh.yaml
kubectl apply -f skinner-master-2-bmh.yaml
```

## Testing BMC Connectivity

```bash
# Test each BMC
ipmitool -I lanplus -H 192.168.86.50 -p 623 -U admin -P admin chassis power status
ipmitool -I lanplus -H 192.168.86.51 -p 623 -U admin -P admin chassis power status
ipmitool -I lanplus -H 192.168.86.52 -p 623 -U admin -P admin chassis power status
```
