#!/usr/bin/env python3
"""
Spotify to Slskd Search Aggregator with Smart Quality Scoring
A Flask application that searches Slskd for artists from Spotify playlists
and provides intelligent filtering to show only the best quality results.
"""

import os
import csv
import json
import time
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from io import StringIO

from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file
from werkzeug.utils import secure_filename
from slskd_api import SlskdClient
from slskd_api.exceptions import SlskdException

# Configuration file path
CONFIG_FILE = Path(os.getenv('DATA_DIR', '/app/data')) / 'config.json'

# Default configuration
DEFAULT_CONFIG = {
    'SLSKD_URL': os.getenv('SLSKD_URL', 'http://192.168.1.124:5030'),
    'SLSKD_API_KEY': os.getenv('SLSKD_API_KEY', ''),
    'SLSKD_USERNAME': os.getenv('SLSKD_USERNAME', ''),
    'SLSKD_PASSWORD': os.getenv('SLSKD_PASSWORD', ''),
    'SLSKD_URL_BASE': os.getenv('SLSKD_URL_BASE', '/'),
    'SEARCH_TIMEOUT': int(os.getenv('SEARCH_TIMEOUT', '15')),
    'SEARCH_DELAY': int(os.getenv('SEARCH_DELAY', '3')),
    'DATA_DIR': os.getenv('DATA_DIR', '/app/data'),
    # Smart Quality Settings
    'MIN_BITRATE': 192,
    'MAX_QUEUE_LENGTH': 50,
    'MIN_SPEED_KBS': 50,
    'TOP_RESULTS_COUNT': 5,
}

