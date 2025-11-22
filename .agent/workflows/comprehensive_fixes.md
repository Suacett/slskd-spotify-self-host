---
description: Comprehensive fixes for all reported issues
---

# Comprehensive Fixes Implementation Plan

## Issues to Address

### 1. **Duplicate Prevention (CRITICAL)**
- **Problem**: Still adding duplicates despite ISRC tracking
- **Solution**: 
  - Enhance ISRC matching with fuzzy title/artist matching as fallback
  - Add track fingerprinting based on artist + title + duration
  - Implement stricter duplicate checking in upload phase
  - Use MusicBrainz metadata for canonical track identification

### 2. **MusicBrainz Integration Enhancement**
- **Problem**: Need better metadata pairing for verification
- **Solution**:
  - Use MusicBrainz track names as canonical reference
  - Match Slskd results against MB metadata (title, duration, album)
  - Score results based on metadata similarity
  - Reject results that don't match MB data within tolerance

### 3. **Search Speed Optimization**
- **Problem**: Searching is slow
- **Current**: 4 concurrent workers, 0.5-1.5s jitter, 2s delay
- **Solution**:
  - Increase concurrent workers to 8
  - Reduce jitter to 0.2-0.5s
  - Reduce SEARCH_DELAY to 1s (from 2s)
  - Implement result caching
  - Skip MusicBrainz lookup for re-searches if already cached

### 4. **Auto-Refresh Dashboard**
- **Problem**: Results don't auto-refresh, show "no quality results" prematurely
- **Solution**:
  - Implement WebSocket or Server-Sent Events for real-time updates
  - Add polling mechanism (every 2-3 seconds) while search is active
  - Show loading state for tracks being searched
  - Only display tracks after search completes

### 5. **Artist Results Organization**
- **Problem**: Hundreds of results for popular artists, hard to find right track
- **Solution**:
  - Group results by album (already partially implemented)
  - Add album art from MusicBrainz
  - Implement pagination (show 20 results, load more button)
  - Add search/filter within artist results
  - Sort by: Quality Score, Album, Date, Bitrate

### 6. **Re-search Functionality**
- **Problem**: Re-search button doesn't work
- **Solution**:
  - Fix the delete_track route to properly trigger re-search
  - Clear MusicBrainz cache for that track
  - Add visual feedback when re-search is queued
  - Show track in "searching" state

### 7. **Language Duplicate Prevention**
- **Problem**: Same song in English/Japanese downloaded twice
- **Solution**:
  - Use ISRC as primary deduplication (already implemented)
  - Add MusicBrainz ID matching
  - Fuzzy match romanized vs original titles
  - Warn user if similar track exists (Levenshtein distance < 0.8)

### 8. **Dark/Light Mode Toggle**
- **Problem**: Toggle doesn't work
- **Solution**:
  - Fix CSS classes for light mode
  - Update Tailwind dark: variants
  - Ensure localStorage persistence works
  - Add smooth transition animation

### 9. **Smart Quality Filter UI**
- **Problem**: Filter indicators too large, no toggle to see filtered results
- **Solution**:
  - Make filter badge smaller (pill-style)
  - Add "Show Filtered Results" toggle button
  - Display filtered count
  - Allow temporary disable of filters per track

### 10. **Smart Filtering Effectiveness**
- **Problem**: Filters don't seem to work
- **Solution**:
  - Debug and log filter decisions
  - Add filter statistics to UI
  - Show why each result passed/failed filters
  - Make filter thresholds configurable

### 11. **Download Functionality**
- **Problem**: Downloads don't work
- **Solution**:
  - Debug Slskd API calls
  - Add better error logging
  - Verify API endpoint format
  - Add download queue status display
  - Show download progress from Slskd

### 12. **Album Organization with Metadata**
- **Problem**: Need to use metadata to create albums and avoid duplicates
- **Solution**:
  - Use MusicBrainz release groups
  - Distinguish between: Album, Single, EP, Compilation
  - Add release type to track metadata
  - Group by release type in UI
  - Prevent downloading same track from different releases

## Implementation Order

1. Fix dark/light mode toggle (quick win)
2. Fix download functionality (critical)
3. Implement auto-refresh (UX improvement)
4. Enhance duplicate prevention (critical)
5. Optimize search speed (performance)
6. Fix re-search functionality
7. Improve smart filtering
8. Enhance album organization
9. Add artist results filtering
10. Refine UI elements

## Technical Approach

### Backend Changes
- `app.py`: Fix routes, add caching, improve duplicate detection
- `musicbrainz_client.py`: Add release type detection, album art URLs
- `isrc_tracker.py`: Add fuzzy matching, MusicBrainz ID tracking
- New file: `duplicate_detector.py` for comprehensive duplicate checking

### Frontend Changes
- `base.html`: Fix dark mode CSS
- `index.html`: Add auto-refresh polling, improve album display
- `track.html`: Add filter toggle, pagination, better result display
- New: WebSocket or SSE for real-time updates

### Configuration
- Add configurable filter thresholds
- Add search speed settings
- Add duplicate detection sensitivity settings
