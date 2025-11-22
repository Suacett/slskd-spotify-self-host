#!/bin/bash
# Proxmox LXC Installation Script for Spotify to Slskd Search Aggregator
# Run this script on your Proxmox host to create and configure an LXC container

set -e

echo "======================================================="
echo "  Spotify to Slskd Search Aggregator"
echo "  Proxmox LXC Installation"
echo "======================================================="
echo ""

# Configuration - Edit these values as needed
CT_ID=121  # Change this if you want a different container ID
CT_HOSTNAME="spotify-slskd-search"
CT_PASSWORD="changeme"  # IMPORTANT: Change this!
CT_STORAGE="local-lvm"  # Your Proxmox storage
CT_MEMORY=1024  # 1GB RAM
CT_SWAP=512
CT_DISK=5  # 5GB disk
CT_CORES=2
BRIDGE="vmbr0"  # Your network bridge
REPO_URL="https://github.com/yourusername/slskd-spotify-self-host.git"  # Update with actual repo URL

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Configuration:${NC}"
echo "  Container ID: $CT_ID"
echo "  Hostname: $CT_HOSTNAME"
echo "  Memory: ${CT_MEMORY}MB"
echo "  Disk: ${CT_DISK}GB"
echo "  Cores: $CT_CORES"
echo "  Storage: $CT_STORAGE"
echo "  Bridge: $BRIDGE"
echo ""

# Confirmation
read -p "Continue with installation? (y/n): " -r
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Installation cancelled."
    exit 0
fi

echo ""
echo -e "${BLUE}Step 1: Creating LXC container...${NC}"

# Download Ubuntu 22.04 template if not exists
if ! pveam list local | grep -q ubuntu-22.04; then
    echo "Downloading Ubuntu 22.04 template..."
    pveam download local ubuntu-22.04-standard_22.04-1_amd64.tar.zst
fi

# Create container
pct create $CT_ID local:vztmpl/ubuntu-22.04-standard_22.04-1_amd64.tar.zst \
    --hostname $CT_HOSTNAME \
    --password $CT_PASSWORD \
    --storage $CT_STORAGE \
    --memory $CT_MEMORY \
    --swap $CT_SWAP \
    --cores $CT_CORES \
    --net0 name=eth0,bridge=$BRIDGE,ip=dhcp \
    --rootfs $CT_STORAGE:$CT_DISK \
    --unprivileged 1 \
    --features nesting=1 \
    --onboot 1

echo -e "${GREEN}✓${NC} Container created with ID: $CT_ID"

# Start container
echo -e "${BLUE}Step 2: Starting container...${NC}"
pct start $CT_ID
sleep 5
echo -e "${GREEN}✓${NC} Container started"

# Install dependencies
echo -e "${BLUE}Step 3: Installing dependencies...${NC}"
pct exec $CT_ID -- bash -c "
    export DEBIAN_FRONTEND=noninteractive
    apt update
    apt install -y python3 python3-pip git curl
    pip3 install --upgrade pip
"
echo -e "${GREEN}✓${NC} Dependencies installed"

# Clone repository
echo -e "${BLUE}Step 4: Cloning repository...${NC}"
pct exec $CT_ID -- bash -c "
    cd /opt
    git clone $REPO_URL
    cd slskd-spotify-self-host
    pip3 install -r requirements.txt
"
echo -e "${GREEN}✓${NC} Repository cloned"

# Create configuration
echo -e "${BLUE}Step 5: Creating configuration...${NC}"
pct exec $CT_ID -- bash -c "
    cd /opt/slskd-spotify-self-host
    cp .env.example .env
    mkdir -p /opt/slskd-spotify-self-host/data
    chmod 755 /opt/slskd-spotify-self-host/data
"
echo -e "${GREEN}✓${NC} Configuration created"

# Create systemd service
echo -e "${BLUE}Step 6: Creating systemd service...${NC}"
pct exec $CT_ID -- bash -c "cat > /etc/systemd/system/spotify-slskd-search.service << 'EOFSERVICE'
[Unit]
Description=Spotify to Slskd Search Aggregator with Smart Quality Filtering
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/slskd-spotify-self-host
Environment=\"PATH=/usr/bin\"
EnvironmentFile=/opt/slskd-spotify-self-host/.env
ExecStart=/usr/bin/python3 /opt/slskd-spotify-self-host/app.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Security
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOFSERVICE
"
echo -e "${GREEN}✓${NC} Systemd service created"