# Load configuration from file or environment
def load_config():
    """Load configuration from file or use defaults"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                saved_config = json.load(f)
                # Merge with defaults
                config = DEFAULT_CONFIG.copy()
                config.update(saved_config)
                return config
        except Exception as e:
            logging.error(f"Error loading config: {e}")
    return DEFAULT_CONFIG.copy()

def save_config(config):
    """Save configuration to file"""
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        logging.error(f"Error saving config: {e}")
        return False

CONFIG = load_config()

# Initialize Flask app
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max upload
app.config['UPLOAD_FOLDER'] = Path(CONFIG['DATA_DIR']) / 'uploads'
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# Setup logging
log_dir = Path(CONFIG['DATA_DIR'])
log_dir.mkdir(parents=True, exist_ok=True)
app.config['UPLOAD_FOLDER'].mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'application.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Global search state
search_state = {
    'active': False,
    'progress': 0,
    'total': 0,
    'current_artist': '',
    'errors': [],
    'completed': False,
}

# Results file path
RESULTS_FILE = Path(CONFIG['DATA_DIR']) / 'search_results.json'


def calculate_quality_score(file_info: Dict) -> float:
    """
    Calculate quality score for a file based on:
    - Bitrate/Format (higher is better)
    - Upload Speed (faster is better)
    - Queue Length (shorter is better)

    Returns a score where higher is better.
    """
    score = 0.0

    # Bitrate scoring (0-100 points)
    bitrate = file_info.get('bitrate', 0)
    extension = file_info.get('extension', '').lower()

    if extension in ['flac', 'wav', 'alac', 'ape']:
        score += 100  # Lossless formats get maximum points
    elif bitrate >= 320:
        score += 90
    elif bitrate >= 256:
        score += 70
    elif bitrate >= 192:
        score += 50
    else:
        score += 20

    # Speed scoring (0-50 points)
    speed_kbs = file_info.get('speed_kbs', 0)
    if speed_kbs >= 2000:  # 2 MB/s
        score += 50
    elif speed_kbs >= 1000:  # 1 MB/s
        score += 40
    elif speed_kbs >= 500:
        score += 30
    elif speed_kbs >= 100:
        score += 20
    elif speed_kbs >= 50:
        score += 10

    # Queue penalty (subtract up to 100 points)
    queue_length = file_info.get('queue_length', 0)
    if queue_length == 0:
        score += 50  # Bonus for instant availability
    elif queue_length <= 5:
        score -= 10
    elif queue_length <= 10:
        score -= 30
    elif queue_length <= 25:
        score -= 50
    else:
        score -= 100  # Heavy penalty for long queues

    # Free slot bonus
    if file_info.get('has_free_slot', False):
        score += 25

    return score


def passes_quality_filters(file_info: Dict) -> bool:
    """
    Apply strict quality filters to determine if a file should be shown.

    Filters:
    - Bitrate must be >= MIN_BITRATE (unless lossless)
    - Queue length must be <= MAX_QUEUE_LENGTH
    - Speed must be >= MIN_SPEED_KBS
    - File must not be locked
    """
    extension = file_info.get('extension', '').lower()
    bitrate = file_info.get('bitrate', 0)
    queue_length = file_info.get('queue_length', 0)
    speed_kbs = file_info.get('speed_kbs', 0)
    is_locked = file_info.get('is_locked', False)

    # Locked files are always rejected
    if is_locked:
        return False

    # Queue too long
    if queue_length > CONFIG['MAX_QUEUE_LENGTH']:
        return False

    # Speed too slow
    if speed_kbs < CONFIG['MIN_SPEED_KBS']:
        return False

    # Bitrate check (lossless formats bypass this)
    if extension not in ['flac', 'wav', 'alac', 'ape']:
        if bitrate < CONFIG['MIN_BITRATE']:
            return False

    return True


def rank_and_filter_results(results: List[Dict]) -> List[Dict]:
    """
    Filter results based on quality criteria and return top N ranked results.

    Returns:
        List of top quality results, ranked by score
    """
    # First, filter out low-quality results
    filtered_results = []
    for result in results:
        if passes_quality_filters(result):
            # Calculate quality score
            result['quality_score'] = calculate_quality_score(result)
            filtered_results.append(result)

    # Sort by quality score (descending)
    filtered_results.sort(key=lambda x: x['quality_score'], reverse=True)

    # Return top N results
    top_count = CONFIG.get('TOP_RESULTS_COUNT', 5)
    return filtered_results[:top_count]


class SearchManager:
    """Manages search operations and result storage"""

    def __init__(self):
        self.results = self._load_results()
        self.lock = threading.Lock()

    def _load_results(self) -> Dict:
        """Load existing search results from JSON file"""
        if RESULTS_FILE.exists():
            try:
                with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading results file: {e}")
                return self._create_empty_results()
        return self._create_empty_results()

    def _create_empty_results(self) -> Dict:
        """Create empty results structure"""
        return {
            'last_updated': None,
            'artists': {}
        }

    def save_results(self):
        """Save results to JSON file"""
        with self.lock:
            self.results['last_updated'] = datetime.now().isoformat()
            try:
                with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(self.results, f, indent=2, ensure_ascii=False)
                logger.info("Results saved successfully")
            except Exception as e:
                logger.error(f"Error saving results: {e}")

    def get_artist_results(self, artist_name: str) -> Optional[Dict]:
        """Get results for a specific artist"""
        return self.results['artists'].get(artist_name)

    def mark_reviewed(self, artist_name: str) -> bool:
        """Mark an artist as reviewed"""
        if artist_name in self.results['artists']:
            self.results['artists'][artist_name]['reviewed'] = True
            self.save_results()
            return True
        return False

    def delete_artist(self, artist_name: str) -> bool:
        """Delete an artist's results"""
        if artist_name in self.results['artists']:
            del self.results['artists'][artist_name]
            self.save_results()
            return True
        return False

    def add_artist_results(self, artist_name: str, results: List[Dict], search_id: str = ""):
        """Add or update results for an artist"""
        with self.lock:
            self.results['artists'][artist_name] = {
                'searched_at': datetime.now().isoformat(),
                'result_count': len(results),
                'reviewed': False,
                'search_id': search_id,
                'results': results
            }
            self.save_results()

    def get_stats(self) -> Dict:
        """Calculate statistics"""
        total_artists = len(self.results['artists'])
        artists_with_results = sum(1 for a in self.results['artists'].values() if a['result_count'] > 0)
        reviewed_artists = sum(1 for a in self.results['artists'].values() if a.get('reviewed', False))
        total_files = sum(a['result_count'] for a in self.results['artists'].values())

        return {
            'total_artists': total_artists,
            'artists_with_results': artists_with_results,
            'reviewed_artists': reviewed_artists,
            'total_files': total_files,
            'last_updated': self.results.get('last_updated')
        }


# Initialize search manager
search_manager = SearchManager()


def parse_spotify_csv(file_path: Path) -> List[str]:
    """Parse Spotify CSV and extract unique artist names"""
    artists = set()

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Try to detect CSV format
        sniffer = csv.Sniffer()
        try:
            dialect = sniffer.sniff(content[:1024])
            has_header = sniffer.has_header(content[:1024])
        except:
            dialect = 'excel'
            has_header = True

        # Parse CSV
        reader = csv.DictReader(StringIO(content), dialect=dialect)

        for row in reader:
            # Try different common column names for artists
            artist = None
            for col_name in ['Artist', 'artist', 'Artist Name', 'ARTIST']:
                if col_name in row and row[col_name]:
                    artist = row[col_name].strip()
                    break

            if artist:
                artists.add(artist)

        logger.info(f"Parsed {len(artists)} unique artists from CSV")
        return sorted(list(artists))

    except Exception as e:
        logger.error(f"Error parsing CSV: {e}")
        raise


