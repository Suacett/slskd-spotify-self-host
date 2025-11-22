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
import concurrent.futures
import random
import difflib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from io import StringIO
from urllib.parse import quote

from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file
from werkzeug.utils import secure_filename
import requests
import pykakasi

# Import custom modules
from musicbrainz_client import MusicBrainzClient
from isrc_tracker import ISRCTracker

# Configuration
DEFAULT_CONFIG = {
    'SLSKD_URL': os.getenv('SLSKD_URL', 'http://192.168.1.124:5030'),
    'SLSKD_API_KEY': os.getenv('SLSKD_API_KEY', ''),
    'SLSKD_URL_BASE': os.getenv('SLSKD_URL_BASE', '/'),
    'SEARCH_TIMEOUT': int(os.getenv('SEARCH_TIMEOUT', '15')),
    'SEARCH_DELAY': int(os.getenv('SEARCH_DELAY', '2')),
    'DATA_DIR': os.getenv('DATA_DIR', '/app/data'),
    'MIN_BITRATE': 192,
    'MAX_QUEUE_LENGTH': 50,
    'MIN_SPEED_KBS': 50,
    'TOP_RESULTS_COUNT': 5,
    'MAX_FILE_SIZE_MB': 30,
}

# Setup Paths
DATA_DIR = Path(DEFAULT_CONFIG['DATA_DIR'])
DATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = DATA_DIR / 'config.json'
SEARCH_STATE_FILE = DATA_DIR / 'search_state.json'
WATCHLIST_FILE = DATA_DIR / 'watch_list.json'
LOG_FILE = DATA_DIR / 'application.log'

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load Config
def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = DEFAULT_CONFIG.copy()
                config.update(json.load(f))
                return config
        except Exception as e:
            logger.error(f"Error loading config: {e}")
    return DEFAULT_CONFIG.copy()

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving config: {e}")
        return False

CONFIG = load_config()

# Initialize Flask
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = DATA_DIR / 'uploads'
app.config['UPLOAD_FOLDER'].mkdir(exist_ok=True)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')

# --- Classes ---

