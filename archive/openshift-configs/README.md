# OpenShift BareMetalHost Configuration

## Virtual BMC Mapping

| Node Name | BMC IP | OpenShift Node IP | VM Name |
|-----------|--------|-------------------|---------|
| willie-master-0 | 192.168.86.50 | 192.168.110.50 | willie-master-0 |
| willie-master-1 | 192.168.86.51 | 192.168.110.51 | willie-master-1 |
| willie-master-2 | 192.168.86.52 | 192.168.110.52 | willie-master-2 |

## Deployment Commands

Apply the BareMetalHost configurations:

```bash
# Apply all configurations
kubectl apply -f /home/lchiaret/git/ipmi-vmware/openshift-configs/

# Or apply individually
kubectl apply -f willie-master-0-bmh.yaml
kubectl apply -f willie-master-1-bmh.yaml
kubectl apply -f willie-master-2-bmh.yaml
```

## Testing BMC Connectivity

```bash
# Test each BMC
ipmitool -I lan -H 192.168.86.50 -p 623 -U admin -P admin chassis power status
ipmitool -I lan -H 192.168.86.51 -p 623 -U admin -P admin chassis power status
ipmitool -I lan -H 192.168.86.52 -p 623 -U admin -P admin chassis power status
```