def search_artist_on_slskd(client: SlskdClient, artist_name: str) -> Tuple[List[Dict], str]:
    """
    Search for an artist on Slskd and return results with quality scoring

    Returns:
        Tuple of (top quality results list, search_id)
    """
    try:
        logger.info(f"Searching for artist: {artist_name}")

        # Perform search with timeout
        search_response = client.searches.search_text(
            search_text=artist_name,
            timeout=CONFIG['SEARCH_TIMEOUT']
        )

        # Wait a bit for results to accumulate
        time.sleep(5)

        # Get search results
        search_id = search_response.get('id', '')

        # Fetch the actual results
        try:
            results_response = client.searches.search_by_id(search_id)
            files = results_response.get('files', [])
        except:
            files = []

        # Parse and format results
        all_results = []
        for file_info in files:
            try:
                # Extract file information
                filename = file_info.get('filename', '')
                size = file_info.get('size', 0)
                username = file_info.get('username', 'Unknown')

                # Quality metrics
                extension = Path(filename).suffix.lower().replace('.', '')
                bitrate = file_info.get('bitRate', 0)
                queue_length = file_info.get('queueLength', 0)
                upload_speed = file_info.get('uploadSpeed', 0)  # in bytes/sec
                speed_kbs = upload_speed / 1024 if upload_speed else 0
                has_free_slot = file_info.get('hasFreeUploadSlot', False)
                is_locked = file_info.get('isLocked', False)

                all_results.append({
                    'username': username,
                    'filename': filename,
                    'size': size,
                    'bitrate': bitrate,
                    'extension': extension,
                    'queue_length': queue_length,
                    'speed_kbs': speed_kbs,
                    'has_free_slot': has_free_slot,
                    'is_locked': is_locked,
                })
            except Exception as e:
                logger.warning(f"Error parsing file info: {e}")
                continue

        # Apply smart quality filtering and ranking
        top_results = rank_and_filter_results(all_results)

        logger.info(f"Found {len(all_results)} total results, filtered to top {len(top_results)} for {artist_name}")
        return top_results, search_id

    except SlskdException as e:
        logger.error(f"Slskd API error searching for {artist_name}: {e}")
        return [], ""
    except Exception as e:
        logger.error(f"Unexpected error searching for {artist_name}: {e}")
        return [], ""


def background_search_task(artists: List[str]):
    """Background task to search for artists"""
    global search_state

    logger.info(f"Starting background search for {len(artists)} artists")

    # Initialize search state
    search_state['active'] = True
    search_state['progress'] = 0
    search_state['total'] = len(artists)
    search_state['errors'] = []
    search_state['completed'] = False

    # Initialize Slskd client
    try:
        client = SlskdClient(
            host=CONFIG['SLSKD_URL'],
            api_key=CONFIG['SLSKD_API_KEY'],
            url_base=CONFIG['SLSKD_URL_BASE']
        )
        logger.info("Slskd client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Slskd client: {e}")
        search_state['errors'].append(f"Failed to connect to Slskd: {e}")
        search_state['active'] = False
        search_state['completed'] = True
        return

    # Search each artist
    for i, artist in enumerate(artists):
        if not search_state['active']:
            logger.info("Search cancelled by user")
            break

        search_state['current_artist'] = artist
        search_state['progress'] = i

        # Skip if already searched
        if search_manager.get_artist_results(artist):
            logger.info(f"Skipping already searched artist: {artist}")
            continue

        # Search with retries
        max_retries = 3
        for attempt in range(max_retries):
            try:
                results, search_id = search_artist_on_slskd(client, artist)
                search_manager.add_artist_results(artist, results, search_id)

                if len(results) == 0:
                    search_state['errors'].append(f"No quality results found for: {artist}")

                break  # Success
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(f"Retry {attempt + 1}/{max_retries} for {artist} after {wait_time}s")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed to search {artist} after {max_retries} attempts: {e}")
                    search_state['errors'].append(f"Failed to search {artist}: {e}")

        # Delay between searches
        if i < len(artists) - 1:
            time.sleep(CONFIG['SEARCH_DELAY'])

    # Mark as completed
    search_state['progress'] = search_state['total']
    search_state['active'] = False
    search_state['completed'] = True
    logger.info("Background search completed")


# Flask Routes

