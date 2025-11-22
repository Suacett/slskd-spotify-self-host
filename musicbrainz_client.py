"""
MusicBrainz API Client
Fetches canonical metadata for tracks including ISRC, duration, album, and artist information.
"""

import time
import logging
import requests
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class MusicBrainzClient:
    """
    Client for querying the MusicBrainz API.

    Implements rate limiting (1 request per second as per MusicBrainz guidelines)
    and provides methods to fetch canonical track metadata.
    """

    BASE_URL = "https://musicbrainz.org/ws/2"
    RATE_LIMIT_DELAY = 1.0  # 1 second between requests per MusicBrainz guidelines
    REQUEST_TIMEOUT = 10  # 10 seconds timeout for requests
    MAX_RETRIES = 3

    def __init__(self, user_agent: str = "slskd-spotify-self-host/1.0"):
        """
        Initialize the MusicBrainz client.

        Args:
            user_agent: User agent string for API requests (required by MusicBrainz)
        """
        self.user_agent = user_agent
        self.last_request_time = 0
        self.headers = {
            'User-Agent': user_agent,
            'Accept': 'application/json'
        }

    def _rate_limit(self):
        """Ensure we don't exceed MusicBrainz rate limits (1 req/sec)."""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time

        if time_since_last_request < self.RATE_LIMIT_DELAY:
            sleep_time = self.RATE_LIMIT_DELAY - time_since_last_request
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Make a request to the MusicBrainz API with retry logic.

        Args:
            endpoint: API endpoint (e.g., 'recording')
            params: Query parameters

        Returns:
            JSON response or None if request fails
        """
        url = f"{self.BASE_URL}/{endpoint}"

        for attempt in range(self.MAX_RETRIES):
            try:
                self._rate_limit()

                logger.debug(f"MusicBrainz request: {endpoint}, params: {params}, attempt {attempt + 1}/{self.MAX_RETRIES}")

                response = requests.get(
                    url,
                    params=params,
                    headers=self.headers,
                    timeout=self.REQUEST_TIMEOUT
                )

                if response.status_code == 200:
                    logger.debug(f"MusicBrainz request successful")
                    return response.json()
                elif response.status_code == 503:
                    # Service unavailable, wait and retry
                    wait_time = (attempt + 1) * 2
                    logger.warning(f"MusicBrainz service unavailable (503), retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                elif response.status_code == 404:
                    logger.info(f"MusicBrainz: No results found (404)")
                    return None
                else:
                    logger.error(f"MusicBrainz request failed: {response.status_code} - {response.text}")
                    return None

            except requests.exceptions.Timeout:
                logger.warning(f"MusicBrainz request timeout (attempt {attempt + 1}/{self.MAX_RETRIES})")
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep((attempt + 1) * 2)
                    continue
            except requests.exceptions.RequestException as e:
                logger.error(f"MusicBrainz request error: {e}")
                return None

        logger.error(f"MusicBrainz request failed after {self.MAX_RETRIES} attempts")
        return None

    def search_recording(self, artist: str, title: str, album: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Search for a recording (track) in MusicBrainz.

        Args:
            artist: Artist name
            title: Track title
            album: Optional album name for better matching

        Returns:
            Dict with metadata or None if not found:
            {
                'isrc': str or None,
                'duration_ms': int or None (in milliseconds),
                'title': str,
                'artist': str,
                'album': str or None,
                'musicbrainz_id': str,
                'score': int (matching confidence 0-100)
            }
        """
        # Build search query
        query_parts = [f'artist:"{artist}"', f'recording:"{title}"']
        if album:
            query_parts.append(f'release:"{album}"')

        query = ' AND '.join(query_parts)

        params = {
            'query': query,
            'fmt': 'json',
            'limit': 5  # Get top 5 matches to find best one
        }

        logger.info(f"Searching MusicBrainz for: {artist} - {title}" + (f" (Album: {album})" if album else ""))

        response = self._make_request('recording', params)

        if not response or 'recordings' not in response or not response['recordings']:
            logger.info(f"No MusicBrainz results for: {artist} - {title}")
            return None

        recordings = response['recordings']
        logger.info(f"Found {len(recordings)} MusicBrainz recording(s)")

        # Get the best match (first result, highest score)
        best_match = recordings[0]

        # Extract ISRC (may be multiple, we'll take the first)
        isrc = None
        if 'isrcs' in best_match and best_match['isrcs']:
            isrc = best_match['isrcs'][0]
            logger.info(f"Found ISRC: {isrc}")
        else:
            logger.warning(f"No ISRC found for: {artist} - {title}")

        # Extract duration (in milliseconds)
        duration_ms = best_match.get('length')  # MusicBrainz stores duration as 'length' in ms
        if duration_ms:
            logger.info(f"Found duration: {duration_ms}ms ({duration_ms / 1000:.1f}s)")

        # Extract artist name (use artist-credit for most accurate)
        mb_artist = artist  # default to search artist
        if 'artist-credit' in best_match and best_match['artist-credit']:
            mb_artist = best_match['artist-credit'][0].get('name', artist)

        # Extract album (from releases if available)
        mb_album = None
        if 'releases' in best_match and best_match['releases']:
            mb_album = best_match['releases'][0].get('title')
            logger.info(f"Found album: {mb_album}")

        metadata = {
            'isrc': isrc,
            'duration_ms': duration_ms,
            'title': best_match.get('title', title),
            'artist': mb_artist,
            'album': mb_album,
            'musicbrainz_id': best_match.get('id'),
            'score': best_match.get('score', 0)
        }

        logger.info(f"MusicBrainz metadata: {metadata}")

        return metadata

    def get_recording_by_isrc(self, isrc: str) -> Optional[Dict[str, Any]]:
        """
        Look up a recording by its ISRC.

        Args:
            isrc: International Standard Recording Code

        Returns:
            Dict with metadata or None if not found
        """
        params = {
            'query': f'isrc:{isrc}',
            'fmt': 'json',
            'limit': 1
        }

        logger.info(f"Looking up ISRC: {isrc}")

        response = self._make_request('recording', params)

        if not response or 'recordings' not in response or not response['recordings']:
            logger.info(f"No recording found for ISRC: {isrc}")
            return None

        recording = response['recordings'][0]

        # Extract basic metadata
        metadata = {
            'isrc': isrc,
            'duration_ms': recording.get('length'),
            'title': recording.get('title'),
            'artist': recording['artist-credit'][0].get('name') if 'artist-credit' in recording else None,
            'musicbrainz_id': recording.get('id')
        }

        return metadata
