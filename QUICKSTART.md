# Quick Start Guide

Get up and running in 5 minutes!

## Prerequisites

- Docker and Docker Compose installed
- Slskd instance running (with API key)
- Spotify playlist CSV export

## Installation

### Option 1: Automated Install (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd slskd-spotify-self-host

# Run the install script
chmod +x install.sh
./install.sh
```

The script will:
- Check for Docker/Docker Compose
- Create .env configuration file
- Optionally prompt for your API key
- Build and start the application

### Option 2: Manual Install

```bash
# Clone and navigate
git clone <repository-url>
cd slskd-spotify-self-host

# Create environment file
cp .env.example .env

# Edit and add your API key
nano .env
# Set SLSKD_API_KEY=your_key_here

# Start the application
docker-compose up -d
```

## Access the Application

Open your browser and go to:
```
http://localhost:5070
```

Or access from another device on your network:
```
http://YOUR_SERVER_IP:5070
```

## First-Time Setup

1. **Configure Slskd Connection**
   - Click "Settings" in the navigation
   - Enter your Slskd URL (e.g., `http://192.168.1.124:5030`)
   - Enter your API key
   - Adjust smart quality filters if desired
   - Click "Save Settings"

2. **Upload Spotify CSV**
   - Return to Dashboard
   - Drag & drop your Spotify CSV export
   - Review the artist count

3. **Start Searching**
   - Click "Start Search"
   - Monitor progress
   - Wait for completion

4. **Browse Results**
   - Click on any artist to see top quality results
   - Results are automatically ranked by quality
   - Only top 5 best files shown per artist

## Smart Quality Filtering

The application automatically filters results to show only high-quality files:

**Default Filters:**
- ✓ Minimum bitrate: 192 kbps (or lossless)
- ✓ Maximum queue: 50 slots
- ✓ Minimum speed: 50 KB/s
- ✓ Top results shown: 5 per artist

**Quality Scoring:**
- FLAC/Lossless files get highest priority
- 320 kbps MP3 gets high priority
- Instant availability (no queue) gets bonus
- Fast upload speeds increase ranking
- Long queues heavily penalized
- Locked files excluded

## Exporting Spotify Playlists

### Using Exportify (Recommended)

1. Go to [https://exportify.net/](https://exportify.net/)
2. Click "Get Started"
3. Log in with Spotify
4. Select playlist to export
5. Click "Export" button
6. Save CSV file

### Using Spotify Data Download

1. Go to Spotify Account page
2. Request your data
3. Wait for email (can take a few days)
4. Download and extract ZIP
5. Find playlist CSV files

## Common Commands

```bash
# View logs
docker-compose logs -f

# Restart application
docker-compose restart

# Stop application
docker-compose stop

# Start application
docker-compose start

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

## Troubleshooting

**Can't connect to application?**
```bash
# Check if container is running
docker-compose ps

# View logs for errors
docker-compose logs
```

**No search results?**
- Check Slskd is connected to Soulseek network
- Verify API key is correct in Settings
- Try lowering quality filters in Settings

**Port 5070 already in use?**
- Edit `docker-compose.yml`
- Change `5070:5000` to `5071:5000` (or any available port)
- Restart: `docker-compose up -d`

## Workflow Example

1. Export "Liked Songs" from Spotify → `liked_songs.csv`
2. Upload CSV to application
3. Start search → Searches 50 artists
4. Browse results → See top 5 files per artist
5. Click artist → View details with quality scores
6. "Open in Slskd" → Manual download
7. Mark as reviewed → Track progress

## Advanced Configuration

Edit `.env` to customize:

```env
# Search behavior
SEARCH_TIMEOUT=15        # Search wait time
SEARCH_DELAY=3           # Delay between searches

# Quality filters (also adjustable in web UI)
MIN_BITRATE=192          # Minimum acceptable bitrate
MAX_QUEUE_LENGTH=50      # Maximum queue to accept
MIN_SPEED_KBS=50         # Minimum upload speed
TOP_RESULTS_COUNT=5      # How many results to show
```

## Next Steps

- Read the full [README.md](README.md) for detailed information
- Check [CHANGELOG.md](CHANGELOG.md) for version history
- Report issues on GitHub
- Star the repository if you find it useful!

---

**Made with ❤️ for smart music discovery**