@app.route('/')
def index():
    """Main dashboard page"""
    # Check if configuration is needed
    if not CONFIG.get('SLSKD_API_KEY'):
        return redirect(url_for('settings'))

    stats = search_manager.get_stats()

    # Get all artists with their info
    artists = []
    for name, data in search_manager.results['artists'].items():
        artists.append({
            'name': name,
            'result_count': data['result_count'],
            'searched_at': data['searched_at'],
            'reviewed': data.get('reviewed', False)
        })

    # Sort by search date (newest first)
    artists.sort(key=lambda x: x['searched_at'], reverse=True)

    return render_template('index.html', stats=stats, artists=artists, search_state=search_state)


@app.route('/settings', methods=['GET', 'POST'])
def settings():
    """Configuration settings page"""
    if request.method == 'POST':
        # Update configuration
        new_config = CONFIG.copy()
        new_config['SLSKD_URL'] = request.form.get('slskd_url', CONFIG['SLSKD_URL'])
        new_config['SLSKD_API_KEY'] = request.form.get('slskd_api_key', CONFIG['SLSKD_API_KEY'])
        new_config['SLSKD_USERNAME'] = request.form.get('slskd_username', '')
        new_config['SLSKD_PASSWORD'] = request.form.get('slskd_password', '')
        new_config['SLSKD_URL_BASE'] = request.form.get('slskd_url_base', CONFIG['SLSKD_URL_BASE'])

        # Parse numeric values
        try:
            new_config['SEARCH_TIMEOUT'] = int(request.form.get('search_timeout', CONFIG['SEARCH_TIMEOUT']))
            new_config['SEARCH_DELAY'] = int(request.form.get('search_delay', CONFIG['SEARCH_DELAY']))
            new_config['MIN_BITRATE'] = int(request.form.get('min_bitrate', CONFIG['MIN_BITRATE']))
            new_config['MAX_QUEUE_LENGTH'] = int(request.form.get('max_queue_length', CONFIG['MAX_QUEUE_LENGTH']))
            new_config['MIN_SPEED_KBS'] = int(request.form.get('min_speed_kbs', CONFIG['MIN_SPEED_KBS']))
            new_config['TOP_RESULTS_COUNT'] = int(request.form.get('top_results_count', CONFIG['TOP_RESULTS_COUNT']))
        except ValueError:
            return jsonify({'error': 'Invalid numeric value'}), 400

        # Save configuration
        if save_config(new_config):
            CONFIG.update(new_config)
            return jsonify({'success': True, 'message': 'Configuration saved successfully'})
        else:
            return jsonify({'error': 'Failed to save configuration'}), 500

    return render_template('settings.html', config=CONFIG)


@app.route('/artist/<artist_name>')
def artist_detail(artist_name: str):
    """Artist detail page showing top quality search results"""
    artist_data = search_manager.get_artist_results(artist_name)

    if not artist_data:
        return "Artist not found", 404

    return render_template(
        'artist.html',
        artist_name=artist_name,
        artist_data=artist_data,
        slskd_url=CONFIG['SLSKD_URL']
    )


