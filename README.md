# Spotify to Slskd Search Aggregator

**Smart music discovery powered by intelligent quality filtering**

A self-hosted web application that automatically searches Slskd for your Spotify favorite artists and shows you only the **highest-quality, most available files**. No more scrolling through hundreds of results – see only the top 5 best options per artist.

[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/python-3.9+-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/flask-%23000.svg?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)

---

## 🎵 What Makes This Special

**Smart Quality Filtering** automatically ranks every search result by:
- 🎧 **Audio Quality** - FLAC/lossless files prioritized, then 320kbps, 256kbps, etc.
- ⚡ **Availability** - Files with no queue get instant priority
- 🚀 **Speed** - Fast upload speeds ranked higher
- 🎯 **Top 5 Only** - See just the best results, not hundreds of options

**NO credentials hardcoded** - Configure everything through the web interface. Safe, secure, and easy.

---

## ✨ Features

### Smart Features
- 🧠 **Intelligent Quality Scoring** - Automatic ranking by bitrate, speed, queue length
- 🎯 **Top Results Only** - Shows top 5 best files per artist (configurable)
- ⚡ **Instant Download Priority** - Files with no queue appear first
- 🔒 **Automatic Filtering** - Rejects low bitrate, locked files, slow sources

### Core Features
- 📊 **CSV Upload** - Upload Spotify playlist exports
- 🔍 **Background Search** - Non-blocking artist searches
- 💾 **Persistent Storage** - Results saved to JSON
- 🎨 **Modern Dark UI** - Responsive Tailwind CSS interface
- ⚙️ **Web Configuration** - No file editing required
- ✅ **Progress Tracking** - Mark artists as reviewed
- 📈 **Statistics Dashboard** - Track searches and results
- 📤 **Export Options** - CSV export and JSON backup

### Security & Deployment
- 🐳 **Docker Ready** - One-command installation
- 🔐 **Secure** - No hardcoded credentials, non-root container
- 🏥 **Health Checks** - Monitor application status
- 🔄 **Easy Updates** - Pull and rebuild

---

## 📋 Table of Contents