class SlskdClient:
    """Custom Slskd Client"""
    def __init__(self, host, api_key, url_base='/'):
        self.host = host.rstrip('/')
        self.api_key = api_key
        self.url_base = url_base.strip().strip('/')
        self.base_url = f"{self.host}/{self.url_base}/api/v0" if self.url_base else f"{self.host}/api/v0"
        self.base_url = self.base_url.replace('//api', '/api') # Cleanup
        self.headers = {'X-API-Key': self.api_key}
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def _request(self, method, endpoint, **kwargs):
        url = f"{self.base_url}{endpoint}"
        try:
            resp = self.session.request(method, url, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Slskd request failed ({method} {url}): {e}")
            return None

    def search(self, query):
        return self._request('POST', '/searches', json={'searchText': query})

    def get_search_results(self, search_id):
        return self._request('GET', f'/searches/{search_id}')

    def download(self, username, filename):
        # Correct endpoint for Slskd download
        logger.info(f"Requesting download: {filename} from {username}")
        return self._request('POST', f'/transfers/downloads/{username}', json=[{'filename': filename}])

    def application_state(self):
        return self._request('GET', '/application')

class SearchManager:
    """Manages search state and persistence"""
    def __init__(self):
        self.lock = threading.RLock()
        self.state = self._load_state()

    def _load_state(self):
        if SEARCH_STATE_FILE.exists():
            try:
                with open(SEARCH_STATE_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load search state: {e}")
        return {'albums': {}, 'last_updated': None}

    def save_state(self):
        with self.lock:
            self.state['last_updated'] = datetime.now().isoformat()
            try:
                with open(SEARCH_STATE_FILE, 'w') as f:
                    json.dump(self.state, f, indent=2)
            except Exception as e:
                logger.error(f"Failed to save search state: {e}")

    def add_track_result(self, track_key, artist, title, album, results, mb_metadata=None):
        with self.lock:
            # Normalize Album Key
            album_name = album if album else "Unknown Album"
            if mb_metadata and mb_metadata.get('album'):
                album_name = mb_metadata['album']
            
            album_key = f"{artist} - {album_name}"
            
            if 'albums' not in self.state:
                self.state['albums'] = {}
            
            if album_key not in self.state['albums']:
                self.state['albums'][album_key] = {
                    'artist': artist,
                    'title': album_name,
                    'type': 'Album', # Default
                    'tracks': {}
                }
                if mb_metadata:
                     self.state['albums'][album_key]['type'] = 'Album' # Could extract type from MB if available

            # Add Track
            self.state['albums'][album_key]['tracks'][track_key] = {
                'artist': artist,
                'title': title,
                'album': album_name,
                'results': results,
                'result_count': len(results),
                'musicbrainz': mb_metadata,
                'searched_at': datetime.now().isoformat(),
                'reviewed': False,
                'smart_filter': True # Default enabled
            }
            self.save_state()

    def get_track(self, track_key):
        for album in self.state['albums'].values():
            if track_key in album['tracks']:
                return album['tracks'][track_key]
        return None

    def delete_track(self, track_key):
        with self.lock:
            for album_key, album in self.state['albums'].items():
                if track_key in album['tracks']:
                    del album['tracks'][track_key]
                    # Clean up empty albums
                    if not album['tracks']:
                        del self.state['albums'][album_key]
                    self.save_state()
                    return True
        return False
    
    def toggle_smart_filter(self, track_key):
        with self.lock:
            track = self.get_track(track_key)
            if track:
                track['smart_filter'] = not track.get('smart_filter', True)
                self.save_state()
                return track['smart_filter']
        return None

    def get_dashboard_data(self):
        # Return structure optimized for frontend
        return self.state

# Initialize Globals
search_manager = SearchManager()
slskd_client = SlskdClient(CONFIG['SLSKD_URL'], CONFIG['SLSKD_API_KEY'], CONFIG['SLSKD_URL_BASE'])
musicbrainz_client = MusicBrainzClient()
isrc_tracker = ISRCTracker(str(DATA_DIR))
romanizer = pykakasi.kakasi()

# --- Helper Functions ---

def calculate_quality_score(file_info, requested_title, mb_metadata=None):
    score = 0
    filename = file_info.get('filename', '').lower()
    req_title = requested_title.lower()
    
    # 1. Name Match
    if req_title in filename:
        score += 50
    
    # 2. Bitrate
    bitrate = file_info.get('bitrate', 0)
    if bitrate >= 320: score += 40
    elif bitrate >= 192: score += 20
    else: score -= 50
    
    # 3. File Size Limit
    size_mb = file_info.get('size', 0) / (1024*1024)
    if size_mb > CONFIG['MAX_FILE_SIZE_MB']:
        score -= 500 # Hard penalty
        
    # 4. MusicBrainz Duration
    if mb_metadata and mb_metadata.get('duration_ms'):
        expected = mb_metadata['duration_ms'] / 1000
        actual = file_info.get('duration', 0) # Assuming Slskd returns 'duration' or 'length'
        if not actual: actual = file_info.get('length', 0)
        
        if actual:
            diff = abs(actual - expected)
            if diff < 5: score += 100
            elif diff < 15: score += 50
            else: score -= 200 # Wrong version
            
    return score

def background_search_task(items):
    for item in items:
        artist = item['artist']
        title = item['title']
        album = item.get('album', '')
        track_key = f"{artist} - {title}"
        
        # 1. MusicBrainz
        mb_meta = None
        try:
            mb_meta = musicbrainz_client.get_track_metadata(artist, title)
        except Exception as e:
            logger.error(f"MB Error: {e}")
            
        # 2. Slskd Search
        query = f"{artist} {title}"
        try:
            resp = slskd_client.search(query)
            search_id = resp.get('id')
            if search_id:
                time.sleep(CONFIG['SEARCH_DELAY'])
                results_resp = slskd_client.get_search_results(search_id)
                files = results_resp.get('files', [])
                
                # Process Results
                processed_results = []
                for f in files:
                    # Basic filtering
                    if f.get('isLocked'): continue
                    ext = Path(f['filename']).suffix.lower().replace('.','')
                    if ext in ['mkv','avi','mp4','mov']: continue # No video
                    
                    f['quality_score'] = calculate_quality_score(f, title, mb_meta)
                    processed_results.append(f)
                
                # Sort
                processed_results.sort(key=lambda x: x['quality_score'], reverse=True)
                
                # Save
                search_manager.add_track_result(track_key, artist, title, album, processed_results, mb_meta)
                
        except Exception as e:
            logger.error(f"Search failed for {track_key}: {e}")

# --- Routes ---

@app.route('/')
def index():
    if not CONFIG['SLSKD_API_KEY']:
        return redirect(url_for('settings'))
    return render_template('index.html', slskd_url=CONFIG['SLSKD_URL'])

@app.route('/api/data')
def api_data():
    return jsonify(search_manager.get_dashboard_data())

@app.route('/api/toggle_quality/<path:track_key>', methods=['POST'])
def toggle_quality(track_key):
    new_state = search_manager.toggle_smart_filter(track_key)
    if new_state is not None:
        return jsonify({'success': True, 'smart_filter': new_state})
    return jsonify({'error': 'Track not found'}), 404

@app.route('/track/<path:track_key>')
def track_detail(track_key):
    track = search_manager.get_track(track_key)
    if not track: return "Track not found", 404
    
    # Filter results based on smart_filter
    results = track['results']
    if track.get('smart_filter', True):
        results = [r for r in results if r['quality_score'] > 0]
        
    return render_template('track.html', track=track, results=results, track_key=track_key, slskd_url=CONFIG['SLSKD_URL'])

@app.route('/track/<path:track_key>/delete', methods=['POST'])
def delete_track(track_key):
    track = search_manager.get_track(track_key)
    if track:
        # Prepare item for re-search
        item = {'artist': track['artist'], 'title': track['title'], 'album': track['album']}
        search_manager.delete_track(track_key)
        
        # Re-queue
        t = threading.Thread(target=background_search_task, args=([item],))
        t.start()
        
        return jsonify({'success': True, 'message': 'Track deleted and re-queued'})
    return jsonify({'error': 'Track not found'}), 404

@app.route('/download/<path:track_key>', methods=['POST'])
def download_track(track_key):
    track = search_manager.get_track(track_key)
    if not track or not track['results']:
        return jsonify({'error': 'No results'}), 404
        
    # Check ISRC
    mb = track.get('musicbrainz')
    if mb and mb.get('isrc'):
        if isrc_tracker.is_duplicate(mb['isrc']):
            return jsonify({'error': 'Duplicate ISRC', 'is_duplicate': True}), 409
            
    # Download Top Result
    # Note: In a real app, user might pick a specific result. 
    # Here we assume top result or the one passed in body? 
    # User prompt implies clicking a download button for a specific file usually.
    # But route is /download/<track_key>. 
    # Let's assume we download the BEST available result.
    
    # Wait, usually the frontend passes the specific file to download.
    # If the route is /download/<track_key>, it implies auto-downloading the best match.
    # If the user wants to download a specific file from the list, the route should probably take a file ID or index.
    # However, based on previous code, it took the top result.
    
    # Let's support an optional 'filename' in body to pick a specific result
    data = request.get_json() or {}
    target_filename = data.get('filename')
    target_username = data.get('username')
    
    result_to_dl = None
    if target_filename and target_username:
        for r in track['results']:
            if r['filename'] == target_filename and r['username'] == target_username:
                result_to_dl = r
                break
    else:
        result_to_dl = track['results'][0]
        
    if result_to_dl:
        resp = slskd_client.download(result_to_dl['username'], result_to_dl['filename'])
        if resp:
            if mb and mb.get('isrc'):
                isrc_tracker.record_download(mb['isrc'], track['artist'], track['title'], result_to_dl['filename'])
            return jsonify({'success': True})
            
    return jsonify({'error': 'Download failed'}), 500

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files: return jsonify({'error': 'No file'}), 400
    f = request.files['file']
    if not f.filename.endswith('.csv'): return jsonify({'error': 'CSV only'}), 400
    
    path = app.config['UPLOAD_FOLDER'] / secure_filename(f.filename)
    f.save(path)
    
    # Parse
    items = []
    with open(path, 'r') as csvf:
        reader = csv.DictReader(csvf)
        for row in reader:
            # Flexible column names
            artist = row.get('Artist') or row.get('artist')
            title = row.get('Title') or row.get('title') or row.get('Track')
            album = row.get('Album') or row.get('album')
            if artist and title:
                items.append({'artist': artist, 'title': title, 'album': album})
                
    # Start Search
    t = threading.Thread(target=background_search_task, args=(items,))
    t.start()
    
    return jsonify({'success': True, 'count': len(items)})

@app.route('/settings')
def settings():
    return render_template('settings.html', config=CONFIG)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