@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle CSV file upload"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        if not file.filename.lower().endswith('.csv'):
            return jsonify({'error': 'Only CSV files are allowed'}), 400

        # Save file
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        saved_filename = f"{timestamp}_{filename}"
        file_path = app.config['UPLOAD_FOLDER'] / saved_filename
        file.save(file_path)

        # Parse artists
        artists = parse_spotify_csv(file_path)

        # Check which are new
        new_artists = [a for a in artists if not search_manager.get_artist_results(a)]
        existing_artists = [a for a in artists if search_manager.get_artist_results(a)]

        return jsonify({
            'success': True,
            'filename': saved_filename,
            'total_artists': len(artists),
            'new_artists': len(new_artists),
            'existing_artists': len(existing_artists),
            'artists': artists,
            'new_artists_list': new_artists
        })

    except Exception as e:
        logger.error(f"Upload error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/search/start', methods=['POST'])
def start_search():
    """Start background search process"""
    global search_state

    if search_state['active']:
        return jsonify({'error': 'Search already in progress'}), 400

    try:
        data = request.get_json()
        artists = data.get('artists', [])

        if not artists:
            return jsonify({'error': 'No artists provided'}), 400

        # Filter out already searched artists unless force is specified
        force = data.get('force', False)
        if not force:
            artists = [a for a in artists if not search_manager.get_artist_results(a)]

        if not artists:
            return jsonify({'message': 'All artists already searched', 'count': 0}), 200

        # Start background thread
        thread = threading.Thread(target=background_search_task, args=(artists,))
        thread.daemon = True
        thread.start()

        return jsonify({
            'success': True,
            'message': f'Started search for {len(artists)} artists',
            'count': len(artists)
        })

    except Exception as e:
        logger.error(f"Error starting search: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/search/status')
def search_status():
    """Get current search status"""
    return jsonify(search_state)


@app.route('/search/cancel', methods=['POST'])
def cancel_search():
    """Cancel ongoing search"""
    global search_state
    search_state['active'] = False
    return jsonify({'success': True})


@app.route('/api/mark_reviewed/<artist_name>', methods=['POST'])
def mark_reviewed(artist_name: str):
    """Mark an artist as reviewed"""
    success = search_manager.mark_reviewed(artist_name)
    if success:
        return jsonify({'success': True})
    return jsonify({'error': 'Artist not found'}), 404


@app.route('/api/stats')
def get_stats():
    """Get statistics"""
    return jsonify(search_manager.get_stats())


@app.route('/artist/<artist_name>/delete', methods=['POST'])
def delete_artist(artist_name: str):
    """Delete an artist to allow re-searching"""
    success = search_manager.delete_artist(artist_name)
    if success:
        return jsonify({'success': True})
    return jsonify({'error': 'Artist not found'}), 404


@app.route('/export/csv')
def export_csv():
    """Export all results to CSV"""
    try:
        output = StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow(['Artist', 'Username', 'Filename', 'Size (MB)', 'Bitrate', 'Extension',
                        'Queue', 'Speed (KB/s)', 'Quality Score', 'Reviewed'])

        # Write data
        for artist_name, artist_data in search_manager.results['artists'].items():
            reviewed = 'Yes' if artist_data.get('reviewed', False) else 'No'
            for result in artist_data['results']:
                writer.writerow([
                    artist_name,
                    result['username'],
                    result['filename'],
                    round(result['size'] / (1024 * 1024), 2),  # Convert to MB
                    result['bitrate'],
                    result['extension'],
                    result.get('queue_length', 'N/A'),
                    round(result.get('speed_kbs', 0), 2),
                    round(result.get('quality_score', 0), 2),
                    reviewed
                ])

        # Create response
        output.seek(0)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'slskd_search_results_{timestamp}.csv'

        return send_file(
            StringIO(output.getvalue()),
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        logger.error(f"Export error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/backup/download')
def download_backup():
    """Download the search_results.json file"""
    if RESULTS_FILE.exists():
        return send_file(RESULTS_FILE, as_attachment=True, download_name='search_results_backup.json')
    return jsonify({'error': 'No results file found'}), 404


@app.route('/health')
def health_check():
    """Health check endpoint"""
    try:
        # Test Slskd connection if configured
        if CONFIG.get('SLSKD_API_KEY'):
            client = SlskdClient(
                host=CONFIG['SLSKD_URL'],
                api_key=CONFIG['SLSKD_API_KEY'],
                url_base=CONFIG['SLSKD_URL_BASE']
            )

            # Try to get server state
            state = client.application.state()

            return jsonify({
                'status': 'healthy',
                'slskd_connected': True,
                'slskd_state': state.get('state', 'unknown'),
                'smart_filtering': True
            })
        else:
            return jsonify({
                'status': 'healthy',
                'slskd_connected': False,
                'configuration_needed': True
            })
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'slskd_connected': False,
            'error': str(e)
        }), 503


if __name__ == '__main__':
    # Log startup info
    logger.info("=" * 50)
    logger.info("Spotify to Slskd Search Aggregator with Smart Quality")
    logger.info("=" * 50)
    logger.info(f"Slskd URL: {CONFIG['SLSKD_URL']}")
    logger.info(f"Data directory: {CONFIG['DATA_DIR']}")
    logger.info(f"Search timeout: {CONFIG['SEARCH_TIMEOUT']}s")
    logger.info(f"Search delay: {CONFIG['SEARCH_DELAY']}s")
    logger.info(f"Min bitrate: {CONFIG['MIN_BITRATE']} kbps")
    logger.info(f"Max queue: {CONFIG['MAX_QUEUE_LENGTH']}")
    logger.info(f"Min speed: {CONFIG['MIN_SPEED_KBS']} KB/s")
    logger.info(f"Top results: {CONFIG['TOP_RESULTS_COUNT']}")
    logger.info("=" * 50)

    if not CONFIG.get('SLSKD_API_KEY'):
        logger.warning("SLSKD_API_KEY not configured! Please configure via web interface.")

    # Run Flask app
    app.run(host='0.0.0.0', port=5000, debug=False)
