#!/bin/bash
"""
VMware IPMI BMC Service Control Script
Facilita o gerenciamento do serviço systemd
"""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SERVICE_NAME="vmware-ipmi-bmc.service"

show_status() {
    echo -e "${BLUE}🔍 VMware IPMI BMC Service Status${NC}"
    echo "=================================="
    sudo systemctl status $SERVICE_NAME
}

start_service() {
    echo -e "${BLUE}🚀 Starting VMware IPMI BMC Service...${NC}"
    sudo systemctl start $SERVICE_NAME
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Service started successfully${NC}"
        show_status
    else
        echo -e "${RED}❌ Failed to start service${NC}"
    fi
}

stop_service() {
    echo -e "${BLUE}🛑 Stopping VMware IPMI BMC Service...${NC}"
    sudo systemctl stop $SERVICE_NAME
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Service stopped successfully${NC}"
    else
        echo -e "${RED}❌ Failed to stop service${NC}"
    fi
}

restart_service() {
    echo -e "${BLUE}🔄 Restarting VMware IPMI BMC Service...${NC}"
    sudo systemctl restart $SERVICE_NAME
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Service restarted successfully${NC}"
        show_status
    else
        echo -e "${RED}❌ Failed to restart service${NC}"
    fi
}

enable_service() {
    echo -e "${BLUE}⚙️  Enabling VMware IPMI BMC Service...${NC}"
    sudo systemctl enable $SERVICE_NAME
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Service enabled for auto-start${NC}"
    else
        echo -e "${RED}❌ Failed to enable service${NC}"
    fi
}

disable_service() {
    echo -e "${BLUE}⚙️  Disabling VMware IPMI BMC Service...${NC}"
    sudo systemctl disable $SERVICE_NAME
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Service disabled${NC}"
    else
        echo -e "${RED}❌ Failed to disable service${NC}"
    fi
}

show_logs() {
    echo -e "${BLUE}📋 VMware IPMI BMC Service Logs${NC}"
    echo "================================="
    if [ "$1" = "-f" ]; then
        echo -e "${YELLOW}📡 Following logs (Ctrl+C to stop)...${NC}"
        sudo journalctl -u $SERVICE_NAME -f
    else
        sudo journalctl -u $SERVICE_NAME -n 20
    fi
}

test_service() {
    echo -e "${BLUE}🧪 Testing VMware IPMI BMC Service${NC}"
    echo "==================================="
    
    # Test basic connectivity
    echo -e "\n${YELLOW}Testing basic connectivity...${NC}"
    result=$(ipmitool -I lanplus -H 127.0.0.1 -U admin -P password chassis power status 2>&1)
    if [[ $result == *"Chassis Power is"* ]]; then
        echo -e "${GREEN}✅ Basic connectivity: OK${NC}"
        echo "   $result"
    else
        echo -e "${RED}❌ Basic connectivity: FAILED${NC}"
        echo "   $result"
        return 1
    fi
    
    # Test power control
    echo -e "\n${YELLOW}Testing power control...${NC}"
    result=$(ipmitool -I lanplus -H 127.0.0.1 -U admin -P password chassis power off 2>&1)
    if [[ $result == *"Down/Off"* ]]; then
        echo -e "${GREEN}✅ Power off: OK${NC}"
    else
        echo -e "${RED}❌ Power off: FAILED${NC}"
        echo "   $result"
    fi
    
    result=$(ipmitool -I lanplus -H 127.0.0.1 -U admin -P password chassis power on 2>&1)
    if [[ $result == *"Up/On"* ]]; then
        echo -e "${GREEN}✅ Power on: OK${NC}"
    else
        echo -e "${RED}❌ Power on: FAILED${NC}"
        echo "   $result"
    fi
    
    echo -e "\n${GREEN}🎉 Service tests completed${NC}"
}

show_help() {
    echo -e "${BLUE}VMware IPMI BMC Service Control${NC}"
    echo "==============================="
    echo ""
    echo "Usage: $0 {start|stop|restart|status|enable|disable|logs|test|help}"
    echo ""
    echo "Commands:"
    echo "  start     - Start the service"
    echo "  stop      - Stop the service" 
    echo "  restart   - Restart the service"
    echo "  status    - Show service status"
    echo "  enable    - Enable auto-start on boot"
    echo "  disable   - Disable auto-start"
    echo "  logs      - Show recent logs"
    echo "  logs -f   - Follow logs in real-time"
    echo "  test      - Run service tests"
    echo "  help      - Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 start"
    echo "  $0 logs -f"
    echo "  $0 test"
}

# Main script logic
case "$1" in
    start)
        start_service
        ;;
    stop)
        stop_service
        ;;
    restart)
        restart_service
        ;;
    status)
        show_status
        ;;
    enable)
        enable_service
        ;;
    disable)
        disable_service
        ;;
    logs)
        show_logs "$2"
        ;;
    test)
        test_service
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}❌ Unknown command: $1${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac
