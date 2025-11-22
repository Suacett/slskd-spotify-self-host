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
import requests
import difflib
import concurrent.futures
import pykakasi
import random
from urllib.parse import quote

# Import custom modules
from musicbrainz_client import MusicBrainzClient
from isrc_tracker import ISRCTracker

# Configuration file path
CONFIG_FILE = Path(os.getenv('DATA_DIR', '/app/data')) / 'config.json'

# Default configuration
DEFAULT_CONFIG = {
    'SLSKD_URL': os.getenv('SLSKD_URL', 'http://192.168.1.124:5030'),
    'SLSKD_API_KEY': os.getenv('SLSKD_API_KEY', ''),
    'SLSKD_URL_BASE': os.getenv('SLSKD_URL_BASE', '/'),
    'SEARCH_TIMEOUT': int(os.getenv('SEARCH_TIMEOUT', '15')),
    'SEARCH_DELAY': int(os.getenv('SEARCH_DELAY', '2')),  # Reduced from 3 to 2 for faster searches
    'DATA_DIR': os.getenv('DATA_DIR', '/app/data'),
    # Smart Quality Settings
    'MIN_BITRATE': 192,
    'MAX_QUEUE_LENGTH': 50,
    'MIN_SPEED_KBS': 50,
    'TOP_RESULTS_COUNT': 50,  # Increased to allow client-side filtering
    'MAX_FILE_SIZE_MB': 30,  # Maximum file size in MB
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

# Results file path
RESULTS_FILE = Path(CONFIG['DATA_DIR']) / 'search_results.json'
WATCHLIST_FILE = Path(CONFIG['DATA_DIR']) / 'watch_list.json'
QUEUE_FILE = Path(CONFIG['DATA_DIR']) / 'queue.json'
STATE_FILE = Path(CONFIG['DATA_DIR']) / 'state.json'


class QueueManager:
    """Manages the persistent search queue"""
    def __init__(self):
        self.queue = []
        self.lock = threading.RLock()
        self.load_queue()

    def load_queue(self):
        """Load queue from disk"""
        if QUEUE_FILE.exists():
            try:
                with open(QUEUE_FILE, 'r', encoding='utf-8') as f:
                    self.queue = json.load(f)
            except Exception as e:
                logger.error(f"Error loading queue: {e}")
                self.queue = []

    def save_queue(self):
        """Save queue to disk"""
        try:
            with open(QUEUE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.queue, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving queue: {e}")

    def add_items(self, items: List[Dict]):
        """Add items to queue"""
        with self.lock:
            # Avoid duplicates
            current_keys = {f"{i['artist']}-{i['title']}" for i in self.queue}
            new_items = []
            for item in items:
                key = f"{item['artist']}-{item['title']}"
                if key not in current_keys:
                    new_items.append(item)
            
            self.queue.extend(new_items)
            self.save_queue()
            return len(new_items)

    def get_next(self) -> Optional[Dict]:
        """Get next item from queue"""
        with self.lock:
            if self.queue:
                item = self.queue.pop(0)
                self.save_queue()
                return item
            return None

    def clear(self):
        """Clear the queue"""
        with self.lock:
            self.queue = []
            self.save_queue()

    def get_count(self) -> int:
        return len(self.queue)


def save_application_state(state: Dict):
    """Save application state to disk"""
    try:
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving state: {e}")

def load_application_state() -> Dict:
    """Load application state from disk"""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading state: {e}")
    return {
        'active': False,
        'progress': 0,
        'total': 0,
        'current_item': '',
        'errors': [],
        'completed': False,
    }


def calculate_quality_score(file_info: Dict, requested_title: str = "", musicbrainz_metadata: Optional[Dict] = None) -> float:
    """
    Calculate quality score for a file based on:
    - Fuzzy Name Match (critical)
    - Duration Match (using MusicBrainz data)
    - Album Match (using MusicBrainz data)
    - Bitrate/Format
    - Upload Speed
    - Queue Length
    """
    score = 0.0
    filename = file_info.get('filename', '')

    # 1. Fuzzy Name Match (+100pts)
    if requested_title:
        # Clean up filename for comparison (remove extension, underscores)
        clean_filename = Path(filename).stem.replace('_', ' ').replace('-', ' ').lower()
        clean_title = requested_title.lower()

        # Negative Filtering (Blacklist)
        blacklist = ['instrumental', 'karaoke', 'cover', 'live', 'remix', 'acapella']
        for word in blacklist:
            if word in clean_filename and word not in clean_title:
                score -= 500  # Heavy penalty for unwanted versions

        # Check for exact containment first
        if clean_title in clean_filename:
            score += 50

        # Fuzzy match ratio
        matcher = difflib.SequenceMatcher(None, clean_title, clean_filename)
        ratio = matcher.ratio()
        if ratio > 0.85:  # Stricter threshold
            score += 100
        elif ratio > 0.7:
            score += 50
        elif ratio < 0.4:
            score -= 100  # Irrelevant result

    # NEW: Album Verification (if MusicBrainz data available)
    if musicbrainz_metadata and musicbrainz_metadata.get('album'):
        official_album = musicbrainz_metadata['album'].lower()
        # Check if album name is in the file path (Slskd often returns full path)
        # We don't have full path in file_info usually, just filename. 
        # But sometimes 'directory' or similar field exists. 
        # Assuming filename might contain album or we just skip if not available.
        # Actually, Slskd search results often don't have directory unless we ask for it.
        # Let's check filename for now.
        if official_album in filename.lower():
            score += 30

    # 2. Duration Verification (MusicBrainz)
    if musicbrainz_metadata and musicbrainz_metadata.get('duration_ms'):
        mb_duration_seconds = musicbrainz_metadata['duration_ms'] / 1000.0
        file_duration = file_info.get('duration_seconds')  # This comes from Slskd file length

        if file_duration:
            duration_diff = abs(mb_duration_seconds - file_duration)
            if duration_diff <= 2:
                # Perfect match (within 2 seconds)
                score += 100
                logger.debug(f"[QUALITY] Duration perfect match: {file_duration}s vs {mb_duration_seconds:.1f}s (diff: {duration_diff:.1f}s)")
            elif duration_diff <= 5:
                # Good match (within 5 seconds)
                score += 50
                logger.debug(f"[QUALITY] Duration good match: {file_duration}s vs {mb_duration_seconds:.1f}s (diff: {duration_diff:.1f}s)")
            elif duration_diff <= 10:
                # Acceptable match
                score += 20
                logger.debug(f"[QUALITY] Duration acceptable match: {file_duration}s vs {mb_duration_seconds:.1f}s (diff: {duration_diff:.1f}s)")
            else:
                # Likely wrong version (radio edit, extended, etc.)
                score -= 200
                logger.debug(f"[QUALITY] Duration mismatch penalty: {file_duration}s vs {mb_duration_seconds:.1f}s (diff: {duration_diff:.1f}s)")

    # 3. Album Verification (MusicBrainz)
    if musicbrainz_metadata and musicbrainz_metadata.get('album'):
        mb_album = musicbrainz_metadata['album'].lower()
        # Extract potential album name from file path
        file_path_lower = filename.lower()

        # Fuzzy match album name in file path
        matcher = difflib.SequenceMatcher(None, mb_album, file_path_lower)
        ratio = matcher.ratio()

        if ratio > 0.7:
            score += 75
            logger.debug(f"[QUALITY] Album match bonus: '{mb_album}' found in path (ratio: {ratio:.2f})")
        elif ratio > 0.5:
            score += 30
            logger.debug(f"[QUALITY] Album partial match: '{mb_album}' (ratio: {ratio:.2f})")

    # 4. Bitrate Tiering
    bitrate = file_info.get('bitrate', 0)
    extension = file_info.get('extension', '').lower()

    if extension in ['flac', 'wav', 'alac', 'ape']:
        score += 50
    elif bitrate >= 320:
        score += 40
    elif bitrate >= 192: # V0/V2 roughly falls here
        score += 30
    else:
        score -= 100  # Instant reject for low quality

    # 5. Queue Penalty
    queue_length = file_info.get('queue_length', 0)
    if queue_length == 0:
        score += 50
    elif queue_length <= 3:
        score -= 10
    elif queue_length >= 10:
        score -= 100  # Reject heavy queues

    # 6. Speed scoring (minor factor)
    speed_kbs = file_info.get('speed_kbs', 0)
    if speed_kbs >= 1000:
        score += 20
    elif speed_kbs >= 100:
        score += 10

    return score


def passes_quality_filters(file_info: Dict) -> bool:
    """
    Apply strict quality filters to determine if a file should be shown.

    Filters:
    - Bitrate must be >= MIN_BITRATE (unless lossless)
    - Queue length must be <= MAX_QUEUE_LENGTH
    - Speed must be >= MIN_SPEED_KBS
    - File must not be locked
    - File must not be a video
    - File size must be <= MAX_FILE_SIZE_MB
    """
    extension = file_info.get('extension', '').lower()
    bitrate = file_info.get('bitrate', 0)
    queue_length = file_info.get('queue_length', 0)
    speed_kbs = file_info.get('speed_kbs', 0)
    is_locked = file_info.get('is_locked', False)
    file_size = file_info.get('size', 0)
    filename = file_info.get('filename', '')

    # Reject video files
    video_extensions = ['mkv', 'mp4', 'avi', 'mov', 'wmv', 'flv', 'webm', 'mpg', 'mpeg', 'm4v']
    if extension in video_extensions:
        logger.debug(f"[FILTER] REJECTED: {filename} - Video file (.{extension})")
        return False

    # Reject files over size limit
    max_size_bytes = CONFIG['MAX_FILE_SIZE_MB'] * 1024 * 1024
    if file_size > max_size_bytes:
        size_mb = file_size / (1024 * 1024)
        logger.debug(f"[FILTER] REJECTED: {filename} - Too large ({size_mb:.1f}MB > {CONFIG['MAX_FILE_SIZE_MB']}MB)")
        return False

    # Locked files are always rejected
    if is_locked:
        logger.debug(f"[FILTER] REJECTED: {filename} - Locked")
        return False

    # Queue too long (Soft filter - handled by scoring, but reject extreme cases)
    if queue_length > 1000: # Was CONFIG['MAX_QUEUE_LENGTH']
        logger.debug(f"[FILTER] REJECTED: {filename} - Queue too long ({queue_length})")
        return False

    # Speed too slow (Soft filter)
    # if speed_kbs < CONFIG['MIN_SPEED_KBS']:
    #     logger.debug(f"[FILTER] REJECTED: {filename} - Speed too slow ({speed_kbs} KB/s)")
    #     return False

    # Bitrate check (Soft filter)
    # if extension not in ['flac', 'wav', 'alac', 'ape']:
    #     if bitrate < CONFIG['MIN_BITRATE']:
    #         logger.debug(f"[FILTER] REJECTED: {filename} - Bitrate too low ({bitrate} kbps)")
    #         return False

    logger.debug(f"[FILTER] ACCEPTED: {filename} - {extension}, {bitrate}kbps, Q:{queue_length}, {speed_kbs}KB/s")
    return True


def rank_and_filter_results(results: List[Dict], musicbrainz_metadata: Optional[Dict] = None) -> List[Dict]:
    """
    Filter results based on quality criteria and return top N ranked results.

    Args:
        results: List of search results
        musicbrainz_metadata: Optional MusicBrainz metadata for enhanced scoring

    Returns:
        List of top quality results, ranked by score
    """
    # First, filter out low-quality results
    filtered_results = []
    for result in results:
        if passes_quality_filters(result):
            # Calculate quality score with MusicBrainz data
            result['quality_score'] = calculate_quality_score(
                result,
                result.get('requested_title', ''),
                musicbrainz_metadata
            )
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
        self.lock = threading.RLock()  # Use RLock to allow reentrant locking

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
            'albums': {},  # New structure: Group by Album
            'tracks': {}   # Legacy/Fallback
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

    def get_track_results(self, track_key: str) -> Optional[Dict]:
        """Get results for a specific track"""
        # Support legacy 'artists' key for backward compatibility
        if 'tracks' in self.results:
            return self.results['tracks'].get(track_key)
        elif 'artists' in self.results:
            # Legacy support
            return self.results['artists'].get(track_key)
        return None

    def mark_reviewed(self, track_key: str) -> bool:
        """Mark a track as reviewed"""
        tracks = self.results.get('tracks', {})
        if track_key in tracks:
            tracks[track_key]['reviewed'] = True
            self.save_results()
            return True
        return False

    def delete_track(self, track_key: str) -> bool:
        """Delete a track's results"""
        tracks = self.results.get('tracks', {})
        if track_key in tracks:
            del tracks[track_key]
            self.save_results()
            return True
        return False

    def get_stats(self) -> Dict:
        """Calculate statistics"""
        # Count tracks from both new 'albums' structure and legacy 'tracks'
        total_tracks = 0
        tracks_with_results = 0
        reviewed_tracks = 0
        total_files = 0

        # Count from Albums
        albums = self.results.get('albums', {})
        for album in albums.values():
            for track in album.get('tracks', []):
                total_tracks += 1
                if track.get('result_count', 0) > 0:
                    tracks_with_results += 1
                if track.get('reviewed', False):
                    reviewed_tracks += 1
                total_files += track.get('result_count', 0)

        # Count from Legacy Tracks (if any)
        tracks = self.results.get('tracks', {})
        for track in tracks.values():
            total_tracks += 1
            if track.get('result_count', 0) > 0:
                tracks_with_results += 1
            if track.get('reviewed', False):
                reviewed_tracks += 1
            total_files += track.get('result_count', 0)

        return {
            'total_tracks': total_tracks,
            'tracks_with_results': tracks_with_results,
            'reviewed_tracks': reviewed_tracks,
            'total_files': total_files,
            'last_updated': self.results.get('last_updated')
        }

    def add_track_results(self, track_key: str, artist: str, title: str, album: str, results: List[Dict],
                         search_id: str = "", musicbrainz_metadata: Optional[Dict] = None):
        """Add or update results for a track, organized by Album"""
        with self.lock:
            # Normalize album name
            album_name = album if album else "Unknown Album"
            album_key = f"{artist} - {album_name}"

            if 'albums' not in self.results:
                self.results['albums'] = {}

            if album_key not in self.results['albums']:
                self.results['albums'][album_key] = {
                    'name': album_name,
                    'artist': artist,
                    'tracks': []
                }

            # Find if track already exists in this album
            album_data = self.results['albums'][album_key]
            existing_track = None
            for t in album_data['tracks']:
                if t['title'] == title:
                    existing_track = t
                    break
            
            track_data = {
                'artist': artist,
                'title': title,
                'album': album_name,
                'searched_at': datetime.now().isoformat(),
                'result_count': len(results),
                'reviewed': False,
                'search_id': search_id,
                'results': results,
                'key': track_key # Store key for easy lookup
            }

            if musicbrainz_metadata:
                track_data['musicbrainz'] = musicbrainz_metadata

            if existing_track:
                # Update existing
                existing_track.update(track_data)
            else:
                # Add new
                album_data['tracks'].append(track_data)

            self.save_results()

    def get_all_tracks_flat(self) -> List[Dict]:
        """Get all tracks as a flat list for display"""
        all_tracks = []
        
        # Get from Albums
        albums = self.results.get('albums', {})
        for album in albums.values():
            all_tracks.extend(album.get('tracks', []))
            
        # Get from Legacy
        tracks = self.results.get('tracks', {})
        all_tracks.extend(tracks.values())
        
        return all_tracks

    def get_track_by_key(self, key: str) -> Optional[Dict]:
        """Find a track by its unique key"""
        # Check albums
        albums = self.results.get('albums', {})
        for album in albums.values():
            for track in album.get('tracks', []):
                if track.get('key') == key:
                    return track
                    
        # Check legacy
        return self.results.get('tracks', {}).get(key)


class SlskdClient:
    """Custom Slskd Client using requests"""
    def __init__(self, host, api_key, url_base='/'):
        self.host = host.rstrip('/')
        self.api_key = api_key
        
        # Clean up URL base
        url_base = url_base.strip()
        if not url_base.startswith('/'):
            url_base = '/' + url_base
        if not url_base.endswith('/'):
            url_base += '/'
        self.url_base = url_base
        
        # Construct base URL carefully to avoid double slashes
        # If host has path, we need to be careful
        self.base_url = f"{self.host}{self.url_base}api/v0"
        self.headers = {'X-API-Key': self.api_key}
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        # Only log if it's a new initialization (avoid noise from health checks)
        # logger.debug(f"SlskdClient initialized with Base URL: {self.base_url}")

    def _request_with_retry(self, method, url, **kwargs):
        """Helper to handle rate limits with retry"""
        max_retries = 3
        backoff = 1
        
        # Set default timeout if not provided
        if 'timeout' not in kwargs:
            kwargs['timeout'] = 30
        
        for i in range(max_retries + 1):
            try:
                response = self.session.request(method, url, **kwargs)
                
                if response.status_code == 429:
                    if i == max_retries:
                        response.raise_for_status()
                    
                    wait_time = backoff * (2 ** i)
                    logger.warning(f"Rate limited (429). Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                    
                response.raise_for_status()
                return response
                
            except requests.exceptions.RequestException as e:
                if i == max_retries:
                    raise
                # Only retry on specific errors if needed, but for now mainly 429 which is handled above.
                # If it's a connection error, maybe retry?
                # For now, let's stick to 429 handling logic within the loop.
                raise

    def search(self, query, timeout=15):
        """Initiate a search"""
        url = f"{self.base_url}/searches"
        try:
            # Slskd expects search text in the body or query param? 
            # Based on docs/usage, usually POST to /search with {searchText: "..."}
            response = self._request_with_retry('POST', url, json={'searchText': query}, timeout=10)
            return response.json()
        except Exception as e:
            logger.error(f"Search init failed for {url}: {e}")
            raise

    def get_search_results(self, search_id):
        """Get results for a search ID"""
        url = f"{self.base_url}/searches/{search_id}"
        try:
            response = self._request_with_retry('GET', url, timeout=10)
            return response.json()
        except Exception as e:
            logger.error(f"Get results failed: {e}")
            raise

    def application_state(self):
        """Get application state"""
        url = f"{self.base_url}/application"
        try:
            response = self._request_with_retry('GET', url, timeout=5)
            return response.json()
        except Exception as e:
            logger.error(f"Get state failed: {e}")
            raise

    def download_file(self, username, filename):
        """Initiate a file download"""
        # Slskd API format: POST /api/v0/transfers/downloads/{username}
        # Body: { "files": ["filename"] }
        url = f"{self.base_url}/transfers/downloads/{username}"
        payload = {"files": [filename]}
        
        logger.info(f"[DOWNLOAD] Initiating download: {filename} from {username}")
        logger.debug(f"[DOWNLOAD] URL: {url}")
        logger.debug(f"[DOWNLOAD] Payload: {payload}")
        
        try:
            response = self._request_with_retry('POST', url, json=payload, timeout=10)
            result = response.json()
            logger.info(f"[DOWNLOAD] Success response: {result}")
            return result
        except requests.exceptions.HTTPError as e:
            logger.error(f"[DOWNLOAD] HTTP Error {e.response.status_code}: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"[DOWNLOAD] Failed for {filename} from {username}: {type(e).__name__}: {e}")
            return None


class WatchListManager:
    """Manages the watch list for busy users"""

    def __init__(self):
        self.watchlist = self._load_watchlist()
        self.lock = threading.Lock()

    def _load_watchlist(self) -> List[Dict]:
        if WATCHLIST_FILE.exists():
            try:
                with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading watchlist: {e}")
                return []
        return []

    def save_watchlist(self):
        with self.lock:
            try:
                with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f:
                    json.dump(self.watchlist, f, indent=2)
            except Exception as e:
                logger.error(f"Error saving watchlist: {e}")

    def add_to_watchlist(self, item: Dict):
        """Add an item to the watch list"""
        with self.lock:
            # Check if already exists
            for existing in self.watchlist:
                if existing['filename'] == item['filename'] and existing['username'] == item['username']:
                    return
            
            item['added_at'] = datetime.now().isoformat()
            self.watchlist.append(item)
            self.save_watchlist()
            logger.info(f"Added to watchlist: {item['filename']} from {item['username']}")

    def remove_from_watchlist(self, item: Dict):
        with self.lock:
            self.watchlist = [i for i in self.watchlist if not (i['filename'] == item['filename'] and i['username'] == item['username'])]
            self.save_watchlist()

    def check_watchlist(self, client: SlskdClient):
        """Check availability of items in watchlist"""
        # Placeholder for check logic
        pass


class Romanizer:
    """Handles Japanese to Romaji conversion"""
    def __init__(self):
        self.kks = pykakasi.kakasi()
        
    def to_romaji(self, text: str) -> str:
        """Convert text to Romaji if it contains Japanese"""
        if not text:
            return ""
            
        result = self.kks.convert(text)
        romaji = " ".join([item['hepburn'] for item in result])
        return romaji.strip()

# Initialize managers
queue_manager = QueueManager()
search_manager = SearchManager()
watchlist_manager = WatchListManager()
romanizer = Romanizer()
musicbrainz_client = MusicBrainzClient(user_agent="slskd-spotify-self-host/1.0 (https://github.com/yourusername/slskd-spotify-self-host)")
isrc_tracker = ISRCTracker(data_dir=CONFIG['DATA_DIR'])

# Load saved state
search_state = load_application_state()


def parse_spotify_csv(file_path: Path) -> List[Dict]:
    """Parse CSV and extract artist, track, and album names"""
    tracks = []

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
            artist = None
            title = None
            album = None
            
            # Extract Artist (case-insensitive)
            for col_name in ['artist', 'Artist', 'Artist Name', 'ARTIST']:
                if col_name in row and row[col_name]:
                    artist = row[col_name].strip()
                    break
            
            # Extract Title (case-insensitive)
            for col_name in ['title', 'Title', 'Track Name', 'Track', 'Song', 'Name']:
                if col_name in row and row[col_name]:
                    title = row[col_name].strip()
                    break
            
            # Extract Album (case-insensitive)
            for col_name in ['album', 'Album', 'Album Name', 'ALBUM']:
                if col_name in row and row[col_name]:
                    album = row[col_name].strip()
                    break

            if artist and title:
                # Create a unique key to avoid duplicates
                key = f"{artist} - {title}"
                if key not in [f"{t['artist']} - {t['title']}" for t in tracks]:
                    tracks.append({
                        'artist': artist,
                        'title': title,
                        'album': album if album else ''
                    })
            elif artist:
                # Fallback if only artist is found
                if artist not in [t['artist'] for t in tracks if not t.get('title')]:
                    tracks.append({
                        'artist': artist,
                        'title': '',
                        'album': album if album else ''
                    })

        logger.info(f"Parsed {len(tracks)} unique tracks from CSV")
        return tracks

    except Exception as e:
        logger.error(f"Error parsing CSV: {e}")
        raise


def search_single_item(client: SlskdClient, search_item: Dict) -> Tuple[List[Dict], str]:
    """
    Search for a single item (artist + title) on Slskd
    """
    artist = search_item.get('artist', '')
    title = search_item.get('title', '')
    
    if title:
        query = f"{artist} {title}"
        display_name = f"{artist} - {title}"
    else:
        query = artist
        display_name = artist

    try:
        logger.info(f"Searching for: {query}")

        # Perform search
        # Note: client.search returns a dict, we need the ID
        search_response = client.search(query)
        search_id = search_response.get('id')
        
        if not search_id:
            logger.error(f"No search ID returned for {query}")
            return [], ""

        # Wait a bit for results to accumulate
        # With concurrent searches, we might want to wait slightly longer or rely on the client to handle it?
        # The user prompt suggested 15s per song was too slow, but that was sequential.
        # In parallel, we can still wait, but maybe less?
        # Let's stick to a reasonable wait time.
        time.sleep(CONFIG['SEARCH_DELAY']) 

        # Fetch results
        results_response = client.get_search_results(search_id)
        files = results_response.get('files', [])

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
                upload_speed = file_info.get('uploadSpeed', 0)
                speed_kbs = upload_speed / 1024 if upload_speed else 0
                has_free_slot = file_info.get('hasFreeUploadSlot', False)
                is_locked = file_info.get('isLocked', False)

                result_dict = {
                    'username': username,
                    'filename': filename,
                    'size': size,
                    'bitrate': bitrate,
                    'extension': extension,
                    'queue_length': queue_length,
                    'speed_kbs': speed_kbs,
                    'has_free_slot': has_free_slot,
                    'is_locked': is_locked,
                    'requested_title': title # Pass for fuzzy matching
                }
                
                all_results.append(result_dict)
            except Exception as e:
                continue

        # Apply smart quality filtering and ranking
        top_results = rank_and_filter_results(all_results)

        logger.info(f"Found {len(all_results)} results for {display_name}, keeping top {len(top_results)}")
        return top_results, search_id

    except Exception as e:
        logger.error(f"Error searching for {display_name}: {e}")
        return [], ""


def background_search_task(search_items: List[Dict] = None):
    """Background task to search for items concurrently"""
    global search_state

    # If items provided, add to queue
    if search_items:
        queue_manager.add_items(search_items)
        logger.info(f"Added {len(search_items)} items to queue")

    # If already active, just return (the loop will pick up new items)
    if search_state['active']:
        return

    logger.info("Starting background search worker")

    # Initialize search state
    search_state['active'] = True
    search_state['total'] = queue_manager.get_count() + search_state.get('progress', 0)
    # Don't reset progress if resuming
    if not search_state.get('progress'):
        search_state['progress'] = 0
    search_state['errors'] = []
    search_state['completed'] = False
    save_application_state(search_state)

    # Initialize Slskd client
    try:
        client = SlskdClient(
            host=CONFIG['SLSKD_URL'],
            api_key=CONFIG['SLSKD_API_KEY'],
            url_base=CONFIG['SLSKD_URL_BASE']
        )
    except Exception as e:
        logger.error(f"Failed to initialize Slskd client: {e}")
        search_state['errors'].append(f"Failed to connect to Slskd: {e}")
        search_state['active'] = False
        search_state['completed'] = True
        save_application_state(search_state)
        return

    def process_item(item):
        if not search_state['active']:
            return

        item_id = f"{item.get('artist', '')} - {item.get('title', '')}"
        logger.info(f"[WORKER] Processing item: {item_id}")

        artist_str = item.get('artist', '')
        title = item.get('title', '')
        album = item.get('album', '')
        search_mode = search_state.get('mode', 'artist_title')

        # STEP 1: Query MusicBrainz for canonical metadata
        mb_metadata = None
        if title:
            try:
                mb_metadata = musicbrainz_client.get_track_metadata(artist_str, title)
                if mb_metadata:
                    logger.info(f"[MB] Found metadata: {mb_metadata.get('title')} ({mb_metadata.get('duration_ms')}ms) ISRC: {mb_metadata.get('isrc')}")
                    item['musicbrainz_metadata'] = mb_metadata
            except Exception as e:
                logger.error(f"[MB] Error querying MusicBrainz: {e}")
                pass
        
        # Split artists (handle comma and ampersand)
        artists = [a.strip() for a in artist_str.replace('&', ',').split(',') if a.strip()]
        if not artists:
            artists = [artist_str]
        
        # Determine search queries based on mode
        queries = []
        
        for artist in artists:
            if search_mode == 'album':
                if album:
                    queries.append({'query': f"{artist} {album}", 'display': f"{artist} - {album}", 'type': 'album'})
                    romaji_artist = romanizer.to_romaji(artist)
                    romaji_album = romanizer.to_romaji(album)
                    if (romaji_artist and romaji_artist != artist) or (romaji_album and romaji_album != album):
                        r_artist = romaji_artist if romaji_artist else artist
                        r_album = romaji_album if romaji_album else album
                        queries.append({'query': f"{r_artist} {r_album}", 'display': f"{artist} - {album} (Romaji)", 'type': 'romaji'})
                else:
                    queries.append({'query': artist, 'display': artist, 'type': 'original'})
                    
            elif search_mode == 'artist_only':
                queries.append({'query': artist, 'display': artist, 'type': 'original'})
                romaji_artist = romanizer.to_romaji(artist)
                if romaji_artist and romaji_artist != artist:
                    queries.append({'query': romaji_artist, 'display': f"{artist} ({romaji_artist})", 'type': 'romaji'})
                    
            else: # artist_title
                if title:
                    queries.append({'query': f"{artist} {title}", 'display': f"{artist} - {title}", 'type': 'original'})
                    romaji_artist = romanizer.to_romaji(artist)
                    romaji_title = romanizer.to_romaji(title)
                    if (romaji_artist and romaji_artist != artist) or (romaji_title and romaji_title != title):
                        r_artist = romaji_artist if romaji_artist else artist
                        r_title = romaji_title if romaji_title else title
                        queries.append({'query': f"{r_artist} {r_title}", 'display': f"{artist} - {title} (Romaji)", 'type': 'romaji'})
                else:
                    queries.append({'query': artist, 'display': artist, 'type': 'original'})

        for q in queries:
            if not search_state['active']:
                return

            display_name = q['display']
            search_state['current_item'] = display_name
            
            # Jitter
            time.sleep(random.uniform(0.5, 1.5))

            try:
                logger.info(f"Searching for: {q['query']}")
                search_response = client.search(q['query'])
                search_id = search_response.get('id')
                
                if search_id:
                    time.sleep(CONFIG['SEARCH_DELAY'])
                    results_response = client.get_search_results(search_id)
                    files = results_response.get('files', [])
                    
                    all_results = []
                    for file_info in files:
                        try:
                            filename = file_info.get('filename', '')
                            size = file_info.get('size', 0)
                            username = file_info.get('username', 'Unknown')
                            extension = Path(filename).suffix.lower().replace('.', '')
                            bitrate = file_info.get('bitRate', 0)
                            queue_length = file_info.get('queueLength', 0)
                            upload_speed = file_info.get('uploadSpeed', 0)
                            speed_kbs = upload_speed / 1024 if upload_speed else 0
                            has_free_slot = file_info.get('hasFreeUploadSlot', False)
                            is_locked = file_info.get('isLocked', False)
                            duration_seconds = file_info.get('length')

                            result_dict = {
                                'username': username,
                                'filename': filename,
                                'size': size,
                                'bitrate': bitrate,
                                'extension': extension,
                                'queue_length': queue_length,
                                'speed_kbs': speed_kbs,
                                'has_free_slot': has_free_slot,
                                'is_locked': is_locked,
                                'duration_seconds': duration_seconds,
                                'requested_title': title if title else artist
                            }
                            all_results.append(result_dict)
                        except:
                            continue

                    musicbrainz_metadata = item.get('musicbrainz_metadata')
                    top_results = rank_and_filter_results(all_results, musicbrainz_metadata)
                    
                    if top_results:
                        if 'collected_results' not in item:
                            item['collected_results'] = []
                        item['collected_results'].extend(top_results)
                        
                else:
                    logger.error(f"No search ID for {q['query']}")
                    
            except Exception as e:
                logger.error(f"[WORKER] Error searching {q['query']}: {e}")

        # After all queries for this item, save results
        main_key = f"{artist} - {title}" if title else artist
        final_results = item.get('collected_results', [])
        
        # Deduplicate
        unique_results = []
        seen = set()
        for r in final_results:
            key = f"{r['username']}_{r['filename']}"
            if key not in seen:
                seen.add(key)
                unique_results.append(r)
        
        # Re-rank
        unique_results.sort(key=lambda x: x['quality_score'], reverse=True)
        unique_results = unique_results[:CONFIG['TOP_RESULTS_COUNT']]
        
        musicbrainz_metadata = item.get('musicbrainz_metadata')

        if unique_results:
            search_manager.add_track_results(
                main_key, 
                artist_str, 
                title, 
                album, 
                unique_results, 
                "", 
                musicbrainz_metadata=musicbrainz_metadata
            )
            # Watchlist check
            top_result = unique_results[0]
            if top_result.get('queue_length', 0) > 0:
                watchlist_manager.add_to_watchlist({
                    'artist': artist,
                    'title': title,
                    'album': album,
                    'username': top_result['username'],
                    'filename': top_result['filename'],
                    'size': top_result['size'],
                    'bitrate': top_result['bitrate']
                })
        else:
             search_state['errors'].append(f"No results for: {main_key}")
             search_manager.add_track_results(main_key, artist, title, album, [], "", musicbrainz_metadata)

        search_state['progress'] += 1
        save_application_state(search_state)
        logger.info(f"[WORKER] Finished item: {item_id}")

    # Drain queue and process
    items_to_process = []
    while True:
        item = queue_manager.get_next()
        if not item: break
        items_to_process.append(item)
    
    if items_to_process:
        # Update total count in case it changed
        search_state['total'] = len(items_to_process) + search_state.get('progress', 0)
        save_application_state(search_state)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(process_item, item) for item in items_to_process]
            concurrent.futures.wait(futures)

    search_state['active'] = False
    search_state['completed'] = True
    save_application_state(search_state)
    logger.info("Background search completed")


# Flask Routes

@app.route('/')
def index():
    """Main dashboard page"""
    # Check if configuration is needed
    if not CONFIG.get('SLSKD_API_KEY'):
        return redirect(url_for('settings'))

    stats = search_manager.get_stats()

    # Get albums for grouped display
    albums = search_manager.results.get('albums', {})
    
    # Also get legacy tracks for backward compatibility or flat view if needed
    # For now, we'll pass both and let the template decide, or migrate legacy to "Unknown Album"
    
    # Sort albums by artist then name
    sorted_albums = dict(sorted(albums.items(), key=lambda item: (item[1]['artist'], item[1]['name'])))

    return render_template('index.html', stats=stats, albums=sorted_albums, search_state=search_state, slskd_url=CONFIG['SLSKD_URL'])


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


@app.route('/track/<path:track_key>')
def track_detail(track_key: str):
    """Track detail page showing top quality search results"""
    track_data = search_manager.get_track_results(track_key)

    if not track_data:
        return "Track not found", 404

    # Limit results to top 20 for better UI performance
    limited_track_data = track_data.copy()
    limited_track_data['results'] = track_data.get('results', [])[:20]

    # Check if ISRC is already downloaded (for duplicate warning)
    musicbrainz_data = track_data.get('musicbrainz')
    isrc = musicbrainz_data.get('isrc') if musicbrainz_data else None
    is_duplicate = isrc_tracker.is_duplicate(isrc) if isrc else False

    return render_template(
        'track.html',
        track_key=track_key,
        track_data=limited_track_data,
        slskd_url=CONFIG['SLSKD_URL'],
        is_duplicate=is_duplicate,
        musicbrainz_data=musicbrainz_data
    )


@app.route('/track/<track_key>/delete', methods=['POST'])
def delete_track(track_key):
    """Delete a track from results and optionally re-search"""
    try:
        # Get track info before deleting if we need to re-search
        research = request.args.get('research', 'false').lower() == 'true'
        
        track_data = search_manager.get_track_results(track_key)
        artist = ""
        title = ""
        
        if track_data:
            artist = track_data.get('artist', '')
            title = track_data.get('title', '')
            
        # If not in data, try to parse key
        if not artist or not title:
            parts = track_key.split(' - ', 1)
            if len(parts) == 2:
                artist, title = parts
            else:
                artist = parts[0]

        # Delete from results
        search_manager.remove_track(track_key)
        
        if research and artist:
            # Add back to queue
            queue_manager.add_items([{
                'artist': artist,
                'title': title,
                'album': track_data.get('album', '') if track_data else ''
            }])
            
            # Ensure search is active
            global search_state
            if not search_state['active']:
                # Start background thread if not running
                search_state['active'] = True
                search_state['completed'] = False
                thread = threading.Thread(target=background_search_task)
                thread.daemon = True
                thread.start()
                
            return jsonify({'success': True, 'message': 'Track deleted and re-queued'})

        return jsonify({'success': True, 'message': 'Track deleted'})

    except Exception as e:
        logger.error(f"Delete error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/download/specific', methods=['POST'])
def download_specific():
    """Download a specific file from a specific user"""
    try:
        data = request.get_json()
        username = data.get('username')
        filename = data.get('filename')
        track_key = data.get('track_key')

        if not username or not filename:
            return jsonify({'error': 'Missing username or filename'}), 400

        # Check for duplicates via ISRC if track_key provided
        isrc = None
        if track_key:
            track_data = search_manager.get_track_results(track_key)
            if track_data and 'musicbrainz' in track_data:
                isrc = track_data['musicbrainz'].get('isrc')
                if isrc and isrc_tracker.is_duplicate(isrc):
                    # We allow override if user explicitly clicked download on a specific file?
                    # Maybe just warn? But the UI disables the button if duplicate.
                    # If they bypass, let them download.
                    pass

        # Initiate download
        # We need a client instance. Since we are in a route, we can create one or use a global one if thread-safe.
        # SlskdClient creates a session. It's better to create a new one or use a pool.
        # For simplicity, create new one.
        client = SlskdClient(
            host=CONFIG['SLSKD_URL'],
            api_key=CONFIG['SLSKD_API_KEY'],
            url_base=CONFIG['SLSKD_URL_BASE']
        )
        
        result = client.download_file(username, filename)
        
        if result:
            # Record download
            artist = ""
            title = ""
            if track_key:
                parts = track_key.split(' - ', 1)
                if len(parts) == 2:
                    artist, title = parts
                else:
                    artist = parts[0]
            
            isrc_tracker.record_download(isrc, artist, title, filename, username=username)
            return jsonify({'success': True, 'message': 'Download initiated'})
        else:
            return jsonify({'error': 'Failed to initiate download'}), 500

    except Exception as e:
        logger.error(f"Specific download error: {e}")
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

        # Filter out already searched items
        force = data.get('force', False)
        search_mode = data.get('mode', 'artist_title')
        
        # Set search mode in state
        search_state['mode'] = search_mode
        
        if not force:
            # Check if "Artist - Title" exists in results
            filtered_artists = []
            for a in artists:
                key = f"{a.get('artist', '')} - {a.get('title', '')}" if a.get('title') else a.get('artist', '')
                if not search_manager.get_track_results(key):
                    filtered_artists.append(a)
            artists = filtered_artists

        if not artists:
            return jsonify({'message': 'All items already searched', 'count': 0}), 200

        # Start background thread
        thread = threading.Thread(target=background_search_task, args=(artists,))
        thread.daemon = True
        thread.start()

        return jsonify({
            'success': True,
            'message': f'Started search for {len(artists)} items',
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


@app.route('/api/mark_reviewed/<path:track_key>', methods=['POST'])
def mark_reviewed(track_key: str):
    """Mark a track as reviewed"""
    success = search_manager.mark_reviewed(track_key)
    if success:
        return jsonify({'success': True})
    return jsonify({'error': 'Track not found'}), 404


@app.route('/api/stats')
def get_stats():
    """Get statistics"""
    return jsonify(search_manager.get_stats())


@app.route('/track/<path:track_key>/delete', methods=['POST'])
def delete_track(track_key: str):
    """Delete a track to allow re-searching"""
    try:
        success = search_manager.delete_track(track_key)
        if success:
            logger.info(f"Deleted track: {track_key}")
            return jsonify({'success': True, 'message': 'Track deleted successfully'})
        else:
            return jsonify({'error': 'Track not found'}), 404
    except Exception as e:
        logger.error(f"Error deleting track {track_key}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/export/csv')
def export_csv():
    """Export all results to CSV"""
    try:
        output = StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow(['Artist', 'Title', 'Album', 'Username', 'Filename', 'Size (MB)', 'Bitrate', 'Extension',
                        'Queue', 'Speed (KB/s)', 'Quality Score', 'Reviewed'])

        # Write data
        tracks = search_manager.results.get('tracks', {})
        for track_key, track_data in tracks.items():
            reviewed = 'Yes' if track_data.get('reviewed', False) else 'No'
            artist = track_data.get('artist', '')
            title = track_data.get('title', '')
            album = track_data.get('album', '')
            for result in track_data['results']:
                writer.writerow([
                    artist,
                    title,
                    album,
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


@app.route('/download/<path:track_key>', methods=['POST'])
def download_track(track_key: str):
    """Download a single track with ISRC-based duplicate prevention"""
    try:
        # Get track results
        track_data = search_manager.get_track_results(track_key)
        if not track_data or not track_data.get('results'):
            return jsonify({'error': 'No results found for track'}), 404

        # Check for ISRC-based duplicates
        musicbrainz_data = track_data.get('musicbrainz')
        isrc = musicbrainz_data.get('isrc') if musicbrainz_data else None
        
        if isrc and isrc_tracker.is_duplicate(isrc):
            duplicate_info = isrc_tracker.get_info_by_isrc(isrc)
            logger.warning(f"Skipping download for {track_key}. Duplicate ISRC found: {isrc}")
            return jsonify({
                'error': 'Duplicate detected',
                'message': 'This track has already been downloaded (ISRC match).',
                'is_duplicate': True,
                'original_download': duplicate_info
            }), 409

        # Get top result
        top_result = track_data['results'][0]
        username = top_result.get('username')
        filename = top_result.get('filename')

        if not username or not filename:
            return jsonify({'error': 'Invalid result data'}), 400

        # Initialize Slskd client
        client = SlskdClient(
            host=CONFIG['SLSKD_URL'],
            api_key=CONFIG['SLSKD_API_KEY']
        )

        # Initiate download via Slskd API
        download_response = client.download_file(username, filename)

        if download_response:
            # Record download with ISRC
            isrc_tracker.record_download(
                isrc=isrc,
                artist=track_data.get('artist'),
                title=track_data.get('title'),
                filename=filename,
                album=track_data.get('album'),
                username=username,
                size=top_result.get('size'),
                bitrate=top_result.get('bitrate'),
                musicbrainz_id=musicbrainz_data.get('musicbrainz_id') if musicbrainz_data else None
            )

            return jsonify({
                'success': True,
                'message': f'Download initiated: {filename}',
                'filename': filename,
                'username': username,
                'isrc': isrc
            })
        else:
            return jsonify({'error': 'Failed to initiate download'}), 500

    except Exception as e:
        logger.error(f"Download error for {track_key}: {e}")
        return jsonify({'error': str(e)}), 500




@app.route('/bulk_download', methods=['POST'])
def bulk_download():
    """Initiate downloads for multiple tracks with ISRC-based duplicate prevention"""
    try:
        data = request.get_json()
        track_keys = data.get('track_keys', [])

        if not track_keys:
            return jsonify({'error': 'No tracks provided'}), 400

        # Initialize Slskd client
        client = SlskdClient(
            host=CONFIG['SLSKD_URL'],
            api_key=CONFIG['SLSKD_API_KEY']
        )

        downloaded = 0
        failed = 0
        duplicates = 0
        duplicate_details = []

        for track_key in track_keys:
            try:
                # Get track results
                track_data = search_manager.get_track_results(track_key)
                if not track_data or not track_data.get('results'):
                    failed += 1
                    logger.warning(f"No results found for track: {track_key}")
                    continue

                # Check for ISRC-based duplicates
                musicbrainz_data = track_data.get('musicbrainz')
                isrc = musicbrainz_data.get('isrc') if musicbrainz_data else None

                if isrc and isrc_tracker.is_duplicate(isrc):
                    duplicates += 1
                    duplicate_info = isrc_tracker.get_info_by_isrc(isrc)
                    duplicate_details.append({
                        'track_key': track_key,
                        'isrc': isrc,
                        'original_download': duplicate_info
                    })
                    logger.warning(f"[DUPLICATE] Blocked download of {track_key} - ISRC {isrc} already downloaded")
                    continue

                # Get top result
                top_result = track_data['results'][0]
                username = top_result.get('username')
                filename = top_result.get('filename')

                if not username or not filename:
                    failed += 1
                    logger.warning(f"Invalid result data for track: {track_key}")
                    continue

                # Initiate download via Slskd API
                download_response = client.download_file(username, filename)

                if download_response:
                    downloaded += 1
                    logger.info(f"Initiated download: {filename} from {username}")

                    # Record download with ISRC
                    isrc_tracker.record_download(
                        isrc=isrc,
                        artist=track_data.get('artist'),
                        title=track_data.get('title'),
                        album=track_data.get('album'),
                        username=username,
                        filename=filename,
                        size=top_result.get('size'),
                        bitrate=top_result.get('bitrate'),
                        musicbrainz_id=musicbrainz_data.get('musicbrainz_id') if musicbrainz_data else None
                    )
                else:
                    failed += 1
                    logger.error(f"Failed to download: {filename}")

            except Exception as e:
                failed += 1
                logger.error(f"Error downloading track {track_key}: {e}")
                continue

        return jsonify({
            'success': True,
            'downloaded': downloaded,
            'failed': failed,
            'duplicates': duplicates,
            'duplicate_details': duplicate_details,
            'total': len(track_keys)
        })

    except Exception as e:
        logger.error(f"Bulk download error: {e}")
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
            state = client.application_state()

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


def watchlist_monitor():
    """Background monitor for watchlist"""
    while True:
        try:
            if CONFIG.get('SLSKD_API_KEY'):
                client = SlskdClient(
                    host=CONFIG['SLSKD_URL'],
                    api_key=CONFIG['SLSKD_API_KEY'],
                    url_base=CONFIG['SLSKD_URL_BASE']
                )
                watchlist_manager.check_watchlist(client)
        except Exception as e:
            logger.error(f"Watchlist monitor error: {e}")
        
        time.sleep(300) # Check every 5 minutes

# Start monitor thread
monitor_thread = threading.Thread(target=watchlist_monitor, daemon=True)
monitor_thread.start()


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
