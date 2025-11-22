# musicbrainz_client.py

import logging
import time
import requests
from typing import Optional, Dict
from urllib.parse import quote

logger = logging.getLogger(__name__)

class MusicBrainzClient:
    """Client for interacting with the MusicBrainz API."""

    BASE_URL = "https://musicbrainz.org/ws/2"
    USER_AGENT = "slskd-spotify-self-host/1.0 (https://github.com/yourusername/slskd-spotify-self-host)"

    def __init__(self, user_agent: str = None):
        if user_agent:
            self.USER_AGENT = user_agent

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.USER_AGENT,
            'Accept': 'application/json'
        })
        self.last_request_time = 0
        # MusicBrainz allows 1 request per second
        self.rate_limit_delay = 1.1

    def _rate_limit(self):
        """Ensure we adhere to the MusicBrainz API rate limit."""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        if time_since_last_request < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last_request
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def search_recording(self, artist: str, title: str, album: Optional[str] = None) -> Optional[Dict]:
        """
        Search MusicBrainz for a track and return its metadata.

        Args:
            artist: Artist name
            title: Track title
            album: Optional album name for better matching

        Returns:
            Dict with metadata or None if no match is found or an error occurs.
        """
        return self.get_track_metadata(artist, title, album)

    def get_track_metadata(self, artist: str, title: str, album: Optional[str] = None) -> Optional[Dict]:
        """
        Search MusicBrainz for a track and return its metadata.
        Returns None if no match is found or an error occurs.
        """
        self._rate_limit()

        # Construct a lucene query
        # We use the 'recording' entity to search for tracks
        query = f'artist:"{artist}" AND recording:"{title}"'
        if album:
            query += f' AND release:"{album}"'

        params = {
            'query': query,
            'fmt': 'json',
            'limit': 1  # We only need the top match
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

                # Take the best match (first one)
                recording = recordings[0]

                metadata = {
                    'musicbrainz_id': recording.get('id'),
                    'title': recording.get('title'),
                    # Duration is in milliseconds
                    'duration_ms': recording.get('length'),
                    'score': recording.get('score', 0)
                }

                # Get artist name(s)
                artist_credits = recording.get('artist-credit', [])
                if artist_credits:
                    metadata['artist'] = artist_credits[0].get('artist', {}).get('name')

                # Get ISRCs
                isrcs = recording.get('isrcs', [])
                if isrcs:
                    # ISRCs are returned as a simple list of strings
                    metadata['isrc'] = isrcs[0]

                # Get Releases (Albums/Singles)
                releases = recording.get('releases', [])
                if releases:
                    # Take the title of the first release, which is often the main album/single
                    metadata['album'] = releases[0].get('title')

                logger.info(f"Found MusicBrainz metadata for: {artist} - {title} (ISRC: {metadata.get('isrc')})")
                return metadata

            elif response.status_code == 503:
                logger.warning("MusicBrainz API is temporarily unavailable (503).")
                return None
            else:
                logger.error(f"MusicBrainz API error: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"Error querying MusicBrainz API: {e}")
            return None

    def get_recording_by_isrc(self, isrc: str) -> Optional[Dict]:
        """
        Look up a recording by its ISRC.

        Args:
            isrc: International Standard Recording Code

        Returns:
            Dict with metadata or None if not found
        """
        self._rate_limit()

        params = {
            'query': f'isrc:{isrc}',
            'fmt': 'json',
            'limit': 1
        }

        logger.info(f"Looking up ISRC: {isrc}")

        try:
            url = f"{self.BASE_URL}/recording"
            response = self.session.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                recordings = data.get('recordings', [])

                if not recordings:
                    logger.info(f"No recording found for ISRC: {isrc}")
                    return None

                recording = recordings[0]

                # Extract basic metadata
                metadata = {
                    'isrc': isrc,
                    'duration_ms': recording.get('length'),
                    'title': recording.get('title'),
                    'artist': recording['artist-credit'][0].get('name') if 'artist-credit' in recording else None,
                    'musicbrainz_id': recording.get('id')
                }

                return metadata
            else:
                logger.error(f"MusicBrainz API error: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error looking up ISRC: {e}")
            return None


# Example usage for testing:
if __name__ == "__main__":
    # Configure basic logging to see output in the console
    logging.basicConfig(level=logging.INFO)

    client = MusicBrainzClient()

    # Test case 1: A known track
    test_artist = "Hikaru Utada"
    test_title = "First Love"
    print(f"\n--- Testing: {test_artist} - {test_title} ---")
    metadata = client.get_track_metadata(test_artist, test_title)
    if metadata:
        print("Found Metadata:")
        for key, value in metadata.items():
            print(f"  {key}: {value}")
    else:
        print("No metadata found.")

    # Test case 2: A track with Japanese characters
    test_artist_jp = "宇多田ヒカル"
    test_title_jp = "First Love"
    print(f"\n--- Testing (Japanese Artist): {test_artist_jp} - {test_title_jp} ---")
    metadata_jp = client.get_track_metadata(test_artist_jp, test_title_jp)
    if metadata_jp:
        print("Found Metadata:")
        for key, value in metadata_jp.items():
            print(f"  {key}: {value}")
    else:
        print("No metadata found.")
