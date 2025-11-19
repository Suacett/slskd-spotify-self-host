# Spotify to Slskd Search Aggregator

A self-hosted web application that helps you discover music on Slskd based on your Spotify favorites. This tool searches for your liked artists on Slskd and provides a browsing interface for manual review and download selection.

**🎵 Important**: This tool does NOT auto-download anything. It aggregates search results for you to manually review and select in the Slskd interface.

---

## Features

- 📊 **CSV Upload**: Upload Spotify playlist exports (CSV format)
- 🔍 **Automated Search**: Background search process for all unique artists
- 💾 **Persistent Storage**: Search results saved in JSON format
- 🎨 **Modern UI**: Clean, responsive interface with dark mode support
- 🔧 **Advanced Filtering**: Filter by quality (FLAC, 320kbps+), size, filename
- ✅ **Review Tracking**: Mark artists as reviewed to track progress
- 📈 **Statistics Dashboard**: Track total artists, results, and review status
- 🐳 **Docker Ready**: Easy deployment with Docker or Docker Compose
- 🔐 **Secure**: Non-root user, proper API key handling, health checks

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Deployment Options](#deployment-options)
  - [Option 1: Standalone Docker](#option-1-standalone-docker)
  - [Option 2: Integration with Existing Media Stack](#option-2-integration-with-existing-media-stack)
  - [Option 3: LXC Container](#option-3-lxc-container)
- [Usage Guide](#usage-guide)
- [API Endpoints](#api-endpoints)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [License](#license)

---

## Prerequisites

### Required

- **Slskd instance** running and accessible on your network
  - URL: `http://192.168.1.124:5030` (or your instance URL)
  - API key configured in Slskd settings
- **Docker** and **Docker Compose** (for Docker deployment)
  - OR **Proxmox with LXC** capability (for LXC deployment)
- **Network access** from deployment location to Slskd instance

### Recommended

- Desktop browser for accessing the web interface
- Spotify CSV export of your playlists or liked songs

---

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd slskd-spotify-self-host
```

### 2. Configure API Key

First, you need to set up an API key in your Slskd instance:

1. Access your Slskd web interface at `http://192.168.1.124:5030`
2. Go to Settings → API
3. Generate a new API key or use an existing one
4. Copy the API key

Then, create a `.env` file from the example:

```bash
cp .env.example .env
```

Edit `.env` and add your API key:

```env
SLSKD_API_KEY=your_actual_api_key_here
```

### 3. Build and Run

```bash
docker-compose up -d
```

### 4. Access the Interface

Open your browser and navigate to:

```
http://192.168.1.124:5070
```

(Or use your server's IP address if different)

---

## Configuration

All configuration is done through environment variables. See `.env.example` for all options:

| Variable | Default | Description |
|----------|---------|-------------|
| `SLSKD_URL` | `http://192.168.1.124:5030` | Your Slskd instance URL |
| `SLSKD_API_KEY` | *(required)* | Your Slskd API key |
| `SLSKD_URL_BASE` | `/` | Slskd API base path |
| `SEARCH_TIMEOUT` | `15` | Search timeout in seconds |
| `SEARCH_DELAY` | `3` | Delay between searches in seconds |
| `DATA_DIR` | `/app/data` | Data directory path (inside container) |
| `FLASK_ENV` | `production` | Flask environment |

### Getting Your Slskd API Key

1. Open Slskd web interface
2. Navigate to **Settings** → **API Keys**
3. Click **Generate New Key** or copy an existing key
4. Add it to your `.env` file

---

## Deployment Options

### Option 1: Standalone Docker

Best for: Simple, isolated deployment

1. **Clone and configure**:
   ```bash
   git clone <repository-url>
   cd slskd-spotify-self-host
   cp .env.example .env
   # Edit .env with your API key
   ```

2. **Build and run**:
   ```bash
   docker-compose up -d
   ```

3. **Access**:
   - Web UI: `http://192.168.1.124:5070`
   - Health check: `http://192.168.1.124:5070/health`

4. **View logs**:
   ```bash
   docker logs -f spotify-slskd-search
   ```

5. **Stop**:
   ```bash
   docker-compose down
   ```

### Option 2: Integration with Existing Media Stack

Best for: Integration with existing mediaapps container (CT120)

1. **Prepare the build context**:
   ```bash
   # Clone to a persistent location
   git clone <repository-url> /opt/spotify-slskd-search
   cd /opt/spotify-slskd-search
   cp .env.example .env
   # Edit .env with your API key
   ```

2. **Update your main docker-compose.yml**:

   Add the service from `docker-compose.mediaapps.yml` to your `/opt/media/docker-compose.yml`:

   ```yaml
   services:
     # ... your existing services ...

     spotify-slskd-search:
       build: /opt/spotify-slskd-search
       container_name: spotify-slskd-search
       restart: unless-stopped
       ports:
         - "5070:5000"
       environment:
         - SLSKD_URL=http://192.168.1.124:5030
         - SLSKD_API_KEY=${SLSKD_API_KEY}
         - SLSKD_URL_BASE=/
         - SEARCH_TIMEOUT=15
         - SEARCH_DELAY=3
         - DATA_DIR=/app/data
         - FLASK_ENV=production
       volumes:
         - /opt/media/spotify-slskd-data:/app/data
       networks:
         - media_net
   ```

3. **Create data directory**:
   ```bash
   mkdir -p /opt/media/spotify-slskd-data
   ```

4. **Add API key to environment**:
   ```bash
   # Add to /opt/media/.env
   echo "SLSKD_API_KEY=your_api_key_here" >> /opt/media/.env
   ```

5. **Start the service**:
   ```bash
   cd /opt/media
   docker-compose up -d spotify-slskd-search
   ```

### Option 3: LXC Container

Best for: Dedicated container, no Docker

1. **Create LXC container**:
   - OS: Ubuntu 22.04 or Debian 11
   - RAM: 512MB minimum, 1GB recommended
   - Disk: 5GB
   - Network: Bridge to same network as Slskd (192.168.1.x)

2. **Install dependencies**:
   ```bash
   apt update
   apt install -y python3 python3-pip git
   ```

3. **Clone and setup**:
   ```bash
   cd /opt
   git clone <repository-url> spotify-slskd-search
   cd spotify-slskd-search
   pip3 install -r requirements.txt
   ```

4. **Configure**:
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   nano .env
   ```

5. **Create systemd service**:

   Create `/etc/systemd/system/spotify-slskd-search.service`:

   ```ini
   [Unit]
   Description=Spotify to Slskd Search Aggregator
   After=network.target

   [Service]
   Type=simple
   User=root
   WorkingDirectory=/opt/spotify-slskd-search
   Environment="PATH=/usr/bin"
   EnvironmentFile=/opt/spotify-slskd-search/.env
   ExecStart=/usr/bin/python3 /opt/spotify-slskd-search/app.py
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   ```

6. **Enable and start**:
   ```bash
   systemctl daemon-reload
   systemctl enable spotify-slskd-search
   systemctl start spotify-slskd-search
   ```

7. **Check status**:
   ```bash
   systemctl status spotify-slskd-search
   journalctl -u spotify-slskd-search -f
   ```

---

## Usage Guide

### 1. Prepare Your Spotify Export

#### Option A: Spotify CSV Export

1. Use a tool like [Exportify](https://exportify.net/) to export your playlists
2. Or use Spotify's data download feature
3. Ensure the CSV has columns: `Artist`, `Track`, `Album`

#### Option B: Manual Artist List

Create a simple text file with one artist per line:

```
Ado
Dazbee
NiziU
Polyphia
Chon
```

Then format it as CSV:

```csv
Artist
Ado
Dazbee
NiziU
Polyphia
Chon
```

### 2. Upload and Search

1. **Access the web interface**: `http://192.168.1.124:5070`

2. **Upload CSV**:
   - Click the upload area or drag & drop your CSV file
   - Review the summary (total artists, new vs. already searched)

3. **Start Search**:
   - Click "Start Search" button
   - Monitor progress with the progress bar
   - Search runs in background—you can navigate away

4. **Wait for Completion**:
   - The interface will show progress
   - You'll see a notification when complete

### 3. Browse Results

1. **Dashboard View**:
   - See statistics (total artists, results, reviewed count)
   - View all searched artists in a table
   - Filter by review status (All, Reviewed, Not Reviewed)
   - Sort by name, results count, or date

2. **Artist Detail View**:
   - Click on any artist to see their results
   - Use quality filters (FLAC only, 320kbps+)
   - Sort by size or quality
   - Search within filenames

3. **Download Files**:
   - Click "Open in Slskd" next to any file
   - This opens your Slskd interface in a new tab
   - Manually download the file from Slskd

4. **Track Progress**:
   - Mark artists as "Reviewed" after checking them
   - This helps you track what you've already browsed

### 4. Re-search Artists

If you want to refresh results for an artist:

1. Go to the artist detail page
2. Click "Re-search" button
3. Confirm the deletion
4. Upload CSV again or manually trigger search

### 5. Export Results

- **CSV Export**: Click "Export CSV" in the navigation to download all results
- **Backup**: Click "Backup" to download the raw JSON file

---

## API Endpoints

The application provides a REST API:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Main dashboard |
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

---

## Troubleshooting

### Cannot Connect to Slskd

**Symptoms**: Health check fails, searches return no results

**Solutions**:
1. Verify Slskd is running: `curl http://192.168.1.124:5030`
2. Check API key is correct in `.env`
3. Verify network connectivity from container to Slskd
4. Check Slskd logs for API errors
5. Ensure Slskd API is enabled in settings

### Port Already in Use

**Symptoms**: Container fails to start with port conflict

**Solutions**:
1. Change port in `docker-compose.yml`:
   ```yaml
   ports:
     - "5071:5000"  # Change 5070 to any available port
   ```
2. Restart: `docker-compose up -d`

### No Results for Searches

**Symptoms**: All searches return 0 results

**Solutions**:
1. Check Slskd is connected to the Soulseek network
2. Verify search timeout isn't too short (increase in `.env`)
3. Check Slskd search functionality directly
4. Review application logs: `docker logs spotify-slskd-search`

### Container Keeps Restarting

**Symptoms**: Container status shows constant restarts

**Solutions**:
1. Check logs: `docker logs spotify-slskd-search`
2. Verify `.env` file exists and is properly formatted
3. Ensure `SLSKD_API_KEY` is set
4. Check file permissions on data directory
5. Verify Python dependencies installed correctly

### Upload Fails

**Symptoms**: CSV upload returns error

**Solutions**:
1. Verify file is valid CSV format
2. Check file size (max 50MB)
3. Ensure file has `Artist` column
4. Try with a smaller test CSV first
5. Check container logs for detailed error

### Search Hangs or Crashes

**Symptoms**: Search starts but never completes

**Solutions**:
1. Reduce `SEARCH_DELAY` if too many artists
2. Check Slskd API rate limits
3. Monitor memory usage: `docker stats spotify-slskd-search`
4. Cancel and restart search
5. Search smaller batches of artists

### Permission Errors

**Symptoms**: Cannot write to data directory

**Solutions**:
1. Fix volume permissions:
   ```bash
   sudo chown -R 1000:1000 ./data
   ```
2. Restart container: `docker-compose restart`

### Dark Mode Not Working

**Symptoms**: Theme doesn't persist

**Solutions**:
1. Clear browser cache
2. Check browser localStorage is enabled
3. Try different browser

---

## Data Structure

### Search Results JSON Format

```json
{
  "last_updated": "2025-11-19T10:30:00",
  "artists": {
    "Ado": {
      "searched_at": "2025-11-19T10:25:00",
      "result_count": 42,
      "reviewed": false,
      "search_id": "abc123",
      "results": [
        {
          "username": "musiclover42",
          "filename": "Ado - うっせぇわ (Usseewa).flac",
          "size": 35651584,
          "bitrate": 0,
          "extension": "flac"
        },
        {
          "username": "jpopfan",
          "filename": "Ado - 踊 (Odo).mp3",
          "size": 8421376,
          "bitrate": 320,
          "extension": "mp3"
        }
      ]
    }
  }
}
```

---

## Development

### Local Development Setup

1. **Clone repository**:
   ```bash
   git clone <repository-url>
   cd slskd-spotify-self-host
   ```

2. **Create virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or
   venv\Scripts\activate  # Windows
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

5. **Run development server**:
   ```bash
   export FLASK_ENV=development
   python app.py
   ```

6. **Access**: `http://localhost:5000`

### Project Structure

```
slskd-spotify-self-host/
├── app.py                          # Main Flask application
├── templates/
│   ├── base.html                   # Base template
│   ├── index.html                  # Dashboard page
│   └── artist.html                 # Artist detail page
├── static/                         # Static files (if needed)
├── data/                           # Data directory (created at runtime)
│   ├── search_results.json         # Search results storage
│   ├── uploads/                    # Uploaded CSV files
│   └── application.log             # Application logs
├── requirements.txt                # Python dependencies
├── Dockerfile                      # Docker image definition
├── docker-compose.yml              # Docker Compose config
├── docker-compose.mediaapps.yml    # Media stack integration config
├── .env.example                    # Environment variables template
├── .dockerignore                   # Docker build exclusions
└── README.md                       # This file
```

### Technology Stack

- **Backend**: Python 3.9, Flask 3.0
- **Slskd Integration**: slskd-api 0.3.0
- **Frontend**: HTML5, Tailwind CSS 3.x (CDN), Vanilla JavaScript
- **Storage**: JSON file-based
- **Deployment**: Docker, Docker Compose

---

## Security Considerations

- ✅ Non-root user in Docker container
- ✅ API key via environment variables (not hardcoded)
- ✅ Input validation and sanitization
- ✅ No auto-download functionality (manual review required)
- ✅ CSRF protection on state-changing operations
- ✅ Secure headers on HTTP responses
- ✅ No sensitive data in logs
- ⚠️ Designed for internal network use (add reverse proxy with auth for external access)

---

## Performance Tips

1. **Large CSV files**: Consider splitting into batches
2. **Many artists**: Increase `SEARCH_DELAY` to avoid rate limiting
3. **Slow searches**: Increase `SEARCH_TIMEOUT` for better results
4. **Memory usage**: Monitor with `docker stats`, increase limits if needed
5. **Network latency**: Ensure good connection between container and Slskd

---

## Backup and Recovery

### Backup Data

```bash
# Copy the entire data directory
cp -r ./data ./data-backup-$(date +%Y%m%d)

# Or download via web interface
curl -O http://192.168.1.124:5070/backup/download
```

### Restore Data

```bash
# Stop container
docker-compose down

# Restore data directory
cp -r ./data-backup-20251119 ./data

# Restart container
docker-compose up -d
```

---

## Updating

### Update to Latest Version

```bash
# Pull latest code
git pull origin main

# Rebuild container
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

Your data in `./data` will persist across updates.

---

## FAQ

**Q: Does this automatically download music?**
A: No! This tool only aggregates search results. You manually review and download in Slskd.

**Q: Can I use this with multiple Slskd instances?**
A: Currently supports one instance, but you can run multiple containers with different configs.

**Q: What Spotify export formats are supported?**
A: CSV files with at least an "Artist" column. Works with Exportify and Spotify data downloads.

**Q: Can I search for specific albums or tracks?**
A: Currently only searches by artist name. Track/album search coming in future versions.

**Q: How long do searches take?**
A: Depends on number of artists and `SEARCH_DELAY`. Roughly 3-5 seconds per artist.

**Q: Can I cancel a search in progress?**
A: Yes, click the "Cancel Search" button in the progress section.

**Q: Are results updated automatically?**
A: No, you need to delete and re-search artists to refresh results.

**Q: Can I access this from outside my network?**
A: Yes, but add authentication (reverse proxy with basic auth recommended).

**Q: Does this work with VPN?**
A: Yes, as long as the container can reach Slskd on your network.

---

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

---

## License

MIT License - see LICENSE file for details

---

## Credits

- Built with [Flask](https://flask.palletsprojects.com/)
- Uses [slskd-api](https://pypi.org/project/slskd-api/) for Slskd integration
- UI styled with [Tailwind CSS](https://tailwindcss.com/)
- Designed for [Slskd](https://github.com/slskd/slskd)

---

## Support

For issues, questions, or feature requests:
- Open an issue on GitHub
- Check the troubleshooting section above
- Review application logs for detailed errors

---

## Version History

### v1.0.0 (2025-11-19)
- Initial release
- CSV upload and parsing
- Background search functionality
- Web UI with filtering and sorting
- Docker and LXC deployment options
- Dark mode support
- Export and backup features

---

**Made with ❤️ for manual music discovery**
