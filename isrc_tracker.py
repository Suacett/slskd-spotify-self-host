"""
ISRC Tracker
Manages the downloads history to prevent duplicate downloads based on ISRCs.
"""

import json
import logging
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


class ISRCTracker:
    """
    Thread-safe tracker for downloaded ISRCs to prevent duplicates.

    Maintains a persistent record of all downloaded tracks with their ISRCs,
    allowing definitive duplicate detection across different languages and versions.
    """

    def __init__(self, data_dir: str = '/app/data'):
        """
        Initialize the ISRC tracker.

        Args:
            data_dir: Directory to store the downloads.json file
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.file_path = self.data_dir / 'downloads.json'
        self.lock = threading.RLock()
        self.downloads = self._load()

    def _load(self) -> Dict[str, Any]:
        """
        Load downloads history from file.

        Returns:
            Dict with downloads data structure
        """
        if not self.file_path.exists():
            logger.info("No downloads.json found, creating new tracker")
            return {
                'last_updated': datetime.now().isoformat(),
                'downloads': []
            }

        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info(f"Loaded {len(data.get('downloads', []))} download records")
                return data
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding downloads.json: {e}, starting fresh")
            return {
                'last_updated': datetime.now().isoformat(),
                'downloads': []
            }
        except Exception as e:
            logger.error(f"Error loading downloads.json: {e}")
            return {
                'last_updated': datetime.now().isoformat(),
                'downloads': []
            }

    def _save(self):
        """Save downloads history to file."""
        try:
            self.downloads['last_updated'] = datetime.now().isoformat()
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(self.downloads, f, indent=2, ensure_ascii=False)
            logger.debug("Downloads history saved")
        except Exception as e:
            logger.error(f"Error saving downloads.json: {e}")

    def is_duplicate(self, isrc: Optional[str]) -> bool:
        """
        Check if an ISRC has already been downloaded.

        Args:
            isrc: International Standard Recording Code to check

        Returns:
            True if this ISRC has been downloaded before, False otherwise
        """
        if not isrc:
            # If no ISRC available, can't determine duplicate status
            return False

        with self.lock:
            for download in self.downloads.get('downloads', []):
                if download.get('isrc') == isrc:
                    logger.info(f"Duplicate detected: ISRC {isrc} already downloaded")
                    logger.info(f"Original download: {download.get('artist')} - {download.get('title')} on {download.get('downloaded_at')}")
                    return True

            return False

    def get_duplicate_info(self, isrc: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a previously downloaded track by ISRC.

        Args:
            isrc: International Standard Recording Code

        Returns:
            Dict with download info or None if not found
        """
        if not isrc:
            return None

        with self.lock:
            for download in self.downloads.get('downloads', []):
                if download.get('isrc') == isrc:
                    return download

            return None

    def record_download(
        self,
        isrc: Optional[str],
        artist: str,
        title: str,
        album: Optional[str] = None,
        username: Optional[str] = None,
        filename: Optional[str] = None,
        size: Optional[int] = None,
        bitrate: Optional[int] = None,
        musicbrainz_id: Optional[str] = None
    ):
        """
        Record a successful download.

        Args:
            isrc: International Standard Recording Code
            artist: Artist name
            title: Track title
            album: Album name
            username: Slskd username
            filename: Downloaded filename
            size: File size in bytes
            bitrate: Audio bitrate
            musicbrainz_id: MusicBrainz recording ID
        """
        with self.lock:
            download_record = {
                'isrc': isrc,
                'artist': artist,
                'title': title,
                'album': album,
                'username': username,
                'filename': filename,
                'size': size,
                'bitrate': bitrate,
                'musicbrainz_id': musicbrainz_id,
                'downloaded_at': datetime.now().isoformat()
            }

            self.downloads.setdefault('downloads', []).append(download_record)
            self._save()

            logger.info(f"Recorded download: {artist} - {title}" + (f" (ISRC: {isrc})" if isrc else " (no ISRC)"))

    def get_all_downloads(self) -> List[Dict[str, Any]]:
        """
        Get all download records.

        Returns:
            List of download records
        """
        with self.lock:
            return self.downloads.get('downloads', []).copy()

    def get_stats(self) -> Dict[str, int]:
        """
        Get download statistics.

        Returns:
            Dict with stats: total downloads, with ISRC, without ISRC
        """
        with self.lock:
            downloads = self.downloads.get('downloads', [])
            with_isrc = sum(1 for d in downloads if d.get('isrc'))

            return {
                'total_downloads': len(downloads),
                'with_isrc': with_isrc,
                'without_isrc': len(downloads) - with_isrc
            }

    def remove_download(self, isrc: str) -> bool:
        """
        Remove a download record by ISRC (for testing/admin purposes).

        Args:
            isrc: ISRC to remove

        Returns:
            True if removed, False if not found
        """
        with self.lock:
            downloads = self.downloads.get('downloads', [])
            original_length = len(downloads)

            self.downloads['downloads'] = [d for d in downloads if d.get('isrc') != isrc]

            if len(self.downloads['downloads']) < original_length:
                self._save()
                logger.info(f"Removed download record for ISRC: {isrc}")
                return True

            return False

    def clear_all(self):
        """Clear all download records (use with caution)."""
        with self.lock:
            self.downloads = {
                'last_updated': datetime.now().isoformat(),
                'downloads': []
            }
            self._save()
            logger.warning("All download records cleared")
