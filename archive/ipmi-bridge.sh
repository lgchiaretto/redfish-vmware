#!/bin/bash
# IPMI-VMware Bridge Control Script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_CMD="$SCRIPT_DIR/.venv/bin/python"
MAIN_SCRIPT="$SCRIPT_DIR/main.py"
PID_FILE="$SCRIPT_DIR/ipmi_bridge.pid"

show_usage() {
    echo "Usage: $0 {start|stop|restart|status|test|logs}"
    echo ""
    echo "Commands:"
    echo "  start     - Start the IPMI-VMware Bridge"
    echo "  stop      - Stop the IPMI-VMware Bridge"
    echo "  restart   - Restart the IPMI-VMware Bridge"
    echo "  status    - Show server status"
    echo "  test      - Test VMware connection"
    echo "  logs      - Show recent logs"
    echo ""
    echo "Examples:"
    echo "  $0 start              # Start the bridge"
    echo "  $0 test               # Test VMware connection"
    echo "  $0 stop               # Stop the bridge"
}

start_bridge() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            echo "IPMI-VMware Bridge is already running (PID: $pid)"
            return 1
        else
            rm -f "$PID_FILE"
        fi
    fi
    
    echo "Starting IPMI-VMware Bridge..."
    nohup "$PYTHON_CMD" "$MAIN_SCRIPT" > ipmi_bridge.out 2>&1 &
    local pid=$!
    echo $pid > "$PID_FILE"
    
    sleep 2
    if kill -0 "$pid" 2>/dev/null; then
        echo "IPMI-VMware Bridge started successfully (PID: $pid)"
        echo "Logs: tail -f $SCRIPT_DIR/ipmi_bridge.out"
        return 0
    else
        echo "Failed to start IPMI-VMware Bridge"
        rm -f "$PID_FILE"
        return 1
    fi
}

stop_bridge() {
    if [ ! -f "$PID_FILE" ]; then
        echo "IPMI-VMware Bridge is not running"
        return 1
    fi
    
    local pid=$(cat "$PID_FILE")
    if ! kill -0 "$pid" 2>/dev/null; then
        echo "IPMI-VMware Bridge is not running (stale PID file)"
        rm -f "$PID_FILE"
        return 1
    fi
    
    echo "Stopping IPMI-VMware Bridge (PID: $pid)..."
    kill "$pid"
    
    # Wait for process to stop
    local count=0
    while kill -0 "$pid" 2>/dev/null && [ $count -lt 10 ]; do
        sleep 1
        count=$((count + 1))
    done
    
    if kill -0 "$pid" 2>/dev/null; then
        echo "Force killing IPMI-VMware Bridge..."
        kill -9 "$pid"
    fi
    
    rm -f "$PID_FILE"
    echo "IPMI-VMware Bridge stopped"
}

status_bridge() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            echo "IPMI-VMware Bridge is running (PID: $pid)"
            echo "Log file: $SCRIPT_DIR/ipmi_vmware.log"
            echo "Output file: $SCRIPT_DIR/ipmi_bridge.out"
            return 0
        else
            echo "IPMI-VMware Bridge is not running (stale PID file)"
            rm -f "$PID_FILE"
            return 1
        fi
    else
        echo "IPMI-VMware Bridge is not running"
        return 1
    fi
}

test_vmware() {
    echo "Testing VMware connection..."
    "$PYTHON_CMD" "$MAIN_SCRIPT" --test-vmware
}

show_logs() {
    if [ -f "$SCRIPT_DIR/ipmi_vmware.log" ]; then
        echo "=== Recent IPMI-VMware Bridge Logs ==="
        tail -20 "$SCRIPT_DIR/ipmi_vmware.log"
    else
        echo "No log file found"
    fi
    
    if [ -f "$SCRIPT_DIR/ipmi_bridge.out" ]; then
        echo ""
        echo "=== Recent Output ==="
        tail -20 "$SCRIPT_DIR/ipmi_bridge.out"
    fi
}

case "$1" in
    start)
        start_bridge
        ;;
    stop)
        stop_bridge
        ;;
    restart)
        stop_bridge
        sleep 1
        start_bridge
        ;;
    status)
        status_bridge
        ;;
    test)
        test_vmware
        ;;
    logs)
        show_logs
        ;;
    *)
        show_usage
        exit 1
        ;;
esac