- [Quick Start](#-quick-start)
- [Installation Methods](#-installation-methods)
  - [Method 1: Docker Compose (Recommended)](#method-1-docker-compose-recommended)
  - [Method 2: Standalone Docker](#method-2-standalone-docker)
  - [Method 3: Proxmox LXC](#method-3-proxmox-lxc)
- [Configuration](#-configuration)
- [Usage Guide](#-usage-guide)
- [Smart Quality Filtering](#-smart-quality-filtering)
- [Troubleshooting](#-troubleshooting)
- [API Reference](#-api-reference)
- [Development](#-development)

---

## 🚀 Quick Start

Get running in **under 5 minutes**:

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/slskd-spotify-self-host.git
cd slskd-spotify-self-host

# 2. Run the installer
chmod +x install.sh
./install.sh

# 3. Access the web interface
# Open http://localhost:5070 in your browser

# 4. Configure your Slskd connection
# Go to Settings → Enter API key → Save

# 5. Upload your Spotify CSV and start searching!
```

That's it! The installer handles everything else.

---

## 📦 Installation Methods

### Prerequisites

**Required:**
- Slskd instance running with API access
- Docker and Docker Compose **OR** Proxmox with LXC
- Network connectivity between this app and Slskd

**Optional:**
- Spotify account (to export playlists)

---

### Method 1: Docker Compose (Recommended)

**Best for:** Most users, easiest setup, automatic updates

#### Step 1: Get the Files

```bash
git clone https://github.com/yourusername/slskd-spotify-self-host.git
cd slskd-spotify-self-host
```

#### Step 2: Create Environment File

```bash
cp .env.example .env
nano .env  # or use your preferred editor
```

Add your Slskd API key:
```env
SLSKD_URL=http://192.168.1.124:5030
SLSKD_API_KEY=your_api_key_here
SLSKD_URL_BASE=/
```

#### Step 3: Start the Application

```bash
docker-compose up -d
```

#### Step 4: Access the Interface

Open your browser:
```
http://localhost:5070
```

Or from another device on your network:
```
http://YOUR_SERVER_IP:5070
```

#### Common Commands

```bash
# View logs
docker-compose logs -f

# Stop the application
docker-compose down

# Restart after changes
docker-compose restart

# Update to latest version
git pull
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Check status
docker-compose ps

# View resource usage
docker stats spotify-slskd-search
```

---

### Method 2: Standalone Docker

**Best for:** Single container deployment, custom networks

#### Step 1: Build the Image

```bash
git clone https://github.com/yourusername/slskd-spotify-self-host.git
cd slskd-spotify-self-host

docker build -t spotify-slskd-search .
```

#### Step 2: Create Data Directory

```bash
mkdir -p ./data
chmod 777 ./data
```

#### Step 3: Run the Container

```bash
docker run -d \
  --name spotify-slskd-search \
  --restart unless-stopped \
  -p 5070:5000 \
  -v $(pwd)/data:/app/data \
  -e SLSKD_URL=http://192.168.1.124:5030 \
  -e SLSKD_API_KEY=your_api_key_here \
  -e SLSKD_URL_BASE=/ \
  -e SEARCH_TIMEOUT=15 \
  -e SEARCH_DELAY=3 \
  spotify-slskd-search
```

#### Step 4: Verify It's Running

```bash
docker logs spotify-slskd-search
```

You should see:
```
Spotify to Slskd Search Aggregator with Smart Quality
Slskd URL: http://192.168.1.124:5030
...
```

#### Management Commands

```bash
# Stop container
docker stop spotify-slskd-search

# Start container
docker start spotify-slskd-search

# View logs
docker logs -f spotify-slskd-search

# Remove container
docker rm -f spotify-slskd-search

# Update
docker pull spotify-slskd-search:latest
docker stop spotify-slskd-search
docker rm spotify-slskd-search
# Then run the docker run command again
```

---

### Method 3: Proxmox LXC

**Best for:** Proxmox users, resource efficiency, isolation

I've created a complete installation script for Proxmox LXC deployment.

#### Automatic Installation Script

Save this as `proxmox-install.sh` on your Proxmox host:

```bash
#!/bin/bash
# Proxmox LXC Installation Script for Spotify to Slskd Search Aggregator

set -e

echo "======================================================="
echo "  Spotify to Slskd Search Aggregator"
echo "  Proxmox LXC Installation"
echo "======================================================="
echo ""

# Configuration
CT_ID=121  # Change this if you want a different container ID
CT_HOSTNAME="spotify-slskd-search"
CT_PASSWORD="changeme"  # Change this!
CT_STORAGE="local-lvm"  # Your Proxmox storage
CT_MEMORY=1024  # 1GB RAM
CT_SWAP=512
CT_DISK=5  # 5GB disk
CT_CORES=2
BRIDGE="vmbr0"  # Your network bridge

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Creating LXC container...${NC}"

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
pct start $CT_ID
sleep 5

echo -e "${BLUE}Installing dependencies...${NC}"

# Install Python and dependencies
pct exec $CT_ID -- bash -c "
    apt update
    apt install -y python3 python3-pip git curl
    pip3 install --upgrade pip
"

echo -e "${GREEN}✓${NC} Dependencies installed"

# Clone repository
echo -e "${BLUE}Cloning repository...${NC}"
pct exec $CT_ID -- bash -c "
    cd /opt
    git clone https://github.com/yourusername/slskd-spotify-self-host.git
    cd slskd-spotify-self-host
    pip3 install -r requirements.txt
"

echo -e "${GREEN}✓${NC} Repository cloned and dependencies installed"

# Create configuration
echo -e "${BLUE}Creating configuration...${NC}"
pct exec $CT_ID -- bash -c "
    cd /opt/slskd-spotify-self-host
    cp .env.example .env
    mkdir -p /opt/slskd-spotify-self-host/data
"

# Create systemd service
echo -e "${BLUE}Creating systemd service...${NC}"
pct exec $CT_ID -- bash -c "cat > /etc/systemd/system/spotify-slskd-search.service << 'EOF'
[Unit]
Description=Spotify to Slskd Search Aggregator
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

[Install]
WantedBy=multi-user.target
EOF
"

# Enable and start service
pct exec $CT_ID -- bash -c "
    systemctl daemon-reload
    systemctl enable spotify-slskd-search
    systemctl start spotify-slskd-search
"

echo -e "${GREEN}✓${NC} Service created and started"

# Get container IP
CT_IP=$(pct exec $CT_ID -- hostname -I | awk '{print $1}')

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
echo ""
echo -e "${BLUE}Access the application:${NC}"
echo "  http://$CT_IP:5000"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "  1. Access the web interface"
echo "  2. Go to Settings"
echo "  3. Enter your Slskd API key"
echo "  4. Configure quality filters"
echo "  5. Start searching!"
echo ""
echo -e "${BLUE}Configuration:${NC}"
echo "  Edit: pct exec $CT_ID -- nano /opt/slskd-spotify-self-host/.env"
echo "  Logs: pct exec $CT_ID -- journalctl -u spotify-slskd-search -f"
echo "  Restart: pct exec $CT_ID -- systemctl restart spotify-slskd-search"
echo ""
echo -e "${YELLOW}IMPORTANT: Change the container password!${NC}"
echo "  pct set $CT_ID --password"
echo ""
```

#### Run the Installation

On your Proxmox host:

```bash
chmod +x proxmox-install.sh
./proxmox-install.sh
```

The script will:
1. Create Ubuntu 22.04 LXC container
2. Install Python and dependencies
3. Clone the repository
4. Set up systemd service
5. Start the application

#### Manual LXC Installation

If you prefer manual installation:

**Step 1: Create LXC Container**

In Proxmox web interface:
- Create → CT → Ubuntu 22.04
- CT ID: 121 (or your choice)
- Hostname: spotify-slskd-search
- Memory: 1024 MB
- Disk: 5 GB
- Network: Bridge, DHCP

**Step 2: Install Dependencies**

```bash
pct enter 121

apt update
apt install -y python3 python3-pip git
```

**Step 3: Clone and Setup**

```bash
cd /opt
git clone https://github.com/yourusername/slskd-spotify-self-host.git
cd slskd-spotify-self-host

pip3 install -r requirements.txt

cp .env.example .env
nano .env  # Add your API key
```

**Step 4: Create Systemd Service**

```bash
nano /etc/systemd/system/spotify-slskd-search.service
```

Paste:
```ini
[Unit]
Description=Spotify to Slskd Search Aggregator
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/slskd-spotify-self-host
Environment="PATH=/usr/bin"
EnvironmentFile=/opt/slskd-spotify-self-host/.env
ExecStart=/usr/bin/python3 /opt/slskd-spotify-self-host/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Step 5: Enable and Start**

```bash
systemctl daemon-reload
systemctl enable spotify-slskd-search
systemctl start spotify-slskd-search
systemctl status spotify-slskd-search
```

**Step 6: Access the Application**

Get your container IP:
```bash
hostname -I
```

Open browser:
```
http://CONTAINER_IP:5000
```

---

## ⚙️ Configuration

### Web-Based Configuration (Recommended)

**No file editing needed!**

1. Open the web interface
2. Click **Settings** in the navigation
3. Configure:
   - **Slskd URL** (e.g., `http://192.168.1.124:5030`)
   - **API Key** (from Slskd Settings → API Keys)
   - **Quality Filters** (bitrate, queue, speed)
   - **Search Settings** (timeout, delay)
4. Click **Save Settings**

Settings are saved to `data/config.json` and persist across restarts.

### Environment Variables (Alternative)

Edit `.env` file:

```env
# Slskd Connection
SLSKD_URL=http://192.168.1.124:5030
SLSKD_API_KEY=your_api_key_here
SLSKD_USERNAME=  # Optional
SLSKD_PASSWORD=  # Optional
SLSKD_URL_BASE=/

# Search Settings
SEARCH_TIMEOUT=15  # seconds
SEARCH_DELAY=3     # seconds between searches

# Data Storage
DATA_DIR=/app/data

# Flask Settings
FLASK_ENV=production
SECRET_KEY=your_random_secret_key
```

### Getting Your Slskd API Key

1. Open Slskd web interface (e.g., `http://192.168.1.124:5030`)
2. Go to **Settings** → **API Keys**
3. Click **Generate New Key**
4. Copy the key
5. Paste into web configuration or `.env` file

---

## 📖 Usage Guide

### Complete Workflow

#### 1. Export Spotify Playlist

**Option A: Using Exportify** (Recommended)
1. Go to [https://exportify.net/](https://exportify.net/)
2. Click "Get Started"
3. Log in with Spotify
4. Select playlist
5. Click "Export" → Download CSV

**Option B: Spotify Data Download**
1. Go to Spotify Account page
2. Request your data
3. Wait for email (2-30 days)
4. Download ZIP
5. Extract and find playlist CSVs

#### 2. Upload CSV

1. Open web interface
2. Drag & drop CSV file into upload area
3. Review artist count summary
4. Click **Start Search**

#### 3. Monitor Progress

- Watch the progress bar
- See current artist being searched
- View any errors in real-time
- Navigate away if needed (search continues in background)

#### 4. Browse Results

**Dashboard View:**
- See all searched artists
- Filter by review status (All, Reviewed, Not Reviewed)
- Sort by name, results count, or date
- View total statistics

**Artist Detail View:**
- See top 5 quality-ranked results
- Each result shows:
  - Quality badge (FLAC/320kbps/etc.)
  - Quality score
  - Instant start indicator (if available)
  - File size, queue length, speed
  - Username
- Click "Open in Slskd" to download

#### 5. Download Files

1. Click **Open in Slskd** button
2. Slskd opens in new tab
3. Manually download the file in Slskd
4. Return to this app
5. Mark artist as **Reviewed** when done

---

## 🧠 Smart Quality Filtering

### How It Works

Every search result is automatically scored and ranked:

**Quality Score = Bitrate Points + Speed Points + Queue Points**

### Scoring Breakdown

**Bitrate/Format (0-100 points):**
- FLAC/WAV/ALAC/APE: **100 points** (lossless)
- 320 kbps: **90 points**
- 256 kbps: **70 points**
- 192 kbps: **50 points**
- Below 192 kbps: **20 points** (usually filtered out)

**Upload Speed (0-50 points):**
- 2+ MB/s: **50 points**
- 1-2 MB/s: **40 points**
- 500 KB/s - 1 MB/s: **30 points**
- 100-500 KB/s: **20 points**
- 50-100 KB/s: **10 points**
- Below 50 KB/s: **0 points** (filtered out)

**Queue Length (-100 to +50 points):**
- No queue: **+50 bonus**
- 1-5 slots: **-10 points**
- 6-10 slots: **-30 points**
- 11-25 slots: **-50 points**
- 26+ slots: **-100 points**

**Free Slot Bonus:**
- Has free upload slot: **+25 points**

### Strict Filters

Files are excluded if they:
- ❌ Have bitrate < 192 kbps (unless lossless)
- ❌ Have queue length > 50 slots
- ❌ Have upload speed < 50 KB/s
- ❌ Are locked
- ❌ Are from banned users

### Customization

Adjust in **Settings** page:

```
Minimum Bitrate: 192 kbps (default)
  - Lower to 128 for more results
  - Raise to 256 for higher quality only

Maximum Queue: 50 slots (default)
  - Lower to 25 for faster availability
  - Raise to 100 if willing to wait

Minimum Speed: 50 KB/s (default)
  - Lower to 25 for slower connections
  - Raise to 100 for faster downloads

Top Results Count: 5 (default)
  - Lower to 3 for fewer options
  - Raise to 10 for more choices
```

### Example Results

**Before Smart Filtering:**
```
Artist: Polyphia
Results: 247 files (many duplicates, varying quality, long queues)
```

**After Smart Filtering:**
```
#1 Polyphia - Playing God.flac (Score: 175.0) ⚡ INSTANT
   FLAC | 45.2 MB | No Queue | 2.5 MB/s | User: FastSharer

#2 Polyphia - Playing God.mp3 (Score: 140.0) ⚡ INSTANT
   320 kbps | 12.3 MB | No Queue | 1.8 MB/s | User: MusicLover

#3 Polyphia - Playing God.mp3 (Score: 110.0)
   320 kbps | 12.1 MB | Queue: 3 | 1.1 MB/s | User: SpeedDemon

#4 Polyphia - Playing God.flac (Score: 95.0)
   FLAC | 44.8 MB | Queue: 5 | 850 KB/s | User: HighQuality

#5 Polyphia - Playing God.mp3 (Score: 75.0)
   256 kbps | 10.2 MB | Queue: 8 | 500 KB/s | User: SlowAndSteady
```

---

## 🔧 Troubleshooting

### Cannot Access Web Interface

**Check container is running:**
```bash
# Docker Compose
docker-compose ps

# Docker
docker ps | grep spotify-slskd-search

# LXC
pct status 121
```

**Check logs:**
```bash
# Docker Compose
docker-compose logs

# Docker
docker logs spotify-slskd-search

# LXC
pct exec 121 -- journalctl -u spotify-slskd-search -f
```

**Verify port:**
```bash
# Should show port 5070 listening
netstat -tlnp | grep 5070

# Or
ss -tlnp | grep 5070
```

### Cannot Connect to Slskd

**Symptoms:**
- Health check fails
- "Cannot connect" errors
- No search results

**Solutions:**

1. **Test connectivity:**
   ```bash
   curl http://192.168.1.124:5030
   ```

2. **Verify API key:**
   - Go to Settings
   - Re-enter API key
   - Save

3. **Check Slskd is running:**
   ```bash
   # Check Slskd container/service status
   docker ps | grep slskd
   ```

4. **Network issues:**
   - Ensure both containers on same network
   - Check firewall rules
   - Verify IP address is correct

### No Search Results

**Causes:**
- Slskd not connected to Soulseek network
- Quality filters too strict
- API timeout too short
- Artists don't exist on network

**Solutions:**

1. **Check Slskd connection:**
   - Open Slskd web interface
   - Verify connected to network
   - Check search works in Slskd directly

2. **Relax quality filters:**
   - Go to Settings
   - Lower minimum bitrate to 128
   - Increase max queue to 100
   - Lower minimum speed to 25
   - Save and re-search

3. **Increase timeout:**
   - Go to Settings
   - Set search timeout to 30 seconds
   - Save

4. **Check logs:**
   ```bash
   docker-compose logs -f
   ```

### Search Hangs or Slow

**Symptoms:**
- Progress bar stuck
- Very slow searches
- Timeouts

**Solutions:**

1. **Reduce batch size:**
   - Search fewer artists at once
   - Split large CSVs

2. **Increase delays:**
   - Go to Settings
   - Set search delay to 5 seconds
   - Reduces API load

3. **Check resources:**
   ```bash
   docker stats spotify-slskd-search
   ```
   - If memory/CPU high, increase container limits

### Port Already in Use

**Error:** `Bind for 0.0.0.0:5070 failed: port is already allocated`

**Solution:**

Edit `docker-compose.yml`:
```yaml
ports:
  - "5071:5000"  # Change 5070 to any free port
```

Restart:
```bash
docker-compose down
docker-compose up -d
```

### Permission Errors

**Symptoms:**
- Cannot write to data directory
- "Permission denied" errors

**Solutions:**

```bash
# Fix permissions
sudo chown -R 1000:1000 ./data
sudo chmod -R 755 ./data

# Restart container
docker-compose restart
```

### Container Keeps Restarting

**Check logs for errors:**
```bash
docker logs spotify-slskd-search --tail 100
```

**Common causes:**
- Missing environment variables
- Invalid configuration
- Port conflict
- Dependency issues

**Solutions:**

1. **Verify .env file exists:**
   ```bash
   ls -la .env
   ```

2. **Check all variables set:**
   ```bash
   cat .env
   ```

3. **Rebuild container:**
   ```bash
   docker-compose down
   docker-compose build --no-cache
   docker-compose up -d
   ```

---

## 📡 API Reference

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Main dashboard |
| GET | `/settings` | Configuration page |
| POST | `/settings` | Save configuration |
| GET | `/artist/<name>` | Artist detail page |
| POST | `/upload` | Upload CSV file |
| POST | `/search/start` | Start background search |
| GET | `/search/status` | Get search progress |
| POST | `/search/cancel` | Cancel ongoing search |
| POST | `/api/mark_reviewed/<name>` | Mark artist as reviewed |
| GET | `/api/stats` | Get statistics |
| POST | `/artist/<name>/delete` | Delete artist results |
| GET | `/export/csv` | Export results to CSV |
| GET | `/backup/download` | Download JSON backup |
| GET | `/health` | Health check endpoint |

### Example API Usage

**Start a search:**
```bash
curl -X POST http://localhost:5070/search/start \
  -H "Content-Type: application/json" \
  -d '{"artists": ["Polyphia", "Chon", "Ado"]}'
```

**Check search status:**
```bash
curl http://localhost:5070/search/status
```

**Get statistics:**
```bash
curl http://localhost:5070/api/stats
```

**Health check:**
```bash
curl http://localhost:5070/health
```

---

## 🛠️ Development

### Local Development Setup

```bash
# Clone repository
git clone https://github.com/yourusername/slskd-spotify-self-host.git
cd slskd-spotify-self-host

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Create configuration
cp .env.example .env
nano .env  # Add your settings

# Run development server
export FLASK_ENV=development
python app.py
```

Access at `http://localhost:5000`

### Project Structure

```
slskd-spotify-self-host/
├── app.py                       # Main Flask application
├── templates/
│   ├── base.html               # Base template
│   ├── index.html              # Dashboard
│   ├── artist.html             # Artist detail page
│   └── settings.html           # Configuration page
├── static/                     # Static files (if any)
├── data/                       # Data directory
│   ├── search_results.json    # Search results
│   ├── config.json            # User configuration
│   ├── uploads/               # Uploaded CSV files
│   └── application.log        # Application logs
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Docker image
├── docker-compose.yml          # Docker Compose config
├── install.sh                  # Installation script
├── .env.example                # Environment template
├── README.md                   # This file
├── QUICKSTART.md               # Quick start guide
├── CHANGELOG.md                # Version history
└── LICENSE                     # MIT license
```

### Technology Stack

- **Backend:** Python 3.9, Flask 3.0
- **API Client:** slskd-api 0.3.0
- **Frontend:** HTML5, Tailwind CSS 3.x, Vanilla JavaScript
- **Storage:** JSON file-based
- **Deployment:** Docker, Docker Compose

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

## 🙏 Credits

- Built with [Flask](https://flask.palletsprojects.com/)
- Uses [slskd-api](https://pypi.org/project/slskd-api/)
- Styled with [Tailwind CSS](https://tailwindcss.com/)
- Designed for [Slskd](https://github.com/slskd/slskd)

---

## 📞 Support

- 📖 [Quick Start Guide](QUICKSTART.md)
- 📝 [Changelog](CHANGELOG.md)
- 🐛 [Report Issues](https://github.com/yourusername/slskd-spotify-self-host/issues)
- 💬 [Discussions](https://github.com/yourusername/slskd-spotify-self-host/discussions)

---

## 🎯 Quick Links

- [Docker Hub](https://hub.docker.com/) - Get Docker
- [Slskd Documentation](https://github.com/slskd/slskd) - Learn about Slskd
- [Exportify](https://exportify.net/) - Export Spotify playlists
- [Proxmox](https://www.proxmox.com/) - Proxmox VE

---

**Made with ❤️ for smart music discovery**

No more scrolling through hundreds of low-quality results. Just the top 5 best files, automatically ranked by quality, speed, and availability.

**Star this repo if you find it useful!** ⭐

## How to Get Your Slskd API Key

To connect this tool to your Soulseek client, you need an API Key.

1. **Open Slskd**: Go to your Slskd Web UI (e.g., http://192.168.1.124:5030).
2. **Go to Settings**: Click the Settings (Cog Icon) ⚙️ in the side menu.
3. **Open Authentication**: Click on the Authentication tab.
4. **Create a Key**:
    - Scroll down to the API Keys section.
    - Click the + (Plus) button to add a new key.
    - **Name**: Enter `SpotifySearch` (or any name).
    - **CIDR**: Enter `0.0.0.0/0` (this allows your local docker container to connect).
    - **Role**: Select `Administrator` (required to manage downloads).
5. **Copy the Key**: Click the Copy icon next to your new key.
6. **Paste it**: Go back to the Spotify Search tool and paste it into the API Key field.
