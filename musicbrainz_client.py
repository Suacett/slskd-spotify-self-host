import logging
import time
import requests
from typing import Optional, Dict
from urllib.parse import quote

logger = logging.getLogger(__name__)

class MusicBrainzClient:
    """Client for interacting with the MusicBrainz API."""
    
    BASE_URL = "https://musicbrainz.org/ws/2"
    # MusicBrainz requires a polite User-Agent. 
    # Ideally, replace 'contact@example.com' with your actual email.
    USER_AGENT = "SpotifyToSlskd/1.0 ( contact@example.com )" 

    def __init__(self, user_agent: str = None):
        self.session = requests.Session()
        ua = user_agent if user_agent else self.USER_AGENT
        self.session.headers.update({
            'User-Agent': ua,
            'Accept': 'application/json'
        })
        self.last_request_time = 0
        # MusicBrainz rate limit rule: 1 request per second per IP
        self.rate_limit_delay = 1.1

    def _rate_limit(self):
        """Ensure we adhere to the MusicBrainz API rate limit."""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        if time_since_last_request < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last_request
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def get_track_metadata(self, artist: str, title: str) -> Optional[Dict]:
        """
        Search MusicBrainz for a track and return its metadata.
        Returns None if no match is found or an error occurs.
        """
        self._rate_limit()
        
        # Use a Lucene search query for artist and recording title
        query = f'artist:"{artist}" AND recording:"{title}"'
        params = {
            'query': query,
            'fmt': 'json',
            'limit': 3 # Fetch top 3 to check for best match
        }
        
        try:
            url = f"{self.BASE_URL}/recording"
            logger.info(f"Querying MusicBrainz for: {artist} - {title}")
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                recordings = data.get('recordings', [])
                
                if not recordings:
                    logger.info(f"No MusicBrainz match found for: {artist} - {title}")
                    return None
                
                # Simple heuristic: take the first (best scored) match.
                recording = recordings[0]
                
                metadata = {
                    'mbid': recording.get('id'),
                    'title': recording.get('title'),
                    # Duration is usually in milliseconds
                    'duration_ms': recording.get('length'), 
                    'isrc': None,
                    'album': None,
                    'artist': None
                }
                
                # Get artist name(s)
                artist_credits = recording.get('artist-credit', [])
                if artist_credits:
                    metadata['artist'] = artist_credits[0].get('artist', {}).get('name')
                    
                # Get ISRC (International Standard Recording Code) - Critical for de-duping
                isrcs = recording.get('isrcs', [])
                if isrcs:
                    # Use the first ISRC found
                    metadata['isrc'] = isrcs[0].get('id')
                    
                # Get Release (Album) information
                releases = recording.get('releases', [])
                if releases:
                    # Try to find an album, preferring official studio albums over compilations
                    preferred_release = releases[0]
                    for release in releases:
                        status = release.get('status', '').lower()
                        secondary_types = release.get('release-group', {}).get('secondary-types', [])
                        if status == 'official' and 'compilation' not in secondary_types:
                            preferred_release = release
                            break
                    metadata['album'] = preferred_release.get('title')
                    
                if metadata['isrc']:
                     logger.info(f"Found MusicBrainz metadata with ISRC: {metadata['isrc']}")
                else:
                     logger.info(f"Found MusicBrainz metadata (no ISRC).")
                     
                return metadata
                
            elif response.status_code == 503:
                logger.warning("MusicBrainz API is temporarily unavailable (rate limited or down).")
                return None
            else:
                logger.error(f"MusicBrainz API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error querying MusicBrainz API: {e}")
            return None