# Enable and start service
echo -e "${BLUE}Step 7: Enabling and starting service...${NC}"
pct exec $CT_ID -- bash -c "
    systemctl daemon-reload
    systemctl enable spotify-slskd-search
    systemctl start spotify-slskd-search
"
echo -e "${GREEN}✓${NC} Service started"

# Wait for service to start
echo "Waiting for service to initialize..."
sleep 3

# Get container IP
CT_IP=$(pct exec $CT_ID -- hostname -I | awk '{print $1}')

# Check service status
SERVICE_STATUS=$(pct exec $CT_ID -- systemctl is-active spotify-slskd-search)

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Installation Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Container Details:${NC}"
echo "  ID: $CT_ID"
echo "  Hostname: $CT_HOSTNAME"
echo "  IP Address: $CT_IP"
echo "  Password: $CT_PASSWORD"
echo "  Service Status: $SERVICE_STATUS"
echo ""
echo -e "${BLUE}Access the application:${NC}"
echo "  http://$CT_IP:5000"
echo ""
echo -e "${BLUE}First-Time Setup:${NC}"
echo "  1. Open http://$CT_IP:5000 in your browser"
echo "  2. Click 'Settings' in the navigation"
echo "  3. Enter your Slskd API key"
echo "  4. Configure quality filters (or use defaults)"
echo "  5. Click 'Save Settings'"
echo "  6. Return to Dashboard and upload a Spotify CSV"
echo "  7. Click 'Start Search' and enjoy!"
echo ""
echo -e "${BLUE}Management Commands:${NC}"
echo "  View logs:    pct exec $CT_ID -- journalctl -u spotify-slskd-search -f"
echo "  Restart:      pct exec $CT_ID -- systemctl restart spotify-slskd-search"
echo "  Stop:         pct exec $CT_ID -- systemctl stop spotify-slskd-search"
echo "  Start:        pct exec $CT_ID -- systemctl start spotify-slskd-search"
echo "  Status:       pct exec $CT_ID -- systemctl status spotify-slskd-search"
echo "  Shell:        pct enter $CT_ID"
echo "  Edit config:  pct exec $CT_ID -- nano /opt/slskd-spotify-self-host/.env"
echo ""
echo -e "${BLUE}Update Application:${NC}"
echo "  pct exec $CT_ID -- bash -c 'cd /opt/slskd-spotify-self-host && git pull && systemctl restart spotify-slskd-search'"
echo ""
echo -e "${YELLOW}⚠️  IMPORTANT SECURITY NOTES:${NC}"
echo "  1. Change the container password:"
echo "     pct set $CT_ID --password"
echo ""
echo "  2. Configure firewall rules if needed"
echo ""
echo "  3. Backup your data directory regularly:"
echo "     /opt/slskd-spotify-self-host/data/"
echo ""
echo -e "${BLUE}Troubleshooting:${NC}"
echo "  If service won't start, check logs:"
echo "    pct exec $CT_ID -- journalctl -u spotify-slskd-search -n 50"
echo ""
echo "  If port is inaccessible, check firewall:"
echo "    pct exec $CT_ID -- netstat -tlnp | grep 5000"
echo ""

# Health check
echo -e "${BLUE}Performing health check...${NC}"
sleep 2

if curl -s -o /dev/null -w "%{http_code}" "http://$CT_IP:5000/health" | grep -q "200\|503"; then
    echo -e "${GREEN}✓${NC} Application is responding"
else
    echo -e "${YELLOW}⚠${NC}  Application may still be starting up"
    echo "    Wait 10-20 seconds and try accessing http://$CT_IP:5000"
fi

echo ""
echo -e "${GREEN}Installation script complete!${NC}"
echo ""
echo "Next: Access http://$CT_IP:5000 and configure your Slskd connection"
echo ""
