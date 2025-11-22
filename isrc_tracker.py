import json
import logging
import threading
from pathlib import Path
from typing import Optional, Dict
import time

logger = logging.getLogger(__name__)

class ISRCTracker:
    """
    Manages a persistent history of downloaded tracks using their ISRC
    to prevent downloading duplicates.
    """
    def __init__(self, data_dir: str):
        self.file_path = Path(data_dir) / 'downloads_history.json'
        self.lock = threading.RLock()
        self.history = self._load_history()

    def _load_history(self) -> Dict[str, Dict]:
        """Load download history from JSON file."""
        if self.file_path.exists():
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading downloads history: {e}")
                return {}
        return {}

    def _save_history(self):
        """Save download history to JSON file."""
        try:
            # Ensure directory exists
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving downloads history: {e}")

    def is_duplicate(self, isrc: Optional[str]) -> bool:
        """Check if an ISRC exists in the history."""
        if not isrc:
            # If we don't have an ISRC, we can't assume it's a duplicate based on this check.
            return False
        with self.lock:
            return isrc in self.history

    def add_download(self, isrc: Optional[str], artist: str, title: str, filename: str):
        """Record a successful download."""
        if not isrc:
            logger.warning(f"Download finished without ISRC for {artist} - {title}. Cannot track for duplicates.")
            return

        with self.lock:
            if isrc not in self.history:
                logger.info(f"Recording download history for ISRC: {isrc} ({artist} - {title})")
                self.history[isrc] = {
                    'artist': artist,
                    'title': title,
                    'filename': filename,
                    'downloaded_at': time.strftime('%Y-%m-%dT%H:%M:%S')
                }
                self._save_history()

    def get_info_by_isrc(self, isrc: str) -> Optional[Dict]:
        """Get details about a previously downloaded ISRC."""
        with self.lock:
            return self.history.get(isrc)
