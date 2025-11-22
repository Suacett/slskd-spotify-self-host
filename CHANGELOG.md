# Changelog

All notable changes to the Spotify to Slskd Search Aggregator project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-11-19

### Added
- Initial release of Spotify to Slskd Search Aggregator
- CSV upload functionality for Spotify playlist exports
- Automatic artist extraction and deduplication from CSV files
- Background search process using slskd-api library
- Progressive result saving to prevent data loss
- Web UI with modern dark mode interface using Tailwind CSS
- Statistics dashboard showing total artists, results count, and review status
- Artist detail pages with comprehensive result listings
- Advanced filtering options:
  - Filter by audio quality (FLAC, 320kbps+)
  - Filter by file size
  - Search within filenames
- Sorting capabilities:
  - Sort by size (largest/smallest first)
  - Sort by quality (highest bitrate first)
  - Sort by filename alphabetically
- Review tracking system to mark artists as reviewed
- Re-search functionality to refresh artist results
- Export features:
  - CSV export of all results
  - JSON backup download
- Health check endpoint for monitoring
- Docker deployment with multi-stage build
- Docker Compose configuration for standalone deployment
- Alternative Docker Compose config for media stack integration
- LXC deployment option with systemd service
- Comprehensive error handling and logging
- API key authentication with environment variable support
- Secure non-root Docker user implementation
- Drag-and-drop file upload support
- Real-time progress tracking for searches
- Background task processing with threading
- Automatic skip of already-searched artists
- Unicode support for international artist names
- Mobile-responsive UI design
- Dark/light mode toggle with localStorage persistence

### Security
- Non-root user in Docker container
- API key via environment variables (not hardcoded)
- Input validation and sanitization
- No auto-download functionality (manual review required)
- Secure file upload handling
- Path traversal protection
- XSS prevention in templates

### Documentation
- Comprehensive README.md with:
  - Quick start guide
  - Detailed deployment instructions for Docker, Docker Compose, and LXC
  - Configuration reference
  - Usage guide with screenshots
  - API endpoint documentation
  - Troubleshooting section
  - FAQ section
- Inline code documentation and comments
- Example configuration files (.env.example)
- Docker deployment examples

## [Unreleased]

### Planned Features
- Album and track-specific search support
- Multiple Slskd instance support
- Automatic result refresh scheduling
- Email notifications on search completion
- Integration with other music services (Apple Music, Last.fm)
- Duplicate detection across search results
- Batch delete functionality
- Advanced search filters (file format, minimum/maximum size)
- User authentication for multi-user support
- Search history and analytics
- Customizable search parameters per artist
- Import/export of entire search databases
- REST API for programmatic access
- Webhook support for automation
- Integration with music download managers

### Known Issues
- None reported in v1.0.0

---

## Version History Summary

- **v1.0.0** (2025-11-19): Initial release with core functionality
