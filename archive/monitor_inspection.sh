#!/bin/bash

echo "🔍 Monitoring willie-worker-1 inspection progress..."
echo "==========================================="

while true; do
    echo "⏰ $(date)"
    
    # Get BareMetalHost status
    BMH_STATUS=$(oc get baremetalhosts willie-worker-1 -n openshift-machine-api -o jsonpath='{.status.provisioning.state}')
    BMH_POWERED=$(oc get baremetalhosts willie-worker-1 -n openshift-machine-api -o jsonpath='{.status.poweredOn}')
    BMH_ERROR=$(oc get baremetalhosts willie-worker-1 -n openshift-machine-api -o jsonpath='{.status.errorMessage}')
    
    echo "📊 State: $BMH_STATUS | Powered: $BMH_POWERED"
    
    if [ ! -z "$BMH_ERROR" ]; then
        echo "❌ Error: $BMH_ERROR"
    fi
    
    # Check if inspection is complete
    if [ "$BMH_STATUS" = "available" ]; then
        echo "🎉 SUCCESS! BareMetalHost is now available for provisioning!"
        break
    elif [ "$BMH_STATUS" = "error" ]; then
        echo "❌ FAILED! BareMetalHost is in error state"
        break
    fi
    
    echo "⏳ Waiting 30 seconds..."
    sleep 30
done
